from flask import Flask, render_template, request, redirect, url_for, flash
from flask import jsonify
from database import get_session, Newsletter, Settings, engine, Base
from sync_service import sync_gmail
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key_for_local_testing')

@app.route('/')
def home():
    session = get_session()

    # "Unread" Tab: Grouped by Sender
    # We want senders who have at least one 'unread' newsletter
    # And we want the count of unread for them

    # Raw SQL might be easier for aggregation, or using SQLAlchemy func
    from sqlalchemy import func

    # Query for Senders with count of unread
    unread_stats = session.query(
        Newsletter.sender,
        func.count(Newsletter.id)
    ).filter(
        Newsletter.status == 'unread'
    ).group_by(
        Newsletter.sender
    ).all()

    # unread_stats is list of (sender, count)

    # "Listening" Tab: Newsletters in progress
    in_progress = session.query(Newsletter).filter(
        Newsletter.status == 'in_progress'
    ).order_by(
        Newsletter.date_received.desc()
    ).all()

    session.close()
    return render_template('home.html', unread_stats=unread_stats, in_progress=in_progress)

@app.route('/sender/<path:sender_name>')
def sender_view(sender_name):
    session = get_session()
    # Show unread first, then others?
    # Or just all for that sender
    newsletters = session.query(Newsletter).filter(
        Newsletter.sender == sender_name,
        Newsletter.status != 'done' # Hide done ones from the main stack view? Or show all?
        # Requirement: "group by sender"
        # Let's show all except deleted/archived (we treat 'done' as archive for now)
    ).order_by(
        Newsletter.status, # unread/in_progress alphabetical? maybe not ideal.
        Newsletter.date_received.desc()
    ).all()
    session.close()
    return render_template('sender.html', sender=sender_name, newsletters=newsletters)

@app.route('/newsletter/<int:newsletter_id>')
def newsletter_detail(newsletter_id):
    session = get_session()
    newsletter = session.query(Newsletter).filter_by(id=newsletter_id).first()

    if not newsletter:
        session.close()
        return "Not Found", 404

    session.close()
    return render_template('detail.html', newsletter=newsletter)

@app.route('/api/newsletter/<int:newsletter_id>/status', methods=['POST'])
def update_status(newsletter_id):
    session = get_session()
    newsletter = session.query(Newsletter).filter_by(id=newsletter_id).first()

    if not newsletter:
        session.close()
        return jsonify({'error': 'Not found'}), 404

    data = request.json
    new_status = data.get('status')

    if new_status in ['unread', 'in_progress', 'done']:
        newsletter.status = new_status
        session.commit()
        session.close()
        return jsonify({'success': True, 'status': new_status})

    session.close()
    return jsonify({'error': 'Invalid status'}), 400

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
