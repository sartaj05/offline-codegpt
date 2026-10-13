import tempfile
import unittest
from pathlib import Path

import requests

from scripts.local_connector import execute_command, flush_queue, load_queue, post_result_or_queue, queue_result


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.posts = []

    def post(self, url, json, timeout):
        self.posts.append((url, json, timeout))
        return FakeResponse()


class OfflineQueueTests(unittest.TestCase):
    def test_results_are_deduplicated_and_flushed(self):
        with tempfile.TemporaryDirectory() as folder:
            queue_file = Path(folder) / "queue.json"
            queue_result(queue_file, "task-1", {"status": "completed", "result": {"value": 1}})
            queue_result(queue_file, "task-1", {"status": "completed", "result": {"value": 2}})
            self.assertEqual(load_queue(queue_file)[0]["body"]["result"]["value"], 2)
            session = FakeSession()
            self.assertEqual(flush_queue(session, "https://example.test", queue_file), 1)
            self.assertFalse(queue_file.exists())
            self.assertEqual(len(session.posts), 1)

    def test_connection_failure_keeps_result_for_later(self):
        class OfflineSession:
            def post(self, url, json, timeout):
                raise requests.ConnectionError("offline")

        with tempfile.TemporaryDirectory() as folder:
            queue_file = Path(folder) / "queue.json"
            self.assertFalse(post_result_or_queue(OfflineSession(), "https://example.test", queue_file, "task-2", {"status": "failed"}))
            self.assertEqual(load_queue(queue_file)[0]["command_id"], "task-2")

    def test_patch_preview_apply_and_undo_stay_in_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "app.py"
            target.write_text("print('old')\n", encoding="utf-8")
            preview = execute_command({"operation": "patch.preview", "payload": {"path": "app.py", "new_content": "print('new')\n"}}, root, "http://127.0.0.1:11434")
            self.assertIn("-print('old')", preview["diff"])
            applied = execute_command({"operation": "patch.apply", "payload": {"path": "app.py", "expected_content": "print('old')\n", "new_content": "print('new')\n"}}, root, "http://127.0.0.1:11434")
            self.assertEqual(target.read_text(encoding="utf-8"), "print('new')\n")
            execute_command({"operation": "patch.undo", "payload": {"path": "app.py", "expected_content": applied["updated"], "original_content": applied["original"]}}, root, "http://127.0.0.1:11434")
            self.assertEqual(target.read_text(encoding="utf-8"), "print('old')\n")


if __name__ == "__main__":
    unittest.main()
