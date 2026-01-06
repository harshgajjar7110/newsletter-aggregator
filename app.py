from flask import Flask, render_template, request, redirect, url_for, flash
from database import get_session, Newsletter, Settings, engine, Base
from sync_service import sync_gmail
from tts_service import process_newsletter_audio
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key_for_local_testing')

@app.route('/')
def home():
    session = get_session()
    
    # Fetch all newsletters order by date desc
    all_newsletters = session.query(Newsletter).order_by(Newsletter.date_received.desc()).all()
    
    # Group by sender
    grouped_newsletters = {}
    for newsletter in all_newsletters:
        if newsletter.sender not in grouped_newsletters:
            grouped_newsletters[newsletter.sender] = []
        grouped_newsletters[newsletter.sender].append(newsletter)
        
    session.close()
    return render_template('home.html', grouped_newsletters=grouped_newsletters)

@app.route('/sender/<path:sender_name>')
def sender_view(sender_name):
    session = get_session()
    newsletters = session.query(Newsletter).filter_by(sender=sender_name).order_by(Newsletter.date_received.desc()).all()
    session.close()
    return render_template('sender.html', sender=sender_name, newsletters=newsletters)

@app.route('/newsletter/<int:newsletter_id>')
def newsletter_detail(newsletter_id):
    session = get_session()
    newsletter = session.query(Newsletter).filter_by(id=newsletter_id).first()

    if not newsletter:
        session.close()
        return "Not Found", 404

    audio_alignment = None
    if newsletter.audio_path:
        # Assuming audio_path is relative to app root or static
        # newsletter.audio_path is stored as 'static/audio/...'
        # We need to find the json file.
        # Check if it exists relative to current working dir
        json_path = os.path.splitext(newsletter.audio_path)[0] + '.json'
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    audio_alignment = json.load(f)
            except Exception:
                pass

    session.close()
    return render_template('detail.html', newsletter=newsletter, audio_alignment=audio_alignment)

@app.route('/newsletter/<int:newsletter_id>/listen')
def listen_newsletter(newsletter_id):
    path = process_newsletter_audio(newsletter_id)
    if path:
        # Redirect back to detail with audio ready?
        # Or just return path?
        # Better: Redirect back to detail view
        return redirect(url_for('newsletter_detail', newsletter_id=newsletter_id))
    else:
        flash("Could not generate audio.")
        return redirect(url_for('newsletter_detail', newsletter_id=newsletter_id))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    session = get_session()
    if request.method == 'POST':
        label = request.form.get('gmail_label')

        # Update or Insert
        setting = session.query(Settings).filter_by(key='gmail_label').first()
        if not setting:
            setting = Settings(key='gmail_label', value=label)
            session.add(setting)
        else:
            setting.value = label
        session.commit()
        flash('Settings updated.')

    current_label = session.query(Settings).filter_by(key='gmail_label').first()
    label_value = current_label.value if current_label else ''
    session.close()
    return render_template('settings.html', label=label_value)

@app.route('/sync')
def sync_route():
    try:
        count = sync_gmail()
        flash(f'Sync complete. Found {count} new newsletters.')
    except Exception as e:
        flash(f'Sync failed: {str(e)}')

    return redirect(url_for('home'))

if __name__ == '__main__':
    # Ensure DB exists
    Base.metadata.create_all(engine)
    app.run(debug=True, port=5000)
