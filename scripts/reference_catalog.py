#!/usr/bin/env python3
"""Validate, search and render the public video reference catalog. Standard library only."""

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("data/references.json")
CATEGORIES = ["美妆与香氛", "食品与饮料", "服装与鞋履", "珠宝与配饰", "数码与小家电",
              "家居与空间", "汽车与出行", "运动与健康", "通用商品与品牌"]
OBSERVATIONS = {"source_description", "metadata_only", "frames", "partial_video", "full_video"}


def new_reference(key, title, url, category, collection, checked_at):
    """Conservative starting record. Enrichment must retain its observation provenance."""
    return {
        "schema_version": 1, "id": key, "title": title, "kind": "reference",
        "collection": collection, "category": category, "metadata": category,
        "source": {"url": url, "platform": urlsplit(url).hostname, "creator": None,
                   "published_at": None, "checked_at": checked_at, "availability": "not_checked"},
        "media": {"poster": None, "watch_url": url, "direct_video_url": None,
                  "duration_seconds": None, "aspect_ratio": None},
        "creative": {"mechanisms": ["待分类"], "summary": "创意机制待观察", "hook": None, "payoff": None},
        "actions": {"original_prop": None, "sequence": [], "observed_intervals": []},
        "transfer": {"hypotheses": [], "constraints": [], "requires_product_review": True},
        "depth": {"status": "not_reviewed", "preserves": [], "gaps": [], "notes": None},
        "observation": {"method": "metadata_only", "scope": [], "evidence_urls": [url]},
        "prompt": {"status": "unknown", "label": "提示词待补", "text": None, "url": None},
        "metrics": {"status": "unknown", "traffic": None, "sales": None},
        "experiment": {"status": "not_tested", "record_url": None},
        "links": [{"label": "作品来源", "url": url}],
    }


def save(records, root=ROOT):
    validate(records, root)
    target = root / DATA
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def upsert_community(root, data, key):
    records = load(root) if (root / DATA).exists() else []
    if any(canonical_url(record["source"]["url"]) == canonical_url(data["url"]) for record in records):
        return False
    record = new_reference("community-" + key, data["text"].splitlines()[0][:100] if data["text"] else key,
                           data["url"], "通用商品与品牌", "community", datetime.now(timezone.utc).date().isoformat())
    record["source"].update(platform=data["platform"], creator=data["author"] or None)
    record["creative"]["summary"] = "群分享线索；创意、商品接入与动作均待观察。"
    record["observation"]["scope"] = ["仅公开嵌入正文；未观看视频；未核对评论或截图"]
    if data.get("prompt"):
        record["prompt"].update(status="source_excerpt", text=data["prompt"], url=data["url"],
                                label="公开正文提示词 · 完整性待核实")
    save(records + [record], root)
    render(records + [record], root)
    return True


def canonical_url(url):
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    if host in {"twitter.com", "mobile.twitter.com"}:
        host = "x.com"
    path = parts.path.rstrip("/")
    if host == "x.com":
        match = re.match(r"/[^/]+/status/(\d+)", path)
        if match:
            path = "/i/status/" + match[1]
    if host == "youtube.com" and path == "/watch":
        from urllib.parse import parse_qs
        return "youtube:" + parse_qs(parts.query).get("v", [""])[0]
    if host == "youtu.be":
        return "youtube:" + path.lstrip("/")
    return urlunsplit(("https", host, path, "", ""))


def load(root=ROOT):
    records = json.loads((root / DATA).read_text(encoding="utf-8"))
    validate(records, root)
    return records


def validate(records, root=ROOT):
    ids, sources = set(), set()
    for record in records:
        key = record["id"]
        if not re.fullmatch(r"[a-z0-9-]+", key) or key in ids:
            raise ValueError(f"Invalid or duplicate ID: {key}")
        ids.add(key)
        if record["schema_version"] != 1 or record["category"] not in CATEGORIES:
            raise ValueError(f"Unsupported schema or category: {key}")
        url = record["source"]["url"]
        if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
            raise ValueError(f"Invalid public source: {key}")
        canonical = canonical_url(record["media"]["direct_video_url"] or url)
        if canonical in sources:
            raise ValueError(f"Duplicate source: {url}")
        sources.add(canonical)
        date.fromisoformat(record["source"]["checked_at"])
        if record["observation"]["method"] not in OBSERVATIONS:
            raise ValueError(f"Unknown observation method: {key}")
        if record["depth"]["status"] not in {"not_reviewed", "usable", "risky", "unusable"}:
            raise ValueError(f"Unknown depth status: {key}")
        for field in ("title", "collection", "metadata", "media", "creative", "actions", "transfer", "prompt", "metrics", "experiment", "links"):
            if field not in record:
                raise ValueError(f"Missing {field}: {key}")
        if not record["creative"]["mechanisms"] or not record["creative"]["summary"]:
            raise ValueError(f"Missing creative retrieval information: {key}")
        if record["observation"]["method"] == "full_video" and not record["observation"]["scope"]:
            raise ValueError(f"Full viewing needs an observation scope: {key}")
        for path in (record["media"]["poster"], *(link["url"] for link in record["links"])):
            if not path:
                continue
            parts = urlsplit(path)
            if parts.scheme and parts.scheme != "https":
                raise ValueError(f"Unsupported link scheme: {key}")
            if not parts.scheme:
                local = Path(path.split("#")[0])
                if local.is_absolute() or ".." in local.parts or not (root / local).is_file():
                    raise ValueError(f"Missing or unsafe local asset: {key}: {path}")


def search(records, query="", category=None, mechanism=None, collection=None):
    terms = query.casefold().split()
    found = []
    for record in records:
        if category and record["category"] != category:
            continue
        if mechanism and mechanism not in record["creative"]["mechanisms"]:
            continue
        if collection and record["collection"] != collection:
            continue
        # Source titles, mechanisms, actions and transfer hypotheses are searchable together.
        body = json.dumps(record, ensure_ascii=False).casefold()
        if all(term in body for term in terms):
            found.append(record)
    return found


def html_link(label, url):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def card(record):
    media, prompt = record["media"], record["prompt"]
    poster = media["poster"]
    visual = "<em>作品封面待补</em>"
    if poster:
        image = f'<img src="{escape(poster, quote=True)}" width="220" alt="{escape(record["title"], quote=True)}的作品封面">'
        visual = html_link("", media["watch_url"]).replace("></a>", ">" + image + "</a>")
    text = prompt["text"] or record["creative"]["summary"]
    label = prompt["label"] if prompt["text"] else "创意线索 · 来源说明整理"
    links = list(record["links"])
    direct = media["direct_video_url"]
    if direct and direct not in {item["url"] for item in links}:
        links.append({"label": "播放入口", "url": direct})
    evidence = {"metadata_only": "仅元数据", "source_description": "来源说明", "frames": "抽帧观察",
                "partial_video": "部分观看", "full_video": "完整观看"}[record["observation"]["method"]]
    footer = f'{record["id"]} · {evidence} · 深度{record["depth"]["status"].replace("not_reviewed", "待评估")}'
    if not prompt["text"]:
        footer += " · 公开提示词待补"
    return "\n".join([
        '  <td width="50%" valign="top">',
        f'    <h4>{escape(record["title"])}</h4>',
        f'    <p><strong>{escape(record["metadata"])}</strong></p>',
        f'    <p>{visual}</p>',
        f'    <p><strong>{escape(label)}</strong></p>',
        f'    <blockquote>{escape(text)}</blockquote>',
        '    <p>' + " · ".join(html_link(item["label"], item["url"]) for item in links) + '</p>',
        f'    <p><sub>{escape(footer)}</sub></p>',
        '  </td>',
    ])


def render(records, root=ROOT, check=False):
    readme = root / "README.md"
    current = readme.read_text(encoding="utf-8")
    intro = """# AI Video Playbook · 商品创意视频参考库

为商品创意选片积累原片、观看依据、动作与跨品类联想。面向 TikTok 商品，也收录其他平台和品牌广告的创意参考。

[全部作品预览](#全部作品预览) · [创意机制索引](references/INDEX.md) · [新增 100 条](references/2026-11-05-creative-commerce-100.md) · [收录与检索](docs/reference-library.md)

"""
    for record in records:
        if record["kind"] == "generated":
            intro += f'## 原创成片\n\n### {record["title"]}\n\n**{record["metadata"]}**\n\n'
            intro += record["media"]["direct_video_url"] + "\n\n"
            intro += "**实际提示词节选**\n\n```text\n" + (record["prompt"]["text"] or "") + "\n```\n\n"
            intro += " · ".join(f'[{item["label"]}]({item["url"]})' for item in record["links"]) + "\n\n"
    tail = "## 从这里开始\n" + current.split("## 从这里开始\n", 1)[1]
    references = [record for record in records if record["kind"] != "generated"]
    counts = Counter(record["collection"] for record in records)
    lines = ["## 全部作品预览", "", f"收录 {len(records)} 个案例。按商品浏览，或从[创意机制索引](references/INDEX.md)跨品类找动作与看点。", "",
             "卡片区分来源说明、抽帧和观看记录。提示词要点为中文整理，公开原文见来源；具体商品能否替换，需要在使用时核对。", "",
             " · ".join(f"[{name}](#{name})" for name in CATEGORIES), "",
             "[结构化数据](data/references.json) · [数据字段与收录方法](docs/reference-library.md)", ""]
    for category in CATEGORIES:
        group = [record for record in references if record["category"] == category]
        group.sort(key=lambda record: (not bool(record["media"]["poster"]), record["id"]))
        if not group:
            continue
        lines.extend([f"### {category}", "", "<table>"])
        for offset in range(0, len(group), 2):
            lines.append("<tr>")
            lines.extend(card(record) for record in group[offset:offset + 2])
            if offset + 1 == len(group):
                lines.append('  <td width="50%"></td>')
            lines.append("</tr>")
        lines.extend(["</table>", ""])
    outputs = {readme: intro + "\n".join(lines) + "\n" + tail}
    mechanisms = sorted({tag for record in records for tag in record["creative"]["mechanisms"]})
    index = ["# 创意机制索引", "", "由 data/references.json 生成。这里的机制标签用于寻找线索，商品适配和深度可用性按当前商品另行核对。", "",
             "[回到作品预览](../README.md#全部作品预览) · [字段说明](../docs/reference-library.md)", ""]
    for mechanism in mechanisms:
        group = search(records, mechanism=mechanism)
        index.extend([f"## {mechanism}（{len(group)}）", "", "| 案例 | 商品方向 | 观察依据 | 原片 |", "| --- | --- | --- | --- |"])
        for record in group:
            title = record["title"].replace("|", " ")
            index.append(f'| {record["id"]} · {title} | {record["category"]} | {record["observation"]["method"]} | [来源]({record["source"]["url"]}) |')
        index.append("")
    outputs[root / "references/INDEX.md"] = "\n".join(index)
    batch = [record for record in records if record["collection"] == "2026-11-05"]
    report = ["# 新增 100 条创意商品视频参考 · 2026-11-05", "",
              "本批按具体创意机制筛选，包含品牌广告和历史作品。来源说明与公开播放器元数据已核对；尚未逐条连续观看或进行深度复刻，商品接入均为待验证假设。", "",
              "[全部封面预览](../README.md#全部作品预览) · [创意机制索引](INDEX.md) · [完整结构化数据](../data/references.json)", ""]
    report.extend(["## 优先补看清单", "", "这 20 条覆盖不同机制，优先补连续观看、声音和关键动作区间。当前仍为来源说明级线索。", ""])
    for record in batch:
        if record.get("review_priority") == "first_20":
            report.append(f'- [{record["title"]}]({record["source"]["url"]}) · {record["id"]}')
    report.append("")
    for record in batch:
        report.extend([f'## {record["id"]} · {record["title"]}', "",
                       f'**{record["category"]} · {" / ".join(record["creative"]["mechanisms"])}**', "",
                       record["creative"]["summary"], "",
                       "**接入假设** " + "".join(record["transfer"]["hypotheses"]), "",
                       "**待核实** " + "".join(record["transfer"]["constraints"]), "",
                       " · ".join(f'[{item["label"]}]({item["url"]})' for item in record["links"]), ""])
    outputs[root / "references/2026-11-05-creative-commerce-100.md"] = "\n".join(report)
    for path, content in outputs.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise ValueError(f"Generated file is stale: {path.relative_to(root)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "render", "search"])
    parser.add_argument("--query", default="")
    parser.add_argument("--category", choices=CATEGORIES)
    parser.add_argument("--mechanism")
    parser.add_argument("--collection")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="Compare generated files without writing")
    args = parser.parse_args()
    records = load()
    if args.command == "render":
        print(json.dumps(render(records, check=args.check), ensure_ascii=False))
    elif args.command == "validate":
        print(f"Valid references: {len(records)}")
    else:
        if args.limit < 1:
            parser.error("--limit must be positive")
        matches = search(records, args.query, args.category, args.mechanism, args.collection)[:args.limit]
        if args.json:
            print(json.dumps(matches, ensure_ascii=False, indent=2))
        else:
            for record in matches:
                print(f'{record["id"]}\t{record["title"]}\t{record["source"]["url"]}')


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
