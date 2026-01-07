from database import get_session, Newsletter, Base, engine
from datetime import datetime

Base.metadata.create_all(engine) # Ensure tables exist
session = get_session()

# Check if exists
if not session.query(Newsletter).filter_by(id=1).first():
    n = Newsletter(
        sender="The Morning Brew",
        subject="Market Crash? What you need to know.",
        date_received=datetime.now(),
        content_text="Welcome to the Morning Brew. Today the markets took a tumble. Apple is down 5%. Google is up 2%. Stay tuned for more updates. This is a long sentence to test the chunking logic of the text to speech engine.",
        gmail_id="test_v2_123",
        status='unread'
    )
    session.add(n)
    session.commit()
    print("Seeded newsletter.")
else:
    print("Newsletter already exists.")

session.close()
