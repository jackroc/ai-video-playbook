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

    def test_analysis_requires_full_duration_evidence_and_valid_action_ranges(self):
        r = self.record
        r["review"] = {"status": "analyzed"}
        with self.assertRaisesRegex(ValueError, "full-duration"):
            catalog.validate([r])
        r["media"]["duration_seconds"] = 10
        r["observation"].update(
            method="frames", automated_analysis={"status": "completed"},
            visual_review={"coverage_seconds": [0, 10], "sampled_frames": 10, "file_sha256": "a" * 64})
        r["transfer"].update(suitable_products=[{"examples": ["戒指"]}], replacement_steps=["按实际尺寸替换"])
        r["actions"]["sequence"] = [{"start_seconds": 0, "end_seconds": 11}]
        with self.assertRaisesRegex(ValueError, "exceeds video duration"):
            catalog.validate([r])
        r["actions"]["sequence"][0]["end_seconds"] = 10
        catalog.validate([r])
        self.assertEqual(catalog.search([r], "戒指"), [r])

    def test_review_links_and_missing_author_prompts_stay_explicit(self):
        r = next(r for r in catalog.load() if r.get("review"))
        html = catalog.card(r)
        self.assertIn(catalog.REVIEW_REPORT + "#" + r["id"], html)
        self.assertIn("全片工具分析＋逐秒抽帧复核", html)
        self.assertIn("已查来源未发现", html)
        self.assertNotIn("公开提示词待补", html)
        report = catalog.render_reviews([r])
        self.assertIn(f'<a id="{r["id"]}"></a>', report)
        self.assertIn("&t=", report)
        self.assertIn("未独立连续听验", report)
        self.assertIn("具体例子", report)

    def test_author_excerpts_require_stage_and_keep_editorial_summary_separate(self):
        r = self.record
        r["prompt"].update(status="original_excerpt", text="A clean storyboard", url=r["source"]["url"],
                           completeness="short_excerpt_full_text_at_source")
        with self.assertRaisesRegex(ValueError, "Author excerpt needs stage"):
            catalog.validate([r])
        r["prompt"].update(stage="storyboard_image", summary="分镜图先排工序", summary_label="分镜图写法 · 本库整理")
        catalog.validate([r])
        html = catalog.card(r)
        self.assertIn("分镜图写法 · 本库整理", html)
        self.assertIn("分镜图先排工序", html)
        self.assertNotIn("A clean storyboard", html)

    def test_new_batch_details_keep_spotcheck_scope_and_original_prompt_link(self):
        r = next(r for r in catalog.load() if r["collection"] == "2026-11-06" and r["prompt"].get("stage") == "storyboard_image")
        self.assertEqual(r["observation"]["frame_spotcheck"]["sampled_frames"], 3)
        self.assertNotEqual(r.get("review", {}).get("status"), "analyzed")
        html = catalog.card(r)
        self.assertIn(catalog.NEW_BATCH_REPORT + "#" + r["id"], html)
        report = catalog.render_new_batch([r])
        self.assertIn("分镜图提示词 1 条", report)
        self.assertIn("没有连续观看或听验", report)
        self.assertIn(r["prompt"]["url"], report)
        self.assertIn(r["prompt"]["text"], report)
        self.assertIn("适合商品", report)


if __name__ == "__main__":
    unittest.main()
