# ichi-radio — 「イチの仕事資産化ラジオ」Podcast配信リポジトリ

> **注意: cover.jpg を追加するまで Podcastディレクトリ(Spotify / Apple Podcasts 等)への登録は不可。**
> feed.xml は `https://icchanyoga.github.io/ichi-radio/cover.jpg` を参照済みだが、画像の実体がまだ無い(ユーザーが生成中)。リポジトリ直下に `cover.jpg` を置けば登録可能になる。

GitHub Pages で Podcast RSS を自前ホスティングするためのリポジトリ。

- 公開URL: https://icchanyoga.github.io/ichi-radio (未公開・構築中)
- RSS: https://icchanyoga.github.io/ichi-radio/feed.xml
- 番組情報の原本: `C:\Users\tyura\音声変換\配信箱\番組情報.md`
- 各エピソードの出典(タイトル・概要欄・チャプター): `C:\Users\tyura\音声変換\配信箱\承認済み\` の配信パック

## 構成

```
ichi-radio/
├─ README.md              このファイル
├─ episodes.json          番組メタ+全エピソードのメタデータ(手で編集するのはここだけ)
├─ scripts/build_feed.py  episodes.json → feed.xml + index.html を生成
├─ feed.xml               生成物(直接編集しない)
├─ index.html             生成物(直接編集しない)。エピソード一覧+試聴プレイヤー
└─ audio/epNNN.m4a        音声の実体
```

## エピソード追加手順

1. 音声ファイルを `audio/epNNN.m4a`(連番)としてコピーする
2. `episodes.json` の `episodes` 配列の**末尾**に1件追記する:
   - `guid`: `ichi-radio-epNNN`(固定文字列。後から変えない)
   - `title`: 配信パックのタイトル案から採用したもの
   - `description`: 配信パックの概要欄(紹介文+ハッシュタグ)+空行+チャプター
   - `audio`: `epNNN.m4a`
   - `duration_seconds`: 文字起こしjsonの `duration_seconds`
   - `pubDate`: RFC 2822形式・`+0900`(例: `Fri, 10 Jul 2026 09:00:00 +0900`)。
     運用ルール: **制作日D → 公開日は「投稿翌日の07:00:00 +0900」** で登録する
     (例: 7/10に制作したエピソードは `Sat, 11 Jul 2026 07:00:00 +0900`)。
3. 生成スクリプトを実行する(enclosureのバイト数は実ファイルから自動計算される):
   ```
   python scripts/build_feed.py
   ```
   `feed.xml OK (well-formed, N items)` と出れば成功。
   - `build_feed.py` は既定で **pubDateが現在時刻(JST)より未来のエピソードを
     feed.xml / index.htmlから除外する**(時限公開)。全件を確認したい場合のみ
     `python scripts/build_feed.py --include-future` を使う(生成物は上書きしない
     こと。確認用途に留める)。
4. `git add` → `commit` → `push`(GitHub Pagesが自動反映)
   - **未来日付(D+1 07:00など)で登録したエピソードは、push直後はfeedに現れない。**
     毎朝07:15(JST)に動く GitHub Actions(`.github/workflows/scheduled_release.yml`)
     が `build_feed.py` を再実行し、公開日が到来したエピソードを自動でfeed.xmlと
     index.htmlへ反映してcommit+pushする。PCの電源が入っていなくても公開される。

## 注意

- `feed.xml` と `index.html` は生成物。直接編集せず、必ず `episodes.json` を直して再生成する
- `guid` は各プラットフォームがエピソードの同一性判定に使うため、公開後は絶対に変更しない
- 音声の元ファイルは `C:\Users\tyura\FP1級基礎〇×ノック\素材\音声\受信箱アーカイブ\` に残してある(このリポジトリのaudio/はコピー)
- 時限公開: `pubDate` が未来のエピソードは `build_feed.py` の実行時点でfeedから自動的に
  除外される。除外はpubDateの解析成功時のみ行われ、解析できないエピソードは安全側に
  倒して常に含まれる(既存エピソードを誤って落とさないため)。公開日到来分は
  毎朝07:15(JST)のGitHub Actionsが自動反映するので、手動でのpush作業は不要
