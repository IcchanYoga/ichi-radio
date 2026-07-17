# -*- coding: utf-8 -*-
"""episodes.json から feed.xml (RSS 2.0 + itunes) と index.html を生成する。

使い方:
    python scripts/build_feed.py
    python scripts/build_feed.py --include-future  # 時限フィルタを無効化

- enclosure の length は audio/ 内の実ファイルのバイト数から自動計算
- itunes:duration は duration_seconds から HH:MM:SS に変換
- 生成後に xml.etree で feed.xml をパースし、整形式であることを検証する
- 既定では pubDate が現在時刻(JST)より未来のエピソードを feed.xml / index.html
  から除外する(時限公開)。pubDate を解析できないエピソードは、既存エピソード
  を誤って落とさないよう安全側に倒して「公開済み」として含め、警告を標準エラー
  へ出す。--include-future を付けるとこのフィルタを無効化し、全件を出力する。
"""
import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent


def itunes(tag: str) -> str:
    return f"{{{ITUNES_NS}}}{tag}"


def hms(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def load_data() -> dict:
    with open(ROOT / "episodes.json", encoding="utf-8-sig") as f:
        return json.load(f)


def filter_published_episodes(episodes: list, now: datetime) -> list:
    """pubDate が now より未来のエピソードを除いた一覧を返す(時限公開フィルタ)。

    pubDate を解析できない、またはタイムゾーン情報が無いエピソードは、
    既存エピソードを絶対に落とさない安全側の方針として除外せず含め、
    その旨を警告として標準エラーへ出す。
    """
    published = []
    for ep in episodes:
        pub_date = ep.get("pubDate", "")
        try:
            parsed = parsedate_to_datetime(pub_date)
        except (TypeError, ValueError, IndexError):
            parsed = None
        if parsed is None:
            print(
                f"WARNING: pubDateを解析できないため公開済み扱いで含めます: "
                f"guid={ep.get('guid', '?')} pubDate={pub_date!r}",
                file=sys.stderr,
            )
            published.append(ep)
            continue
        if parsed.tzinfo is None:
            print(
                f"WARNING: pubDateにタイムゾーン情報が無いため公開済み扱いで含めます: "
                f"guid={ep.get('guid', '?')} pubDate={pub_date!r}",
                file=sys.stderr,
            )
            published.append(ep)
            continue
        if parsed <= now:
            published.append(ep)
    return published


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="episodes.json から feed.xml と index.html を生成する"
    )
    parser.add_argument(
        "--include-future",
        action="store_true",
        help="pubDateが未来のエピソードも含めて生成する(時限フィルタを無効化)",
    )
    return parser.parse_args(argv)


def build_feed(data: dict) -> None:
    show = data["show"]
    base = show["link"].rstrip("/")

    ET.register_namespace("itunes", ITUNES_NS)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = show["title"]
    ET.SubElement(channel, "link").text = show["link"]
    ET.SubElement(channel, "language").text = show["language"]
    ET.SubElement(channel, "description").text = show["description"]
    ET.SubElement(channel, itunes("author")).text = show["author"]
    owner = ET.SubElement(channel, itunes("owner"))
    ET.SubElement(owner, itunes("name")).text = show["owner_name"]
    ET.SubElement(owner, itunes("email")).text = show["owner_email"]
    ET.SubElement(channel, itunes("image"), {"href": show["image"]})
    category = ET.SubElement(channel, itunes("category"), {"text": show["category"]})
    ET.SubElement(category, itunes("category"), {"text": show["subcategory"]})
    ET.SubElement(channel, itunes("explicit")).text = show["explicit"]

    for ep in data["episodes"]:
        audio_path = ROOT / "audio" / ep["audio"]
        if not audio_path.is_file():
            sys.exit(f"ERROR: audio file not found: {audio_path}")
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = ep["title"]
        ET.SubElement(item, "description").text = ep["description"]
        ET.SubElement(item, "enclosure", {
            "url": f"{base}/audio/{ep['audio']}",
            "type": "audio/mp4",
            "length": str(audio_path.stat().st_size),
        })
        guid = ET.SubElement(item, "guid", {"isPermaLink": "false"})
        guid.text = ep["guid"]
        ET.SubElement(item, "pubDate").text = ep["pubDate"]
        ET.SubElement(item, itunes("duration")).text = hms(ep["duration_seconds"])

    ET.indent(rss)
    tree = ET.ElementTree(rss)
    tree.write(ROOT / "feed.xml", encoding="utf-8", xml_declaration=True)


def build_index(data: dict) -> None:
    show = data["show"]
    parts = [
        "<!DOCTYPE html>",
        '<html lang="ja">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(show['title'])}</title>",
        "<style>",
        "body { font-family: sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; line-height: 1.7; }",
        ".description { white-space: pre-wrap; }",
        "article { border-top: 1px solid #ccc; padding: 1.5rem 0; }",
        "audio { width: 100%; margin-top: 0.5rem; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(show['title'])}</h1>",
        f'<p class="description">{html.escape(show["description"])}</p>',
        f'<p><a href="feed.xml">Podcast RSS (feed.xml)</a></p>',
    ]
    for ep in reversed(data["episodes"]):  # 新しい順に表示
        parts += [
            "<article>",
            f"<h2>{html.escape(ep['title'])}</h2>",
            f"<p><small>{html.escape(ep['pubDate'])} / {hms(ep['duration_seconds'])}</small></p>",
            f'<p class="description">{html.escape(ep["description"])}</p>',
            f'<audio controls preload="none" src="audio/{ep["audio"]}"></audio>',
            "</article>",
        ]
    parts += ["</body>", "</html>", ""]
    (ROOT / "index.html").write_text("\n".join(parts), encoding="utf-8")


def validate_feed() -> None:
    tree = ET.parse(ROOT / "feed.xml")  # 整形式でなければ ParseError で落ちる
    items = tree.getroot().findall("./channel/item")
    print(f"feed.xml OK (well-formed, {len(items)} items)")


def main() -> None:
    args = parse_args()
    data = load_data()
    if not args.include_future:
        now = datetime.now(JST)
        data = dict(data)
        data["episodes"] = filter_published_episodes(data["episodes"], now)
    build_feed(data)
    build_index(data)
    validate_feed()
    print("generated: feed.xml, index.html")


if __name__ == "__main__":
    main()
