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

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Lock to prevent concurrent sync operations which can cause port conflicts during auth
sync_lock = threading.Lock()

def get_gmail_service():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                 raise FileNotFoundError("credentials.json not found. Please follow README instructions.")

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                # port=0 allows the OS to pick an available port to avoid collisions
                creds = flow.run_local_server(port=0)
            except OSError as e:
                if "Address already in use" in str(e) or "Only one usage of each socket address" in str(e) or e.errno == 98 or e.errno == 10048:
                    raise RuntimeError("Sync is already in progress or a port conflict occurred. Please try again in a few seconds.") from e
                raise e

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

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
    session = get_session()

    # Get user settings for label
    label_setting = session.query(Settings).filter_by(key='gmail_label').first()
    user_label = label_setting.value if label_setting else None

    query_parts = []
    if user_label:
        query_parts.append(f"label:{user_label}")

    # Also look for unsubscribe in body if no label or in addition?
    # Requirement: "find email where unsubscribe word is there"
    # The user said: "find email where unsubscribe word is there, + add text box support for user where they can add label, so system should look into that label and unsubscribe word"
    # This implies OR logic or maybe AND?
    # "group by sender" -> suggests we want a broad net.
    # Let's search for EITHER: has the label OR has "unsubscribe"

    # Gmail search operator for OR is {query1 query2}
    # But checking for unsubscribe in content is `content:unsubscribe` or just `unsubscribe`

    search_query = ""
    if user_label:
        search_query = f"{{label:{user_label} unsubscribe}}"
    else:
        search_query = "unsubscribe"

    print(f"Searching with query: {search_query}")

    # Fetch messages (limit to last 50 for now to keep it minimal/fast)
    results = service.users().messages().list(userId='me', q=search_query, maxResults=50).execute()
    messages = results.get('messages', [])

    new_count = 0

    if not messages:
        print("No messages found.")
    else:
        for message in messages:
            msg_id = message['id']

            # Check if already exists
            existing = session.query(Newsletter).filter_by(gmail_id=msg_id).first()
            if existing:
                continue

            # Fetch full message
            msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), "")
            date_obj = parse_date(date_str)

            # Extract Body
            body_content = ""
            if 'parts' in msg['payload']:
                for part in msg['payload']['parts']:
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
                data = msg['payload']['body'].get('data')
                if data:
                    body_content = base64.urlsafe_b64decode(data).decode('utf-8')

            if body_content:
                clean_body = clean_text(body_content)

                # Check for unsubscribe word again in parsed text to be sure?
                # The Gmail search API is good, but let's trust it.

                new_newsletter = Newsletter(
                    gmail_id=msg_id,
                    sender=sender,
                    subject=subject,
                    date_received=date_obj,
                    content_text=clean_body
                )
                session.add(new_newsletter)
                new_count += 1
                print(f"Imported: {subject}")

    session.commit()
    return new_count

if __name__ == '__main__':
    # For testing purposes
    try:
        count = sync_gmail()
        print(f"Sync complete. Added {count} new newsletters.")
    except Exception as e:
        print(f"Error: {e}")
