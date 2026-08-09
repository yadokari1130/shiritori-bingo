# しりとりビンゴ

Vue 3 + Vuetify のフロントエンドと、Python 3.14 + FastAPI + SQLite のバックエンドで構成した、複数端末対応のしりとりビンゴです。

ルームのゲーム状態、カード、単語履歴、undo履歴はバックエンドのSQLiteへ保存し、参加者の再接続はHttpOnly CookieとSSEで行います。ブラウザの`localStorage`には、利用者が明示的に保存したゲームルールの名前付きプリセットだけを保存します。

## 前提環境

- Python 3.14 以上
- uv
- Node.js 20 以上（フロントエンド用）
- pnpm 10 以上（フロントエンド用）
- Docker Compose（コンテナ起動を確認する場合）

## 依存関係のインストール

```sh
pnpm --dir frontend install
uv sync --directory backend
```

必要に応じて、`frontend/.env.example` と `backend/.env.example` を `.env` として用意します。ローカル開発では、フロントエンドの開発サーバーが`/api`へのリクエストを`http://localhost:3001`にプロキシするため、`.env`がなくても動作します。本番では、バックエンドの`FRONTEND_ORIGIN`にブラウザで表示するフロントエンドのOriginを指定してください。複数のOriginはカンマ区切りで指定できます。

## ローカル起動

バックエンドを起動します。

```sh
uv run --directory backend fastapi dev
```

別のターミナルでフロントエンドを起動します。

```sh
pnpm --dir frontend dev
```

フロントエンドは `http://localhost:5173`、バックエンドのヘルスチェックは `http://localhost:3001/api/health` で確認できます。ルーム作成後、`/game/:roomId`のURLを参加者へ共有します。

## 確認コマンド

```sh
pnpm --dir frontend build
pnpm --dir frontend test
uv run --directory backend ruff check .
uv run --directory backend pytest
```

## Docker Compose

バックエンドコンテナだけを起動します。nginx は本番 VPS のホストへインストールする構成です。

```sh
docker compose build app
docker compose up -d app
```

SQLite の永続化先はプロジェクト直下の `data/` です。Docker Compose ではコンテナをホストユーザー（UID 1000）で実行するため、`data/` ディレクトリが同じユーザーで書き込み可能であることを確認してください。nginx の設定は `nginx/shiritori-bingo.conf` を VPS の `sites-available` 配下へ配置し、ドメインと証明書のパスを環境に合わせて変更します。

## CORS設定

本番の`FRONTEND_ORIGIN`は、Cloudflare Pagesの実際のOriginと完全に一致させます。例えばフロントエンドが`https://shiritori-bingo.pages.dev`で公開されている場合は、次のように設定します。

```text
FRONTEND_ORIGIN=https://shiritori-bingo.pages.dev
```

Originにはパスや末尾の`/`を指定しません。API側のOriginはフロントエンドの`VITE_API_BASE_URL`に指定し、変更後はバックエンドの再起動とフロントエンドの再ビルドが必要です。未指定のOriginや`*`はCookie付き通信のため許可されません。

Docker Composeでは、ホスト側の`FRONTEND_ORIGIN`環境変数をコンテナへ渡します。未指定の場合はローカル開発用の`http://localhost:5173`になります。
