# Multi Social Auto - common foundation

ベル30日チャレンジの副線として、X / YouTube / Instagram / TikTok を将来1つの投稿基盤にまとめるための共通層です。

## 現在の状態

- X: 既存の `x_auto/` が本番稼働。
- YouTube: 未接続。
- Instagram: 未接続。
- TikTok: 未接続。
- このフォルダ自体は **dry-run専用**。外部投稿はしません。

## 共通データ

`social_auto/queue.json` の1項目は、1つの元ネタから複数媒体へ展開できる形にします。

主な項目:

- id
- date
- source_theme
- asset_type
- asset_url
- platforms
- status
- text_by_platform
- title_by_platform
- scheduled_slot_by_platform

## 方針

- 媒体ごとに別々の企画を作らず、1つの元ネタを各媒体向けに最適化する。
- 各媒体の公式APIだけを使う。
- 未接続媒体は自動で live にならない。
- 認証情報はGitHub Secrets等の秘匿領域だけに置く。
- Xの実績を先に安定させ、YouTube → Instagram → TikTok の順で接続する。
