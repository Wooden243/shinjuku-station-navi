# 公開手順

フロントはVercel、APIはRender、DBはRender PostgreSQLを想定します。GitHubへ秘密を除くソースをpushし、Renderで `render.yaml`、Vercelで `frontend` をルートとして読み込みます。

Vercelには `BACKEND_URL=https://APIのホスト名` と、ブラウザ直通構成なら `NEXT_PUBLIC_API_BASE_URL` を設定します。Renderの `SHINJUKU_CORS_ORIGINS` は公開フロントのHTTPS originだけにします。`SHINJUKU_ENV=production`、`SHINJUKU_AUTH_MODE=oidc-proxy`、PostgreSQL `DATABASE_URL` を使用します。OIDCプロキシなしでは管理操作を公開しないでください。

APIコンテナは `data/processed` を内包します。起動時にAlembicを適用し、`/api/health` でDB・データ件数を監視します。PWAはHTTPS必須です。公開後にService Worker更新、CORS、Cookie、バックアップ復元を実機確認します。
