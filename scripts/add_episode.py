"""エピソードの追加・直しを1本で行う道具(今まで担当が毎回 add_epNNN.py / upd_epNNN.py を書いていた分)。

やること(順番どおり・どれかで失敗したらそこで止まる):
  1) 音声を audio/epNNN.m4a に置く(--audio で元ファイルを渡す。既にあるなら省略)
  2) episodes.json に追記(--update なら同じ guid の行を直す)。guid の連番・重複・題の長さ・pubDate の形を検査
  3) build_feed.py を流して feed.xml と index.html を作り直し、件数を確かめる
  4) --push のときだけ: git add / commit / pull --rebase / 再生成 / push(公開に当たる操作なので既定では行わない)
  5) --desktop のときだけ: stand.fm 用にデスクトップへ ★stand.fm用_<日付>_epNNN.m4a を複製

概要欄(description)は担当が書く。--desc-file に UTF-8 の本文(ハッシュタグとチャプターまで)を置いて渡す。

使い方(cwd=ichi-radio):
  python scripts/add_episode.py 91 --title "題" --desc-file desc.txt --audio "元.m4a" --duration 289 --publish 2026-10-24
  python scripts/add_episode.py 91 --title "題" --desc-file desc.txt --transcript-json "文字起こし.json" --publish 2026-10-24 --push --desktop
  python scripts/add_episode.py 88 --update --desc-file desc.txt        (直す。題・音声・時間・公開日は渡したものだけ置き換える)
--publish は公開日(YYYY-MM-DD)。時刻は決まりの 07:00 +0900 に固定。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EP_JSON = REPO / "episodes.json"
DESKTOP = Path(r"C:\Users\tyura\OneDrive\デスクトップ")
TITLE_MAX = 40  # stand.fm の題は40文字以内(超えると予約ボタンが押せない)
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rfc2822(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return f"{WD[d.weekday()]}, {d.day:02d} {MON[d.month - 1]} {d.year} 07:00:00 +0900"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True, encoding="utf-8", **kw)
    if r.returncode != 0:
        sys.exit(f"失敗: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def build() -> str:
    r = run([sys.executable, "scripts/build_feed.py"])
    ok = [ln for ln in r.stdout.splitlines() if "OK (well-formed" in ln]
    if not ok:
        sys.exit("feed の生成が成功と出なかった: " + r.stdout.strip())
    return ok[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("num", type=int, help="エピソード番号(89 など)")
    ap.add_argument("--title")
    ap.add_argument("--desc-file")
    ap.add_argument("--audio", help="元の音声ファイル(audio/epNNN.m4a に複製)")
    ap.add_argument("--duration", type=float)
    ap.add_argument("--transcript-json", help="文字起こしjson(duration_seconds を読む)")
    ap.add_argument("--publish", help="公開日 YYYY-MM-DD(07:00 +0900)")
    ap.add_argument("--update", action="store_true", help="既にある行を直す")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--desktop", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ep = f"ep{a.num:03d}"
    guid = f"ichi-radio-{ep}"
    data = json.loads(EP_JSON.read_text(encoding="utf-8"))
    eps = data["episodes"]
    row = next((e for e in eps if e["guid"] == guid), None)

    if a.title and len(a.title) > TITLE_MAX:
        sys.exit(f"題が{len(a.title)}文字(上限{TITLE_MAX})")
    desc = None
    if a.desc_file:
        desc = Path(a.desc_file).read_text(encoding="utf-8").strip()
        if not desc:
            sys.exit("概要欄の本文が空")
    duration = a.duration
    if a.transcript_json:
        duration = float(json.loads(Path(a.transcript_json).read_text(encoding="utf-8"))["duration_seconds"])

    audio_dst = REPO / "audio" / f"{ep}.m4a"
    if a.audio and Path(a.audio).resolve() != audio_dst.resolve():
        shutil.copyfile(a.audio, audio_dst)
    pub = rfc2822(a.publish) if a.publish else None

    if a.update:
        if not row:
            sys.exit(f"{guid} が無い(追加なら --update を外す)")
        for k, v in (("title", a.title), ("description", desc), ("duration_seconds", duration), ("pubDate", pub)):
            if v is not None:
                row[k] = v
        if a.audio:
            row["audio"] = f"{ep}.m4a"
        verb = "直した"
    else:
        if row:
            sys.exit(f"{guid} は既にある(直すなら --update)")
        missing = [n for n, v in (("--title", a.title), ("--desc-file", desc), ("--publish", pub)) if not v]
        if missing or duration is None:
            sys.exit("追加に必要: " + " ".join(missing + ([] if duration is not None else ["--duration か --transcript-json"])))
        expect = len(eps) + 1
        if a.num != expect:
            sys.exit(f"連番が合わない: 次は ep{expect:03d}(いま {len(eps)} 件)")
        if not audio_dst.exists():
            sys.exit(f"{audio_dst} が無い(--audio で元ファイルを渡す)")
        eps.append({"guid": guid, "title": a.title, "description": desc, "audio": f"{ep}.m4a",
                    "duration_seconds": duration, "pubDate": pub})
        verb = "追加した"

    EP_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{guid} を{verb}。" + build())

    if a.push:
        run(["git", "add", "-A"])
        msg = f"{ep} {verb.replace('した', '')}: {(a.title or row['title'])}"
        run(["git", "commit", "-q", "-m", msg + "\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"])
        run(["git", "pull", "-q", "--rebase"])
        print("再生成: " + build())
        run(["git", "push", "-q"])
        print("push 済み: " + run(["git", "log", "--oneline", "-1"]).stdout.strip())
    else:
        print("push はまだ(--push を付けて流し直すか、手で git push)")

    if a.desktop:
        pubd = a.publish or dt.datetime.strptime(row["pubDate"][5:16], "%d %b %Y").date().isoformat()
        out = DESKTOP / f"★stand.fm用_{pubd}_{ep}.m4a"
        shutil.copyfile(audio_dst, out)
        print("デスクトップへ複製: " + out.name)


if __name__ == "__main__":
    main()
