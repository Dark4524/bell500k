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
