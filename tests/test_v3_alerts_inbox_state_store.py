from __future__ import annotations

import os
import tempfile
import unittest

from watchfuleye.v3.alerts.inbox_state_store import get_last_seen_event_id, set_last_seen_event_id


class TestV3AlertsInboxStateStore(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_env = dict(os.environ)
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        os.environ["DB_PATH"] = self.tmp.name

    def tearDown(self) -> None:
        try:
            os.unlink(self.tmp.name)
        except Exception:
            pass
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_default_last_seen_is_zero(self) -> None:
        self.assertEqual(get_last_seen_event_id(user_id=123), 0)

    def test_set_last_seen_monotonic(self) -> None:
        self.assertEqual(set_last_seen_event_id(user_id=123, last_seen_event_id=10), 10)
        # Cannot go backwards.
        self.assertEqual(set_last_seen_event_id(user_id=123, last_seen_event_id=5), 10)
        # Can advance.
        self.assertEqual(set_last_seen_event_id(user_id=123, last_seen_event_id=42), 42)


if __name__ == "__main__":
    unittest.main()


