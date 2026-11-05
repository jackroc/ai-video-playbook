import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reference_catalog as catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.record = catalog.new_reference("example-1", "Example", "https://x.com/creator/status/123",
                                            "家居与空间", "test", "2026-11-05")

    def test_alias_duplicates_are_rejected_but_distinct_media_on_one_page_survive(self):
        other = copy.deepcopy(self.record)
        other["id"] = "example-2"
        other["source"]["url"] = "https://twitter.com/another-name/status/123?s=20"
        with self.assertRaisesRegex(ValueError, "Duplicate source"):
            catalog.validate([self.record, other])
        self.record["media"]["direct_video_url"] = "https://example.com/first.mp4"
        other["media"]["direct_video_url"] = "https://example.com/second.mp4"
        catalog.validate([self.record, other])
        self.assertEqual(catalog.canonical_url("https://youtu.be/abcdefghijk?t=2"),
                         catalog.canonical_url("https://www.youtube.com/watch?v=abcdefghijk&feature=shared"))

    def test_render_escapes_public_text_and_check_detects_stale_pages(self):
        self.record["title"] = '<img src=x onerror="bad">'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / "README.md"
            readme.write_text("# Test\n\n## 全部作品预览\n\n## 从这里开始\nKeep this text\n")
            catalog.render([self.record], root)
            catalog.render([self.record], root, check=True)
            content = readme.read_text()
            self.assertIn("&lt;img", content)
            self.assertNotIn('<img src=x', content)
            self.assertIn("Keep this text", content)
            readme.write_text(content.replace("&lt;img", "changed"))
            with self.assertRaisesRegex(ValueError, "stale"):
                catalog.render([self.record], root, check=True)

    def test_query_combines_filters_without_upgrading_observation(self):
        self.record["creative"].update(mechanisms=["微缩世界"], summary="手指走进微缩厨房")
        matches = catalog.search([self.record], "手指 厨房", "家居与空间", "微缩世界", "test")
        self.assertEqual(matches, [self.record])
        self.assertEqual(matches[0]["depth"]["status"], "not_reviewed")
        self.assertEqual(catalog.search([self.record], category="食品与饮料"), [])
        self.record["observation"]["method"] = "full_video"
        with self.assertRaisesRegex(ValueError, "observation scope"):
            catalog.validate([self.record])


if __name__ == "__main__":
    unittest.main()
