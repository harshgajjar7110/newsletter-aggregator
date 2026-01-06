import threading
import time
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_service import sync_gmail, sync_lock

class TestSyncConcurrency(unittest.TestCase):

    @patch('sync_service._sync_gmail_impl')
    def test_concurrent_sync(self, mock_impl):
        # Mock the implementation to take some time
        def long_running_sync():
            time.sleep(1)
            return 10

        mock_impl.side_effect = long_running_sync

        # Define a wrapper to run sync in a thread
        results = []
        errors = []

        def run_sync():
            try:
                res = sync_gmail()
                results.append(res)
            except RuntimeError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f"Unexpected: {e}")

        # Start two threads
        t1 = threading.Thread(target=run_sync)
        t2 = threading.Thread(target=run_sync)

        t1.start()
        # Ensure t1 gets the lock first
        time.sleep(0.1)
        t2.start()

        t1.join()
        t2.join()

        # Expect 1 success and 1 failure
        self.assertEqual(len(results), 1, "Should have 1 successful sync")
        self.assertEqual(len(errors), 1, "Should have 1 error")
        self.assertIn("Sync is already running", errors[0])

if __name__ == '__main__':
    unittest.main()
