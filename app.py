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
    # Group by sender?
    # Logic: Get all newsletters, order by date desc.
    # Grouping usually happens in UI or query.
    # Let's list unique senders first? Or just a flat list?
    # Requirement: "list of newsltter group by sender"

    # Let's get list of senders
    senders = session.query(Newsletter.sender).distinct().all()
    senders = [s[0] for s in senders]

    # Get latest 5 newsletters for dashboard
    latest = session.query(Newsletter).order_by(Newsletter.date_received.desc()).limit(5).all()

    session.close()
    return render_template('home.html', senders=senders, latest=latest)

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

    # Check if audio exists, if not, offer to generate?
    # Or just generate on fly?
    # Let's pass the object to template.

    session.close()
    return render_template('detail.html', newsletter=newsletter)

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
