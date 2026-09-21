# X 自動投稿

このフォルダは @jitsuyo_ai のX公式API自動投稿用です。

## GitHub Actions Secrets

Repository Settings → Secrets and variables → Actions に次の4件を登録します。

- `X_API_KEY`
- `X_API_KEY_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

値はGitHub Secretsだけに保存し、リポジトリのファイルやチャットには書きません。

## 実行時刻

- morning: 07:45 JST
- midday: 12:15 JST（速報等で必要な場合のみキューに入れる）
- evening: 20:30 JST

キューに対象投稿がなければ、API投稿は行いません。

## キュー形式

`x_auto/queue.json` に以下の形式で追加します。

```json
[
  {
    "id": "2026-09-22-evening-01",
    "date": "2026-09-22",
    "slot": "evening",
    "status": "ready",
    "text": "投稿本文",
    "tweet_id": null,
    "posted_at": null
  }
]
```

## 接続テスト

GitHub Actions の「X Auto Post」を手動実行し、mode=`test` を選びます。
テスト投稿を作成後、約3秒で自動削除します。

## 安全方針

- X Web画面の自動操作はしません。X公式APIのみを使います。
- 自動いいね、無差別フォロー、自動DM、無差別返信は行いません。
- API利用額はX Developer Consoleの請求サイクル上限を優先します。
- 投稿キューが空なら投稿しません。
- 失敗時は自動で連続再投稿しません。


## 2026-09-21 追加の安全機能

- 1日最大2投稿。上限到達時は投稿しません。
- 同一文面の再投稿を自動ブロックします。明示的に `allow_duplicate: true` を付けた場合だけ例外です。
- 1投稿あたり最大2回まで試行し、2回失敗したら `error` で停止します。
- 失敗時も `attempts`、`last_attempt_at`、`last_error` をキューへ保存します。
- 当面はAPI投稿時のハッシュタグ記号 # を自動除去します。
- 全体停止は `x_auto/settings.json` の `enabled: false` で行えます。
- 07:55 / 12:25 / 20:40 JST に10分後の予備実行があります。主実行で投稿済みなら予備実行は何もしません。

## インプレッション・反応取得

`x_auto/x_metrics.py` と `.github/workflows/x-metrics.yml` を用意済みです。

- 取得対象は投稿後24時間・72時間の2点。
- 取得結果は各投稿の `metrics_snapshots` に記録します。
- 実際の観測時刻と投稿後経過時間も残します。
- 現在は `settings.json` の `metrics_enabled: false` のため、X APIの読み取りは行いません。
- X APIの読み取り費用・残高運用を確認してから有効化します。

## 重要：公開リポジトリ

このリポジトリは公開です。そのため `queue.json` に入れた将来の投稿本文も公開状態になります。
認証情報はGitHub Secretsにあり公開されませんが、投稿前原稿を非公開にしたい場合は、今後専用の非公開リポジトリまたは非公開キューへ移行します。
