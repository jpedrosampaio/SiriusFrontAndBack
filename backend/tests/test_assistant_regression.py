import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ConversationTests(unittest.TestCase):
    def test_bounded_history_keeps_recent_turns_and_summary(self):
        from assistant_service import compact_history
        messages = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i) + 'x' * 2000} for i in range(100)]
        recent, summary = compact_history(messages, '')
        self.assertLessEqual(len(recent), 12)
        self.assertLessEqual(sum(len(m['content']) for m in recent), 18000)
        self.assertLessEqual(len(summary), 4000)
        self.assertEqual(recent[-1], messages[-1])
        self.assertIn('user:', summary)

    def test_all_frontend_routes_are_known(self):
        from assistant_service import PAGE_NAMES
        for path in ['/studies', '/workouts', '/nutrition', '/finance', '/tasks', '/habits', '/goals', '/calendar', '/profile']:
            self.assertIn(path, PAGE_NAMES)
