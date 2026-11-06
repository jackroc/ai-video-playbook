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
REVIEW_REPORT = "references/2026-11-06-priority-20-analysis.md"
NEW_BATCH_REPORT = "references/2026-11-06-creative-commerce-100.md"
CURATED_INDEX = "references/2026-11-06-curated-100.md"
CATEGORY_SLUGS = {"美妆与香氛": "beauty", "食品与饮料": "food", "服装与鞋履": "apparel",
                  "珠宝与配饰": "accessories", "数码与小家电": "electronics", "家居与空间": "home",
                  "汽车与出行": "automotive", "运动与健康": "sports", "通用商品与品牌": "general"}
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
    ids, sources, positions = set(), set(), set()
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
        prompt = record["prompt"]
        if prompt["status"] == "original_excerpt":
            if (prompt.get("stage") not in {"video", "storyboard_image", "image"}
                    or not prompt.get("text") or not prompt.get("url")
                    or urlsplit(prompt["url"]).scheme != "https"
                    or prompt.get("completeness") != "short_excerpt_full_text_at_source"):
                raise ValueError(f"Author excerpt needs stage, text and original link: {key}")
        if record["observation"]["method"] == "full_video" and not record["observation"]["scope"]:
            raise ValueError(f"Full viewing needs an observation scope: {key}")
        if record.get("review", {}).get("status") == "analyzed":
            duration = record["media"]["duration_seconds"]
            visual = record["observation"].get("visual_review", {})
            coverage = visual.get("coverage_seconds", [])
            if (not duration or len(coverage) != 2 or coverage[0] != 0
                    or abs(coverage[1] - duration) > .001
                    or visual.get("sampled_frames", 0) < int(duration)
                    or not re.fullmatch(r"[a-f0-9]{64}", visual.get("file_sha256", ""))
                    or record["observation"].get("automated_analysis", {}).get("status") != "completed"):
                raise ValueError(f"Analysis needs full-duration visual evidence: {key}")
            if not record["actions"]["sequence"] or not record["transfer"].get("suitable_products") or not record["transfer"].get("replacement_steps"):
                raise ValueError(f"Analysis needs actions and product substitution: {key}")
            for step in record["actions"]["sequence"]:
                if not 0 <= step["start_seconds"] < step["end_seconds"] <= duration + .001:
                    raise ValueError(f"Action interval exceeds video duration: {key}")
        if record.get("curation"):
            selected = record["curation"]
            position = selected.get("position")
            expected = f'references/curated-100/{CATEGORY_SLUGS[record["category"]]}.md#{key}'
            if (record.get("review", {}).get("status") != "analyzed" or not selected.get("reason")
                    or not isinstance(position, int) or not 1 <= position <= 100 or position in positions
                    or selected.get("report") != expected):
                raise ValueError(f"Curated reference needs complete analysis and a unique position: {key}")
            positions.add(position)
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


def search(records, query="", category=None, mechanism=None, collection=None, curated=False):
    terms = query.casefold().split()
    found = []
    for record in records:
        if curated and not record.get("curation"):
            continue
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
    if curated:
        found.sort(key=lambda record: record["curation"]["position"])
    return found


def html_link(label, url):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def review_link(record, prefix=""):
    target = record.get("curation", {}).get("report") or record.get("review", {}).get("report")
    return prefix + (target or f'{REVIEW_REPORT}#{record["id"]}')


def timestamp(seconds):
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def observation_label(record):
    if record.get("review", {}).get("status") == "analyzed":
        return "全片工具分析＋逐秒抽帧复核"
    return {"metadata_only": "仅元数据", "source_description": "来源说明", "frames": "抽帧观察",
            "partial_video": "部分观看", "full_video": "完整观看"}[record["observation"]["method"]]


def card(record):
    media, prompt = record["media"], record["prompt"]
    poster = media["poster"]
    visual = "<em>作品封面待补</em>"
    if poster:
        image = f'<img src="{escape(poster, quote=True)}" width="220" alt="{escape(record["title"], quote=True)}的作品封面">'
        visual = html_link("", media["watch_url"]).replace("></a>", ">" + image + "</a>")
    text = prompt.get("summary") or prompt["text"] or record["creative"]["summary"]
    reviewed = record.get("review", {}).get("status") == "analyzed"
    fallback_label = "创意与动作 · 全片辅助分析" if reviewed else ("创意线索 · 抽帧与来源说明" if record["observation"]["method"] == "frames" else "创意线索 · 来源说明整理")
    label = prompt.get("summary_label") or (prompt["label"] if prompt["text"] else fallback_label)
    links = list(record["links"])
    extra = []
    if reviewed:
        links.append({"label": "动作拆解 / 适合商品 / 替换步骤", "url": review_link(record)})
    elif record["collection"] == "2026-11-06":
        links.append({"label": "商品适配 / 换品思路 / 核实记录", "url": NEW_BATCH_REPORT + "#" + record["id"]})
    if record["transfer"].get("suitable_products"):
        examples = [item for group in record["transfer"]["suitable_products"] for item in group["examples"]]
        extra = [f'    <p><strong>适合商品：</strong>{escape("、".join(examples))}</p>']
    direct = media["direct_video_url"]
    if direct and direct not in {item["url"] for item in links}:
        links.append({"label": "播放入口", "url": direct})
    evidence = observation_label(record)
    footer = f'{record["id"]} · {evidence} · 深度{record["depth"]["status"].replace("not_reviewed", "待评估")}'
    if record.get("curation"):
        footer = f'精选 {record["curation"]["position"]:03d} · {record["curation"]["lens"]} · ' + footer
    if not prompt["text"]:
        if prompt.get("stage") == "unknown" and "评论" in prompt.get("scope", ""):
            footer += " · 正文未取得完整提示词，评论待查"
        else:
            footer += " · 原作者提示词：已查来源未发现" if prompt["status"] == "not_found_in_checked_sources" else " · 公开提示词待补"
    return "\n".join([
        '  <td width="50%" valign="top">',
        f'    <h4>{escape(record["title"])}</h4>',
        f'    <p><strong>{escape(record["metadata"])}</strong></p>',
        f'    <p>{visual}</p>',
        f'    <p><strong>{escape(label)}</strong></p>',
        f'    <blockquote>{escape(text)}</blockquote>',
        *extra,
        '    <p>' + " · ".join(html_link(item["label"], item["url"]) for item in links) + '</p>',
        f'    <p><sub>{escape(footer)}</sub></p>',
        '  </td>',
    ])


def render_new_batch(records):
    batch = [r for r in records if r["collection"] == "2026-11-06"]
    stages = Counter(r["prompt"].get("stage", "unknown") for r in batch)
    ai = sum(r["source"]["platform"] == "x.com" for r in batch)
    analyzed = sum(r.get("review", {}).get("status") == "analyzed" for r in batch)
    spotchecked = sum(bool(r["observation"].get("frame_spotcheck")) for r in batch)
    descriptions = sum(r["observation"]["method"] == "source_description" for r in batch)
    lines = ["# 新增 100 条创意带货视频参考 · 2026-11-06", "",
             f"本批 {len(batch)} 条：{ai} 条 AI 创作者作品、{len(batch) - ai} 条品牌广告与历史经典。原链接和媒体标识均与既有案例去重；跨账号重传仍可能漏识别。", "",
             f"已取得作者正文中的视频提示词 {stages['video']} 条、分镜图提示词 {stages['storyboard_image']} 条、场景生图提示词 {stages['image']} 条。保留短摘录与原帖入口，另写中文要点；未取得的评论区指令不凭空补写。", "",
             f"**观察范围：** 其中{analyzed}条已升级为全片工具分析＋逐秒画面复核，详见[精选100详解](2026-11-06-curated-100.md)。其余{spotchecked}条仅三处抽帧、{descriptions}条仍为来源说明级。声音未独立连续听验，商品适配与换品均未试生成。", "",
             "片长：取得实际文件的以文件为准，其余品牌广告为搜索卡片约数。历史活动年份与上传日期分开保存。X互动仅为2026-11-06的帖子累计快照，不能当销量或实时增速。", "",
             "[全部双列预览](../README.md#全部作品预览) · [机制索引](INDEX.md) · [上一批100条](2026-11-05-creative-commerce-100.md) · [已补20条全片分析](2026-11-06-priority-20-analysis.md)", "",
             "## 按商品选参考", "", "| 案例 | 适合商品 | 提示词类型 | 观察依据 |", "| --- | --- | --- | --- |"]
    for r in batch:
        examples = "、".join(x for group in r["transfer"]["suitable_products"] for x in group["examples"])
        stage = {"video": "视频原文入口", "storyboard_image": "分镜图原文入口", "image": "场景生图原文入口"}.get(r["prompt"].get("stage"), "未取得")
        lines.append(f'| [{r["title"]}](#{r["id"]}) | {examples} | {stage} | {observation_label(r)} |')
    for r in batch:
        prompt, media, source = r["prompt"], r["media"], r["source"]
        lines.extend(["", f'<a id="{r["id"]}"></a>', "", f'## {r["id"]} · {r["title"]}', "",
                      f'**{r["metadata"]}**', "", f'[![作品封面]({media["poster"]})]({media["watch_url"]})', "",
                      " · ".join(f'[{item["label"]}]({item["url"]})' for item in r["links"]), "",
                      "**创意线索** " + r["creative"]["summary"], "",
                      "**机制** " + " / ".join(r["creative"]["mechanisms"]), "",
                      "**适合商品（待按实物确认）** " + "、".join(x for group in r["transfer"]["suitable_products"] for x in group["examples"]), "",
                      "**换品思路** " + "".join(r["transfer"]["hypotheses"]), "",
                      "**限制与待核实** " + "；".join(r["transfer"]["constraints"]), "",
                      "### 提示词", ""])
        if r.get("curation"):
            lines.extend([f'[完整动作拆解、商品适配与换品步骤]({r["curation"]["report"].removeprefix("references/")})', ""])
        if prompt["text"]:
            lines.extend([f'**{prompt["summary_label"]}** {prompt["summary"]}', "",
                          f'**{prompt["label"]}**', "", "> " + prompt["text"], "",
                          f'[查看作者完整正文]({prompt["url"]})。此处是短摘录；中文写法由本库整理，不是作者完整提示词。', ""])
        else:
            lines.extend([prompt["scope"], ""])
        lines.extend(["### 来源与核实", "",
                      f'- {"原帖账号" if source["creator_role"] == "posting_account" else "当前版本上传者"}：{source["creator"]}；核对日期：{source["checked_at"]}。'])
        lines.extend('- ' + scope for scope in r["observation"]["scope"])
        if source.get("published_at"):
            lines.append(f'- 原帖发布时间（UTC）：{source["published_at"]}。模型名称为作者自述，未独立验证。')
        else:
            lines.append('- 当前视频上传日期未知；文章日期与历史活动年份不代填上传日期。')
        if source.get("description_published_at"):
            lines.append(f'- 剧情来源文章日期：{source["description_published_at"]}。')
        if source.get("campaign_year"):
            lines.append(f'- 历史活动年份：{source["campaign_year"]}；当前链接可能为存档上传。')
        if r["observation"].get("frame_spotcheck"):
            times = r["observation"]["frame_spotcheck"]["sampled_times_seconds"]
            lines.append('- 实际文件 ' + f'{media["duration_seconds"]:.3f} 秒；抽查时刻（秒）：' + ' / '.join(str(t) for t in times) + '。')
        traffic = r["metrics"]["traffic"]
        if traffic:
            counts = "；".join(f'{label} {traffic[field]:,}' for field, label in [('views','浏览'),('likes','赞'),('bookmarks','收藏'),('replies','回复')] if traffic.get(field) is not None)
            lines.append('- X帖子互动快照：' + counts + '。来源为公开帖子元数据（FxTwitter），成交未知。')
        else:
            lines.append('- 本轮未取得同口径的互动快照，成交未知。')
    return "\n".join(lines) + "\n"


def prompt_kind(record):
    prompt = record["prompt"]
    if prompt["status"] == "original_excerpt":
        return {"video": "作者视频提示词", "storyboard_image": "作者分镜图提示词",
                "image": "作者场景生图提示词"}[prompt["stage"]]
    return "未取得生成提示词原文"


def markdown_cell(value):
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def from_repository_root(url, prefix="../../"):
    return url if urlsplit(url).scheme or url.startswith("#") else prefix + url


def render_curated(records, root):
    selected = sorted((r for r in records if r.get("curation")), key=lambda r: r["curation"]["position"])
    stages = Counter(r["prompt"].get("stage", "unknown") for r in selected if r["prompt"]["status"] == "original_excerpt")
    reused = sum(r["curation"].get("reused_analysis", False) for r in selected)
    minutes = sum(r["media"]["duration_seconds"] for r in selected) / 60
    frames = sum(r["observation"]["visual_review"]["sampled_frames"] for r in selected)
    groups = {category: [r for r in selected if r["category"] == category] for category in CATEGORIES}
    index = ["# 精选100 · 创意带货视频动作与换品手册", "",
             f"从仓库现有案例中精选{len(selected)}条，按创意看点、商品接入、原片可核验性和作者提示词可得性选择。按提示词可得性优先安排阅读顺序，不是跨平台互动或成交排行榜。", "",
             f"已取得作者视频提示词{stages['video']}条、分镜图提示词{stages['storyboard_image']}条、场景生图提示词{stages['image']}条。其余保留查询范围和缺口，不把本库拆解或广告对白冒充生成提示词。", "",
             f"覆盖当前完整版本合计约{minutes:.1f}分钟、逐秒画面{frames:,}张。本轮新增{len(selected)-reused}条全片工具分析与画面复核，另{reused}条复用此前同一原片的详解及文件指纹。", "",
             "**核看方式：** 视频工具分析完整原片，再以1fps顺序复核开场至片尾，动作和时间码按实际文件修正。没有标成人工连续视听；声音仅工具辅助识别，未独立连续听验。时间区间约1秒精度，选中后需再确认切点与接触时刻。", "",
             "每条有实际动作、适合商品及原因、换品步骤、一个改编例子、提示词来源和制作缺口。标签区分剧情创意、商品展示技法、条件参考；商品适配是本库判断，尚未转深度或试生成。", "",
             "[全部作品双列预览](../README.md#全部作品预览) · [创意机制索引](INDEX.md) · [检索方法](../docs/reference-library.md) · [结构化数据](../data/references.json)", "",
             "## 按商品找参考", "", "| 商品方向 | 数量 | 动作与换品详解 |", "| --- | --- | --- |"]
    for category, group in groups.items():
        if group:
            slug = CATEGORY_SLUGS[category]
            index.append(f'| {category} | {len(group)} | [{category}详解](curated-100/{slug}.md) |')
    index.extend(["", "## 全部精选 · 封面点击看原片", "", "| 预览 | 案例与入选理由 | 适合商品 | 提示词 |", "| --- | --- | --- | --- |"])
    for r in selected:
        c = r["curation"]
        detail = c["report"].removeprefix("references/")
        poster = r["media"]["poster"]
        preview = f'<a href="{escape(r["media"]["watch_url"], quote=True)}"><img src="{escape(from_repository_root(poster, "../"), quote=True)}" width="120" alt="作品封面"></a>' if poster else "封面待补"
        products = "、".join(x for group in r["transfer"]["suitable_products"] for x in group["examples"])
        prompt = f'[{prompt_kind(r)}]({r["prompt"]["url"]})' if r["prompt"]["status"] == "original_excerpt" else prompt_kind(r)
        index.append(f'| {preview} | **{c["position"]:03d} · [{markdown_cell(r["title"])}]({detail})**<br>{markdown_cell(c["lens"])}<br>{markdown_cell(c["reason"])} | {markdown_cell(products)} | {prompt} |')
    outputs = {root / CURATED_INDEX: "\n".join(index) + "\n"}
    landing = ["# 精选100 · 按商品阅读详解", "", "[选择入口与核看方法](../2026-11-06-curated-100.md)", ""]
    for category, group in groups.items():
        if not group:
            continue
        slug = CATEGORY_SLUGS[category]
        landing.append(f'- [{category}（{len(group)}）]({slug}.md)')
        lines = [f"# {category} · 精选动作与商品替换", "",
                 "[精选100总览](../2026-11-06-curated-100.md) · [全部作品预览](../../README.md#全部作品预览)", "",
                 "全片工具分析＋1fps顺序画面复核，约1秒定位精度；声音未独立连续听验。商品适配与例子为本库判断，未转深度或试生成。", ""]
        lines.extend(f'- [{r["curation"]["position"]:03d} · {r["title"]}](#{r["id"]}) · {prompt_kind(r)}' for r in group)
        for r in group:
            c, media, transfer, review = r["curation"], r["media"], r["transfer"], r["review"]
            lines.extend(["", f'<a id="{r["id"]}"></a>', "", f'## {c["position"]:03d} · {r["title"]}', "",
                          f'**{c["lens"]} · {media["duration_seconds"]:.3f}秒 · {media["aspect_ratio"]}**', ""])
            if r["source"].get("model_as_reported"):
                lines.extend(["模型/工具自述：" + r["source"]["model_as_reported"] + "；未独立验证底层模型。", ""])
            if media["poster"]:
                lines.extend([f'[![作品封面]({from_repository_root(media["poster"])})]({media["watch_url"]})', ""])
            lines.extend([" · ".join(f'[{link["label"]}]({from_repository_root(link["url"])})' for link in r["links"]), "",
                          "**为什么选** " + c["reason"], "", "**实际内容** " + r["creative"]["summary"], "",
                          "**开场钩子** " + r["creative"]["hook"], "", "**结尾回报** " + r["creative"]["payoff"], "",
                          "### 动作拆解", "", "原道具：" + r["actions"]["original_prop"], "",
                          "| 约略区间 | 画面与动作 |", "| --- | --- |"])
            for step in r["actions"]["sequence"]:
                seconds = int(step["start_seconds"])
                if canonical_url(media["watch_url"]).startswith("youtube:"):
                    target = media["watch_url"] + ("&" if "?" in media["watch_url"] else "?") + f"t={seconds}s"
                else:
                    target = (media["direct_video_url"] or media["watch_url"]).split("#")[0] + f"#t={seconds}"
                interval = f'{timestamp(seconds)}–{timestamp(step["end_seconds"])}'
                lines.append(f'| [{interval}]({target}) | {markdown_cell(step["description"])} |')
            lines.extend(["", "### 适合什么商品", ""])
            for fit in transfer["suitable_products"]:
                lines.append(f'- **{"、".join(fit["examples"])}**：{fit["fit_reason"]}')
            lines.extend(["", "### 怎么替换商品", ""])
            lines.extend(f'{i}. {step}' for i, step in enumerate(transfer["replacement_steps"], 1))
            example = transfer["example"]
            lines.extend(["", f'**改编例子 · {example["product"]}** {example["preserve"]}{example["replace"]}', "",
                          "### 提示词与制作判断", "", "**" + prompt_kind(r) + "**", ""])
            prompt = r["prompt"]
            if prompt["status"] == "original_excerpt":
                lines.extend([f'[作者公开原文]({prompt["url"]})。数据只保留短摘录；以下中文写法为本库整理。', "",
                              prompt.get("summary", "公开正文见原帖；不把本库改编例子当原作者指令。"), ""])
            else:
                lines.extend([prompt.get("scope") or prompt.get("check_scope") or "已查所列来源，未取得作者生成提示词；不推测广告是否AI制作。", ""])
            lines.extend(["**换品与深度参考缺口**", ""])
            lines.extend('- ' + text for text in dict.fromkeys([*transfer["constraints"], *r["depth"]["gaps"]]))
            lines.extend(["",
                          "**声音依赖（工具辅助）** " + "".join(review["sound_dependencies"]), "",
                          "<details>", "<summary>版本与核看记录</summary>", "",
                          review["version_note"], ""])
            visual = r["observation"]["visual_review"]
            lines.extend([f'- 观察：全片工具分析，1fps顺序复核{visual["sampled_frames"]}张；全时长覆盖0–{media["duration_seconds"]:.3f}秒。',
                          f'- 当前文件：{visual["width"]}×{visual["height"]}；SHA-256 `{visual["file_sha256"]}`。',
                          f'- {"复用此前同一原片分析及指纹" if c["reused_analysis"] else "本轮新增全片分析与画面复核"}；记录日期：{review["date"]}。',
                          '- 原帖账号/上传者：' + str(r["source"]["creator"]) + '；不把上传者自动认作原创署名。',
                          '- 深度与生成：未测试；互动不当成交。', "", "</details>", ""])
        outputs[root / f"references/curated-100/{slug}.md"] = "\n".join(lines)
    outputs[root / "references/curated-100/README.md"] = "\n".join(landing) + "\n"
    return outputs


def render_reviews(records):
    reviewed = [r for r in records if r.get("review", {}).get("status") == "analyzed"
                and r["review"].get("report", "").startswith(REVIEW_REPORT + "#")]
    lines = ["# 优先 20 条创意参考 · 动作拆解与商品替换", "", "更新于 2026-11-06。由 data/references.json 生成。", "",
             "本轮逐条调用视频分镜工具分析完整链接，再读取同一原片文件，以 1fps 从开场到片尾顺序复核画面。工具部分时间码有误，以下按实际片长和逐秒画面重排，约 1 秒精度，不能直接当剪辑切点。", "",
             "观察方式保留为 `frames`，并记录全时长覆盖、采样数量与文件指纹。声音仅为工具辅助识别，未独立连续听验；没有把它标成人工连续视听验收。适用商品与替换步骤是本库的创意判断，尚未转换深度或试生成。", "",
             "本轮已查作品公开简介及文末所列剧情/制作来源，未发现这 20 条的原作者生成提示词。广告对白与公开广告脚本分别记录，不能当作生成提示词；其他未查来源中是否存在提示词仍未知。", "",
             "[全部作品预览](../README.md#全部作品预览) · [机制索引](INDEX.md) · [完整数据](../data/references.json)", "",
             "## 按商品快速选片", "", "| 参考 | 适合商品 | 使用判断 |", "| --- | --- | --- |"]
    for r in reviewed:
        examples = "、".join(x for group in r["transfer"]["suitable_products"] for x in group["examples"])
        lines.append(f'| [{r["title"]}](#{r["id"]}) | {examples} | {r["review"]["recommendation"]} |')
    for r in reviewed:
        obs, transfer, review = r["observation"], r["transfer"], r["review"]
        lines.extend(["", f'<a id="{r["id"]}"></a>', "", f'## {r["id"]} · {r["title"]}', "",
                      f'**{r["metadata"]}**', "", f'[![作品封面]({r["media"]["poster"]})]({r["media"]["watch_url"]})', "",
                      f'[播放原片]({r["media"]["watch_url"]}) · [剧情/制作来源]({r["source"]["description_url"]})', "",
                      "**版本与观察范围** " + review["version_note"], "",
                      f'实际文件 {r["media"]["duration_seconds"]:.3f} 秒；全片工具分析，另以 1fps 复核 {obs["visual_review"]["sampled_frames"]} 帧。声音未独立连续听验。', "",
                      "**开场钩子** " + r["creative"]["hook"], "", "**结尾回报** " + r["creative"]["payoff"], "",
                      "**使用判断** " + review["recommendation"], "", "### 动作拆解", "",
                      f'原道具：{r["actions"]["original_prop"]}。', "",
                      "| 约略区间 | 画面与动作 | 创意作用 |", "| --- | --- | --- |"])
        for step in r["actions"]["sequence"]:
            seconds = int(step["start_seconds"])
            url = r["media"]["watch_url"] + f"&t={seconds}s"
            time = f'{timestamp(seconds)}–{timestamp(step["end_seconds"])}'
            lines.append(f'| [{time}]({url}) | {step["description"]} | {step["creative_role"]} |')
        lines.extend(["", "### 适合什么商品", ""])
        for group in transfer["suitable_products"]:
            lines.append(f'- **{group["category"]}**：{"、".join(group["examples"])}。{group["fit_reason"]}')
        lines.extend(["", "### 怎么替换商品", ""])
        for i, step in enumerate(transfer["replacement_steps"], 1):
            lines.append(f"{i}. {step}")
        example = transfer["example"]
        lines.extend(["", f'**具体例子 · {example["product"]}** {example["preserve"]}{example["replace"]}', "",
                      "**使用限制**", ""])
        lines.extend("- " + item for item in transfer["constraints"])
        lines.extend(["", "### 深度参考时需要保留和另做的部分", "",
                      "- 可借动作：" + "；".join(r["depth"]["preserves"]) + "。",
                      "- 缺口：" + "；".join(r["depth"]["gaps"]) + "。",
                      "- 声音依赖：" + "".join(review["sound_dependencies"]),
                      "- " + r["depth"]["notes"], "", "### 原作者提示词与来源", "",
                      "本次已查来源未发现公开的生成提示词；原文为空，未用本库的动作分析或适配例子代填。", ""])
        if r["prompt"].get("related_script_url"):
            lines.extend([f'[公开广告脚本与制作署名]({r["prompt"]["related_script_url"]})；这是广告脚本，不是生成提示词，未复制全文。', ""])
        lines.extend(f'- [已查来源 {i}]({url})' for i, url in enumerate(r["prompt"]["checked_sources"], 1))
    return "\n".join(lines) + "\n"


def render(records, root=ROOT, check=False):
    readme = root / "README.md"
    current = readme.read_text(encoding="utf-8")
    intro = """# AI Video Playbook · 商品创意视频参考库

为商品创意选片积累原片、观看依据、动作与跨品类联想。面向 TikTok 商品，也收录其他平台和品牌广告的创意参考。

[精选100 · 动作与换品详解](references/2026-11-06-curated-100.md) · [全部作品预览](#全部作品预览) · [创意机制索引](references/INDEX.md) · [最新收录100条](references/2026-11-06-creative-commerce-100.md) · [收录与检索](docs/reference-library.md)

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
             "点击封面观看作品。卡片区分来源说明、抽帧和观看记录；提示词类型分别标注视频、分镜图与生图，中文要点为本库整理，原文见作者链接。具体商品能否替换，需要在使用时核对。", "",
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
            case = f'{record["id"]} · {title}'
            if record.get("curation"):
                case = f'[{case}]({record["curation"]["report"].removeprefix("references/")})'
            elif record.get("review", {}).get("status") == "analyzed":
                case = f'[{case}]({Path(REVIEW_REPORT).name}#{record["id"]})'
            elif record["collection"] == "2026-11-06":
                case = f'[{case}]({Path(NEW_BATCH_REPORT).name}#{record["id"]})'
            index.append(f'| {case} | {record["category"]} | {observation_label(record)} | [来源]({record["source"]["url"]}) |')
        index.append("")
    outputs[root / "references/INDEX.md"] = "\n".join(index)
    batch = [record for record in records if record["collection"] == "2026-11-05"]
    report = ["# 新增 100 条创意商品视频参考 · 2026-11-05", "",
              "本批按具体创意机制筛选，包含品牌广告和历史作品。原100条中的优先20条已于2026-11-06补全片工具分析、逐秒画面复核与换品方案，其余仍为来源说明级线索。所有案例均未验证深度复刻，商品接入需要按具体实物核对。", "",
              "[全部封面预览](../README.md#全部作品预览) · [创意机制索引](INDEX.md) · [完整结构化数据](../data/references.json)", ""]
    report.extend(["## 优先 20 条 · 分析入口", "", "已补动作拆解、适用商品与替换步骤；声音未独立连续听验。详情见[20条分析](2026-11-06-priority-20-analysis.md)。", ""])
    for record in batch:
        if record.get("review_priority") == "first_20":
            target = f'{Path(REVIEW_REPORT).name}#{record["id"]}' if record.get("review") else record["source"]["url"]
            report.append(f'- [{record["title"]}]({target}) · {record["id"]}')
    report.append("")
    for record in batch:
        detail = []
        if record.get("review", {}).get("status") == "analyzed":
            detail = [f'[动作拆解、适用商品与替换步骤]({Path(REVIEW_REPORT).name}#{record["id"]}) · {observation_label(record)}', ""]
        report.extend([f'## {record["id"]} · {record["title"]}', "",
                       f'**{record["category"]} · {" / ".join(record["creative"]["mechanisms"])}**', "",
                       record["creative"]["summary"], "",
                       *detail,
                       "**接入假设** " + "".join(record["transfer"]["hypotheses"]), "",
                       "**待核实** " + "".join(record["transfer"]["constraints"]), "",
                       " · ".join(f'[{item["label"]}]({item["url"]})' for item in record["links"]), ""])
    outputs[root / "references/2026-11-05-creative-commerce-100.md"] = "\n".join(report)
    outputs[root / REVIEW_REPORT] = render_reviews(records)
    outputs[root / NEW_BATCH_REPORT] = render_new_batch(records)
    outputs.update(render_curated(records, root))
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
    parser.add_argument("--curated", action="store_true", help="Search only the reviewed curated selection")
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
        matches = search(records, args.query, args.category, args.mechanism, args.collection, args.curated)[:args.limit]
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
