import os.path
import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from database import get_session, Newsletter, Settings
from datetime import datetime
import re
import threading
import concurrent.futures

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Lock to prevent concurrent sync operations which can cause port conflicts during auth
sync_lock = threading.Lock()

def get_credentials():
    """
    Returns valid user credentials.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8081)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def get_gmail_service():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    return service

def clean_text(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()

    text = soup.get_text(separator='\n')

    # Break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)

    return text

def parse_date(date_str):
    # Example format: "Tue, 23 Jan 2024 10:00:00 +0000" or similar
    # Using a generic parser or trying a few formats
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception as e:
        print(f"Error parsing date {date_str}: {e}")
        return datetime.now()

def fetch_and_parse_message(creds, msg_id):
    """
    Fetches and parses a single message. Running in a thread.
    Returns a dict with data or None if failed.
    """
    try:
        # Build a thread-local service
        service = build('gmail', 'v1', credentials=creds)
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

        payload = msg.get('payload', {})
        headers = payload.get('headers', [])
        
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
        date_str = next((h['value'] for h in headers if h['name'] == 'Date'), "")
        date_obj = parse_date(date_str)

        # Extract Body
        body_content = ""
        parts = payload.get('parts', [])
        
        if parts:
            for part in parts:
                if part['mimeType'] == 'text/html':
                    data = part['body'].get('data')
                    if data:
                        body_content = base64.urlsafe_b64decode(data).decode('utf-8')
                        break # Prefer HTML
                elif part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body_content = base64.urlsafe_b64decode(data).decode('utf-8')
        else:
             # Multipart/alternative might not be at top level, or it's a simple message
            data = payload.get('body', {}).get('data')
            if data:
                body_content = base64.urlsafe_b64decode(data).decode('utf-8')

        if body_content:
            clean_body = clean_text(body_content)
            return {
                'gmail_id': msg_id,
                'sender': sender,
                'subject': subject,
                'date_received': date_obj,
                'content_text': clean_body
            }
    except Exception as e:
        print(f"Error processing message {msg_id}: {e}")
        return None
    return None

def sync_gmail():
    # Use lock to ensure only one sync happens at a time
    if not sync_lock.acquire(blocking=False):
        raise RuntimeError("Sync is already running. Please wait.")

    try:
        return _sync_gmail_impl()
    finally:
        sync_lock.release()

def _sync_gmail_impl():
    service = get_gmail_service()
    creds = get_credentials()
    session = get_session()

    # Get user settings for label
    label_setting = session.query(Settings).filter_by(key='gmail_label').first()
    user_label = label_setting.value if label_setting else None

    search_query = ""
    if user_label:
        search_query = f"{{label:{user_label} unsubscribe}}"
    else:
        search_query = "unsubscribe"

    print(f"Searching with query: {search_query}")

    total_new_count = 0
    page_token = None
    
    # Process in chunks (pages)
    while True:
        try:
            results = service.users().messages().list(userId='me', q=search_query, pageToken=page_token, maxResults=50).execute()
        except Exception as e:
            print(f"Error fetching page: {e}")
            break

        messages = results.get('messages', [])
        page_token = results.get('nextPageToken')

        if not messages:
            if not page_token:
                break
            continue

        print(f"Processing batch of {len(messages)} messages...")
        
        # Filter out already existing messages BEFORE threading to save API calls
        # fetches all existing IDs in this batch
        msg_ids = [m['id'] for m in messages]
        existing_db = session.query(Newsletter.gmail_id).filter(Newsletter.gmail_id.in_(msg_ids)).all()
        existing_ids = set(r[0] for r in existing_db)
        
        to_process_ids = [mid for mid in msg_ids if mid not in existing_ids]

        if not to_process_ids:
            print("All messages in this batch already exist. Moving to next page.")
            if not page_token:
                break
            continue

        # Threaded processing for the new messages
        new_newsletters_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Pass creds so each thread builds its own service
            future_to_id = {executor.submit(fetch_and_parse_message, creds, mid): mid for mid in to_process_ids}
            
            for future in concurrent.futures.as_completed(future_to_id):
                result = future.result()
                if result:
                    new_newsletters_data.append(result)

        # Bulk Insert (or one by one) in Main Thread
        for data in new_newsletters_data:
            new_newsletter = Newsletter(
                gmail_id=data['gmail_id'],
                sender=data['sender'],
                subject=data['subject'],
                date_received=data['date_received'],
                content_text=data['content_text']
            )
            session.add(new_newsletter)
            total_new_count += 1
            try:
                print(f"Imported: {data['subject']} ({data['sender']})")
            except Exception:
                # Safe print for consoles that don't support special characters
                safe_subject = data['subject'].encode('ascii', 'replace').decode('ascii')
                safe_sender = data['sender'].encode('ascii', 'replace').decode('ascii')
                print(f"Imported: {safe_subject} ({safe_sender})")

        # Commit per page/batch
        session.commit()
        print(f"Batch committed. Total new so far: {total_new_count}")

        if not page_token:
            break
            
    return total_new_count

if __name__ == '__main__':
    # For testing purposes
    try:
        count = sync_gmail()
        print(f"Sync complete. Added {count} new newsletters.")
    except Exception as e:
        print(f"Error: {e}")
