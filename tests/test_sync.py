import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_service import sync_gmail, clean_text
from database import get_session, Newsletter, Settings, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TestSync(unittest.TestCase):

    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Patch get_session to return our test session
        self.get_session_patcher = patch('sync_service.get_session', return_value=self.session)
        self.get_session_patcher.start()

    def tearDown(self):
        self.get_session_patcher.stop()
        self.session.close()

    def test_clean_text(self):
        html = "<html><body><h1>Hello</h1><p>World</p><style>body{color:red}</style></body></html>"
        text = clean_text(html)
        self.assertEqual(text, "Hello\nWorld")

    @patch('sync_service.get_gmail_service')
    def test_sync_logic(self, mock_get_service):
        # Mock Gmail Service
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        # Mock List Messages
        mock_service.users().messages().list().execute.return_value = {
            'messages': [{'id': '123'}]
        }

        # Mock Get Message
        import base64
        body_html = "<html><body>Test Newsletter Content</body></html>"
        b64_body = base64.urlsafe_b64encode(body_html.encode('utf-8')).decode('utf-8')

        mock_service.users().messages().get().execute.return_value = {
            'id': '123',
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': 'Weekly News'},
                    {'name': 'From', 'value': 'newsletter@example.com'},
                    {'name': 'Date', 'value': 'Tue, 23 Jan 2024 10:00:00 +0000'}
                ],
                'body': {'data': b64_body}
            }
        }

        # Run Sync
        count = sync_gmail()

        self.assertEqual(count, 1)

        # Verify DB
        newsletter = self.session.query(Newsletter).first()
        self.assertIsNotNone(newsletter)
        self.assertEqual(newsletter.subject, 'Weekly News')
        self.assertEqual(newsletter.content_text, 'Test Newsletter Content')

if __name__ == '__main__':
    unittest.main()
