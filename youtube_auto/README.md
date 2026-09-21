# YouTube 自動投稿基盤

ベル30日チャレンジの動画を、将来 YouTube Shorts へ公式 YouTube Data API でアップロードするための基盤です。

## 現在の安全状態

- `settings.json` の `enabled=false`。
- 自動アップロードは **private限定**。
- GitHub Actionsから公開設定へ変更する機能はまだ入れていません。
- OAuth認証が完了していなくても validate は実行できます。
- YouTube / Google の認証情報はGitHub Secretsだけに保存します。

## 必要なGitHub Secrets

OAuth接続後に最低限、次の2件をPrivateリポジトリ側へ登録します。

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_REFRESH_TOKEN`

ダウンロードしたOAuthクライアントに `client_secret` が含まれる場合だけ、`YOUTUBE_CLIENT_SECRET` も追加します。Desktop OAuthはpublic clientとして扱われるため、client secretを必須条件にはしません。

## Google側で一度だけ必要な設定

1. Google Cloudプロジェクトで YouTube Data API v3 を有効化。
2. OAuth同意画面を設定。
3. Desktop app または適切なOAuth clientを作成。
4. OAuth client JSONをPCへ保存。
5. `get_refresh_token.py` をPCで一度実行し、ブラウザでYouTubeチャンネルへのアップロード権限を承認。
6. 得られたClient IDとRefresh TokenをGitHub Secretsへ保存。Client Secretが返る構成ならそれも保存。

使用スコープは最小限の `youtube.upload` のみです。

## キュー例

```json
[
  {
    "id": "2026-09-22-short-01",
    "date": "2026-09-22",
    "status": "ready",
    "file": "generated/2026-09-22-short-01.mp4",
    "title": "AI自動投稿を実際に作って分かったこと",
    "description": "ベル30日チャレンジの検証記録です。",
    "privacy_status": "private"
  }
]
```

## 実装順

1. 動画生成エンジンがMP4を作る。
2. YouTubeキューへメタデータを入れる。
3. validateで縦動画・長さ・タイトル等を確認。
4. OAuth接続後にPrivateアップロード試験。
5. YouTube側のAPIプロジェクト監査・運用条件を確認後、公開/予約公開を検討。

## 注意

新しい未監査APIプロジェクトから `videos.insert` でアップロードした動画は、Google側の監査を通すまで非公開に制限される場合があります。初期テストはその仕様と相性がよいため、private限定で始めます。


## OAuth Testing運用の注意

Google Auth Platformを External / Testing のまま使う場合、`youtube.upload` のような基本プロフィール以外のスコープを含むrefresh tokenは原則7日で期限切れになります。最初の非公開アップロード試験には使えますが、30日間の無人運転に入れる前にOAuthの公開状態・確認要否を整理します。
