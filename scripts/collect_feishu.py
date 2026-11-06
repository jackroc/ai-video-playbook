#!/usr/bin/env python3
"""Collect public X/TikTok links from one Feishu group using lark-cli."""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import html
from html.parser import HTMLParser
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

from notify_feishu import notify
import reference_catalog

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".local"
REPO_URL = "git@github.com:jackroc/ai-video-playbook.git"
PUBLIC_URL = "https://github.com/jackroc/ai-video-playbook/blob/main/"
CATALOG_PATHS = ("references/community", "data/references.json", "README.md", "references/INDEX.md",
                 "references/2026-11-05-creative-commerce-100.md",
                 "references/2026-11-06-priority-20-analysis.md",
                 "references/2026-11-06-creative-commerce-100.md",
                 "references/2026-11-06-curated-100.md", "references/curated-100")
HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com",
         "tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com", "v.tiktok.com"}
FETCH_HOSTS = HOSTS | {"publish.twitter.com", "publish.x.com"}
STOP = threading.Event()
LOG = logging.getLogger("collector")


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key in {"FEISHU_WEBHOOK_URL", "FEISHU_CHAT_ID", "LARK_CLI_PATH", "FEISHU_RECEIVE_MODE", "FEISHU_POLL_FROM"}:
                    os.environ.setdefault(key, value.strip())


def accepted_url(value):
    try:
        p = urlsplit(value)
        if p.scheme not in {"https", "http"} or p.hostname not in HOSTS:
            return None
        if p.username or p.password or p.port not in {None, 80, 443}:
            return None
        path = p.path
        host = p.hostname
        if "tiktok.com" in host:
            if re.fullmatch(r"/@[\w.-]+/video/\d+/?", path):
                return "https://www.tiktok.com" + path.rstrip("/")
            if host in {"vm.tiktok.com", "vt.tiktok.com", "v.tiktok.com"} and re.fullmatch(r"/[A-Za-z0-9]+/?", path):
                return "https://" + host + path
            if re.fullmatch(r"/t/[A-Za-z0-9]+/?", path):
                return "https://www.tiktok.com" + path
            return None
        m = re.fullmatch(r"/([A-Za-z0-9_]+|i/web)/status/(\d+)(?:/(?:video|photo)/\d+)?/?", path)
        if m:
            return "https://x.com/" + m.group(1) + "/status/" + m.group(2)
    except ValueError:
        pass
    return None


def links_in(text):
    result = []
    for value in re.findall(r"https?://[^\s<>\[\]{}\"']+", text):
        value = value.rstrip(".,;:!?，。；：！？）)】")
        url = accepted_url(value)
        if url and url not in result:
            result.append(url)
    return result[:10]


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urlsplit(newurl)
        if p.scheme != "https" or p.hostname not in FETCH_HOSTS or p.username or p.password:
            raise ValueError("Disallowed redirect")
        if p.port not in {None, 443}:
            raise ValueError("Disallowed redirect port")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get_public(url, prefix=False):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in FETCH_HOSTS:
        raise ValueError("Disallowed endpoint")
    req = Request(url, headers={"User-Agent": "AI-Video-Playbook/1.0", "Accept": "application/json,text/html"})
    with build_opener(SafeRedirect()).open(req, timeout=15) as response:
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024 and not prefix:
            raise ValueError("Response too large")
        return response.geturl(), data.decode("utf-8", errors="replace")


class PostText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.depth = 0
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignore += 1
        if tag == "p":
            self.depth += 1
        if tag == "br" and self.depth:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.ignore = max(0, self.ignore - 1)
        if tag == "p":
            self.depth = max(0, self.depth - 1)
            self.parts.append("\n")

    def handle_data(self, value):
        if self.depth and not self.ignore:
            self.parts.append(value)


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = {}

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            fields = dict(attrs)
            name = fields.get("property") or fields.get("name")
            if name in {"og:description", "description"} and fields.get("content"):
                self.tags[name] = fields["content"]


def metadata(url):
    original = url
    try:
        if "/status/" not in url and not re.search(r"/video/\d+$", url):
            final, _ = get_public(url, prefix=True)
            url = accepted_url(final)
            if not url or not re.search(r"/video/\d+$", url):
                raise ValueError("Could not resolve public video link")
        provider = "X" if "/status/" in url else "TikTok"
        endpoint = "https://publish.x.com/oembed" if provider == "X" else "https://www.tiktok.com/oembed"
        params = {"url": url}
        if provider == "X":
            params.update(omit_script="true", hide_thread="true", dnt="true")
        _, payload = get_public(endpoint + "?" + urlencode(params))
        data = json.loads(payload)
        parser = PostText()
        parser.feed(str(data.get("html", "")))
        text = str(data.get("title") or "".join(parser.parts)).strip()[:12000]
        author = str(data.get("author_name") or "")[:200]
        access = "已读取公开嵌入信息" if text else "已获取嵌入信息，正文待补"
        if provider == "TikTok":
            author = author or urlsplit(url).path.split("/")[1]
            if not text:
                try:
                    _, page = get_public(url, prefix=True)
                    meta = PageMetadata()
                    meta.feed(page)
                    desc = meta.tags.get("og:description") or meta.tags.get("description", "")
                    if desc and "make your day" not in desc.lower():
                        text = desc.strip()[:12000]
                        access = "已读取公开页面描述"
                except Exception:
                    pass
        return {"url": url, "platform": provider, "author": author, "text": text, "access": access}
    except Exception:
        # Fail closed and preserve the link; never publish exception URLs or group content.
        return {"url": url or original, "platform": "X" if "/status/" in original else "TikTok",
                "author": "", "text": "", "access": "待补：公开接口未返回可用正文"}


def classify(text):
    text = text.lower()
    rules = [("ugc", ("ugc", "口播", "用户生成")),
             ("comedy", ("comedy", "funny", "搞笑", "反转", "幽默")),
             ("product-demo", ("product demo", "商品演示", "带货", "product video")),
             ("cinematic", ("cinematic", "电影感", "电影级")),
             ("transition", ("transition", "转场"))]
    return [category for category, words in rules if any(word in text for word in words)] or ["inbox"]


def prompt_from(text):
    match = re.search(r"(?:^|\n|[.!?。！？]\s+)\s*(?:prompt|提示词)\s*[:：]\s*(.+)", text, re.I | re.S)
    return match.group(1).strip() if match else ""


def post_key(url):
    m = re.search(r"/(status|video)/(\d+)", url)
    if m:
        return ("x-" if m.group(1) == "status" else "tiktok-") + m.group(2)
    return "tiktok-short-" + hashlib.sha256(url.encode()).hexdigest()[:16]


def quote(value):
    return "\n".join("> " + html.escape(line) for line in value.splitlines())


def render(data):
    tags = classify(data["text"])
    prompt = prompt_from(data["text"])
    title = data["text"].splitlines()[0][:100] if data["text"] else post_key(data["url"])
    title = html.escape(title.replace("#", ""))
    models = list(dict.fromkeys(re.findall(r"\b(?:Seedance|Kling|Sora|Veo|Runway|Hailuo)(?:\s*\d+(?:\.\d+)?)?\b|可灵|海螺", data["text"], re.I)))
    return f"""# {title}

- 来源：[{data['platform']} 原帖与成品]({data['url']})
- 作者：{html.escape(data['author']) or '待补'}
- 收录日期：{datetime.now(timezone.utc).date().isoformat()}
- 分类：{' / '.join(tags)}（规则初分，待复核）
- 原帖提及模型：{' / '.join(models) or '待补'}
- 获取情况：{data['access']}
- 验证状态：外部分享，未自行复现；带货效果未测
- 观察范围：仅公开嵌入信息或页面描述，尚未观看或分析视频画面

## 原帖公开文字

{quote(data['text']) if data['text'] else '待补。可访问原帖补充提示词或公开截图。'}

## 提示词

{quote(prompt) if prompt else '待补：公开正文中未识别到明确标注的提示词。'}

提示词识别仅依据原帖中的 Prompt / 提示词标记；嵌入内容可能截断，完整性待核实。模型版本、生成参数、输入素材和后期流程均需按原作者资料补齐，不从成片反推。

## 复用与实测

待人工补充创意机制、适用商品与复现记录。成品保留原帖链接，未自动下载或转载视频。
"""


def index_files(repo):
    base = repo / "references/community"
    rows = []
    for p in sorted(base.glob("*/*.md")):
        heading = p.read_text().splitlines()[0].removeprefix("# ").replace("|", " ").replace("[", " ").replace("]", " ")
        rows.append(f"| [{heading}]({p.relative_to(base).as_posix()}) | {p.parent.name} | 外部案例，未复现 |")
    (base / "README.md").write_text(
        "# 群分享自动收录\n\n仅保存指定收录群分享链接对应的公开资料。规则分类待复核；缺失信息标记待补。详见[接入说明](../../docs/feishu-collection.md)。\n\n"
        "| 案例 | 初步分类 | 状态 |\n| --- | --- | --- |\n" + "\n".join(rows) + "\n", encoding="utf-8")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=90).stdout.strip()


def prepare_repo(repo):
    if not (repo / ".git").exists():
        subprocess.run(["git", "clone", REPO_URL, str(repo)], check=True, capture_output=True, timeout=120)
    for key in ("user.name", "user.email"):
        git(repo, "config", key, git(ROOT, "config", key))
    if git(repo, "remote", "get-url", "origin") != REPO_URL:
        raise RuntimeError("Unexpected collection repository origin")
    if git(repo, "status", "--porcelain"):
        # A previous interrupted publish can leave only generated paths dirty.
        dirty = git(repo, "status", "--porcelain").splitlines()
        paths = [row[3:].strip('"') for row in dirty]
        if any(path not in CATALOG_PATHS and not path.startswith(("references/community/", "references/curated-100/")) for path in paths):
            raise RuntimeError("Unexpected local changes in collection checkout")
        if (repo / reference_catalog.DATA).exists():
            reference_catalog.render(reference_catalog.load(repo), repo)
        git(repo, "add", "--", *CATALOG_PATHS)
        git(repo, "commit", "-m", "docs: recover interrupted community collection")
    # Push an interrupted prior commit before pulling; reject divergence for manual recovery.
    if git(repo, "rev-list", "--count", "origin/main..HEAD") != "0":
        git(repo, "push", "origin", "HEAD:main")
    git(repo, "pull", "--ff-only", "origin", "main")


def publish(repo, data):
    prepare_repo(repo)
    data = dict(data, prompt=prompt_from(data["text"]))
    key = post_key(data["url"])
    existing = list((repo / "references/community").glob("*/" + key + ".md"))
    if existing:
        if reference_catalog.upsert_community(repo, data, key):
            git(repo, "add", "--", *CATALOG_PATHS)
            git(repo, "commit", "-m", "docs: index public video reference " + key)
            git(repo, "push", "origin", "HEAD:main")
        return PUBLIC_URL + existing[0].relative_to(repo).as_posix()
    category = classify(data["text"])[0]
    path = repo / "references/community" / category / (key + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(data), encoding="utf-8")
    index_files(repo)
    reference_catalog.upsert_community(repo, data, key)
    git(repo, "add", "--", *CATALOG_PATHS)
    git(repo, "commit", "-m", "docs: collect public video reference " + key)
    git(repo, "push", "origin", "HEAD:main")
    return PUBLIC_URL + path.relative_to(repo).as_posix()


def database():
    db = sqlite3.connect(str(RUNTIME / "queue.sqlite3"), timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS jobs (url TEXT PRIMARY KEY, message_id TEXT, status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0, next_at REAL DEFAULT 0, result TEXT DEFAULT '', notified INTEGER DEFAULT 0)")
    return db


def enqueue(event, target, db):
    if (not isinstance(event, dict) or event.get("chat_id") != target or event.get("sender_type") != "user"
            or event.get("message_type") not in {"text", "post"} or not event.get("message_id")):
        return 0
    count = 0
    for url in links_in(event.get("content", "")):
        cursor = db.execute("INSERT OR IGNORE INTO jobs(url,message_id) VALUES (?,?)", (url, event["message_id"]))
        count += cursor.rowcount
    db.commit()
    return count


def history_event(message, target):
    return {"chat_id": message.get("chat_id") or target, "sender_type": (message.get("sender") or {}).get("sender_type"),
            "message_type": message.get("msg_type"), "message_id": message.get("message_id"),
            "content": "" if message.get("deleted") else message.get("content") or ""}


def poll_group(target, cli):
    db = database()
    db.execute("CREATE TABLE IF NOT EXISTS receiver_state (chat_id TEXT PRIMARY KEY, first_at INTEGER, through_at INTEGER)")
    row = db.execute("SELECT first_at,through_at FROM receiver_state WHERE chat_id=?", (target,)).fetchone()
    if row:
        first, through = row
    else:
        first = through = int(os.environ.get("FEISHU_POLL_FROM") or time.time())
        db.execute("INSERT INTO receiver_state VALUES (?,?,?)", (target, first, through))
        db.commit()

    def iso(value):
        return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")

    ready = False
    span = 900
    try:
        while not STOP.is_set():
            end = min(int(time.time()) - 2, through + span)
            if end <= through:
                STOP.wait(5)
                continue
            try:
                result = subprocess.run([cli, "im", "+chat-messages-list", "--as", "user", "--chat-id", target,
                                         "--start", iso(max(first, through - 30)), "--end", iso(end),
                                         "--order", "asc", "--page-size", "50", "--page-all", "--page-limit", "10",
                                         "--no-reactions", "--format", "json"], capture_output=True, text=True, timeout=60)
                if result.returncode:
                    raise RuntimeError(f"lark-cli exit {result.returncode}")
                page = json.loads(result.stdout)
                if page.get("ok") is not True:
                    raise RuntimeError("unsuccessful group history response")
                if page.get("data", {}).get("has_more") or page.get("meta", {}).get("pagination", {}).get("complete") is False:
                    span = max(10, span // 2)
                    raise RuntimeError("incomplete page; cursor held")
                seen = queued = 0
                for message in page.get("data", {}).get("messages") or []:
                    event = history_event(message, target)
                    if event["chat_id"] == target and event["sender_type"] == "user" and event["message_type"] in {"text", "post"}:
                        seen += len(links_in(event["content"]))
                    queued += enqueue(event, target, db)
                db.execute("UPDATE receiver_state SET through_at=? WHERE chat_id=?", (end, target))
                db.commit()
                through = end
                span = 900
                if not ready:
                    ready = True
                    (RUNTIME / "receiver-ready").write_text(datetime.now(timezone.utc).isoformat())
                    LOG.info("Group polling ready using existing user authorization; recognized %d link(s), queued %d", seen, queued)
                elif queued:
                    LOG.info("Queued %d public link(s) from the approved group", queued)
            except Exception as exc:
                ready = False
                (RUNTIME / "receiver-ready").unlink(missing_ok=True)
                LOG.error("Group polling unavailable (%s); cursor retained", type(exc).__name__)
                STOP.wait(25)
                continue
            STOP.wait(20 if end >= int(time.time()) - 5 else 1)
    finally:
        db.close()
        (RUNTIME / "receiver-ready").unlink(missing_ok=True)


def receive(target, cli):
    jq = 'select(.chat_id=="' + target + '" and .sender_type=="user")'
    while not STOP.is_set():
        proc = subprocess.Popen([cli, "event", "consume", "im.message.receive_v1", "--as", "bot", "--timeout", "1h", "--jq", jq],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        def diagnostics():
            for line in proc.stderr:
                if "ready event_key=" in line or "feishu-websocket: connected" in line:
                    LOG.info(line.strip())
                    if "ready event_key=" in line:
                        (RUNTIME / "receiver-ready").write_text(datetime.now(timezone.utc).isoformat())
                elif "WARN" in line or "error" in line.lower():
                    LOG.error("Receiver diagnostic reported an error; inspect lark-cli configuration")

        thread = threading.Thread(target=diagnostics, daemon=True)
        thread.start()

        def stop_on_signal():
            while proc.poll() is None:
                if STOP.wait(0.25):
                    try:
                        proc.terminate()
                    except ProcessLookupError:
                        pass
                    break

        threading.Thread(target=stop_on_signal, daemon=True).start()
        db = database()
        try:
            for line in proc.stdout:
                if STOP.is_set():
                    break
                try:
                    n = enqueue(json.loads(line), target, db)
                    if n:
                        LOG.info("Queued %d public link(s)", n)
                except (ValueError, TypeError):
                    LOG.warning("Ignored malformed event")
        finally:
            db.close()
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=20)
            (RUNTIME / "receiver-ready").unlink(missing_ok=True)
        if not STOP.is_set():
            LOG.warning("Receiver disconnected (exit %s); reconnecting", proc.returncode)
            STOP.wait(10)


def work():
    db = database()
    repo = RUNTIME / "collection-repo"
    while not STOP.is_set():
        row = db.execute("SELECT url,attempts FROM jobs WHERE status='pending' AND next_at<=? ORDER BY rowid LIMIT 1", (time.time(),)).fetchone()
        if row:
            url, attempts = row
            try:
                data = metadata(url)
                result = publish(repo, data)
                db.execute("UPDATE jobs SET status='done',result=? WHERE url=?", (json.dumps({"link": result, "access": data["access"], "tags": classify(data["text"])}), url))
                db.commit()
                LOG.info("Published %s", post_key(data["url"]))
            except Exception as exc:
                # Never log exception text: network exceptions can contain credentials/URLs.
                db.execute("UPDATE jobs SET attempts=?,next_at=?,status=? WHERE url=?",
                           (attempts + 1, time.time() + min(600, 15 * 2 ** attempts), "failed" if attempts >= 4 else "pending", url))
                db.commit()
                LOG.error("Collection failed (%s); retry is bounded and input is retained", type(exc).__name__)
        for url, raw in db.execute("SELECT url,result FROM jobs WHERE status='done' AND notified=0 LIMIT 1").fetchall():
            data = json.loads(raw)
            try:
                notify("AI 视频方案库已收录（外部案例，未复现）\n分类：" + "/".join(data["tags"]) + "\n" + data["access"] + "\n" + data["link"])
                db.execute("UPDATE jobs SET notified=1 WHERE url=?", (url,))
                db.commit()
            except Exception:
                LOG.warning("Notification pending; repository entry has already been saved")
                STOP.wait(30)
        STOP.wait(1)
    db.close()


def run():
    load_env()
    target = os.environ.get("FEISHU_CHAT_ID", "")
    if not re.fullmatch(r"oc_[a-zA-Z0-9]+", target):
        raise SystemExit("Set FEISHU_CHAT_ID for exactly one approved collection group")
    cli = os.environ.get("LARK_CLI_PATH") or shutil.which("lark-cli")
    if not cli:
        raise SystemExit("lark-cli not found")
    mode = os.environ.get("FEISHU_RECEIVE_MODE", "bot-events")
    if mode not in {"bot-events", "user-poll"}:
        raise SystemExit("FEISHU_RECEIVE_MODE must be bot-events or user-poll")
    os.umask(0o077)
    RUNTIME.mkdir(exist_ok=True)
    lock = (RUNTIME / "collector.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Collector is already running")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    (RUNTIME / "collector.pid").write_text(str(os.getpid()))
    (RUNTIME / "receiver-ready").unlink(missing_ok=True)
    thread = threading.Thread(target=poll_group if mode == "user-poll" else receive, args=(target, cli), daemon=True)
    thread.start()
    LOG.info("Collector started for one configured group; public links only")
    try:
        work()
    finally:
        STOP.set()
        thread.join(timeout=8)
        (RUNTIME / "collector.pid").unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "preview"])
    parser.add_argument("--url")
    args = parser.parse_args()
    if args.command == "preview":
        url = accepted_url(args.url or "")
        if not url:
            raise SystemExit("Provide a public X status or TikTok video URL")
        print(render(metadata(url)))
    else:
        run()


if __name__ == "__main__":
    main()
