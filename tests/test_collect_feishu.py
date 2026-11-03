import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_feishu as collector


class CollectorTests(unittest.TestCase):
    def test_extracts_public_posts_and_removes_tracking(self):
        text = "看这个 https://twitter.com/creator/status/123/video/1?s=20，和 https://www.tiktok.com/@a/video/456?_t=private。"
        self.assertEqual(collector.links_in(text), ["https://x.com/creator/status/123", "https://www.tiktok.com/@a/video/456"])
        self.assertEqual(collector.links_in("https://x.com.evil.example/a/status/1 https://user@x.com/a/status/1 https://x.com:999/a/status/1"), [])

    def test_group_and_sender_filter_and_duplicate_event(self):
        event = {"chat_id": "oc_target", "message_type": "text", "sender_type": "user", "message_id": "om_1",
                 "content": "private comment https://x.com/a/status/123?s=20"}
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE jobs (url TEXT PRIMARY KEY, message_id TEXT)")
            self.assertEqual(collector.enqueue(event, "oc_other", db), 0)
            self.assertEqual(collector.enqueue(dict(event, sender_type="bot"), "oc_target", db), 0)
            self.assertEqual(collector.enqueue(event, "oc_target", db), 1)
            self.assertEqual(collector.enqueue(dict(event, message_id="om_2", content="https://twitter.com/a/status/123"), "oc_target", db), 0)
            self.assertEqual(db.execute("SELECT url FROM jobs").fetchone(), ("https://x.com/a/status/123",))

    def test_history_replays_only_eligible_group_links(self):
        m = {"message_id": "om_1", "sender": {"sender_type": "user"}, "msg_type": "text",
             "content": "https://x.com/a/status/123", "chat_id": "oc_target"}
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE jobs (url TEXT PRIMARY KEY, message_id TEXT)")
            self.assertEqual(collector.enqueue(collector.history_event(dict(m, deleted=True), "oc_target"), "oc_target", db), 0)
            self.assertEqual(collector.enqueue(collector.history_event(dict(m, chat_id="oc_other"), "oc_target"), "oc_target", db), 0)
            self.assertEqual(collector.enqueue(collector.history_event(m, "oc_target"), "oc_target", db), 1)
            self.assertEqual(collector.enqueue(collector.history_event(m, "oc_target"), "oc_target", db), 0)

    def test_uses_public_body_to_extract_prompt_and_classify(self):
        payload = json.dumps({"author_name": "Example Creator", "html": "<blockquote><p>Funny UGC<br>Prompt: a small scene</p></blockquote><script>not a prompt</script>"})
        url = "https://x.com/a/status/123"
        with patch.object(collector, "get_public", return_value=(url, payload)):
            data = collector.metadata(url)
        self.assertEqual(collector.classify(data["text"]), ["ugc", "comedy"])
        self.assertEqual(collector.prompt_from(data["text"]), "a small scene")
        self.assertNotIn("not a prompt", collector.render(data))
        self.assertIn("未自行复现", collector.render(data))

    def test_access_failure_keeps_original_link_pending(self):
        url = "https://vm.tiktok.com/Abc123/"
        with patch.object(collector, "get_public", side_effect=ValueError("unavailable")):
            data = collector.metadata(url)
        self.assertEqual(data["url"], url)
        self.assertEqual(collector.classify(data["text"]), ["inbox"])
        self.assertIn("待补", collector.render(data))

    def test_redirect_cannot_reach_unapproved_host(self):
        with self.assertRaises(ValueError):
            collector.SafeRedirect().redirect_request(None, None, 302, "", {}, "https://127.0.0.1/test")

    def test_publish_reaches_remote_once_and_indexes_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bare = root / "remote.git"
            seed = root / "seed"
            worker = root / "worker"
            subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(bare)], check=True, capture_output=True)
            subprocess.run(["git", "init", "--initial-branch=main", str(seed)], check=True, capture_output=True)
            collector.git(seed, "config", "user.name", "Collector Test")
            collector.git(seed, "config", "user.email", "collector@example.test")
            collector.git(seed, "commit", "--allow-empty", "-m", "initial")
            collector.git(seed, "push", str(bare), "main")
            data = {"url": "https://x.com/a/status/123", "platform": "X", "author": "Creator",
                    "text": "UGC\nPrompt: example", "access": "已读取公开嵌入信息"}
            with patch.object(collector, "REPO_URL", str(bare)), patch.object(collector, "ROOT", seed):
                result = collector.publish(worker, data)
                head = collector.git(bare, "rev-parse", "main")
                self.assertEqual(collector.publish(worker, data), result)
                self.assertEqual(collector.git(bare, "rev-parse", "main"), head)
            self.assertTrue(result.endswith("references/community/ugc/x-123.md"))
            self.assertIn("ugc/x-123.md", collector.git(bare, "show", "main:references/community/README.md"))
            self.assertIn("Prompt: example", collector.git(bare, "show", "main:references/community/ugc/x-123.md"))


if __name__ == "__main__":
    unittest.main()
