# 新宿地下ナビ

東京都都市整備局のオープンデータ「新宿駅周辺の施設情報等」を加工し、改札から出口までを階層別に案内するアプリです。出口詳細、施設検索、方向矢印、階層移動、利用者投稿、管理者審査、PWAオフライン経路探索を備えます。

> 経路・営業時間・閉鎖情報は最新とは限りません。緊急時は現地表示と係員の指示を優先してください。GPS、氏名、メールアドレスは取得しません。

## Windowsで初回起動

PowerShellを2つ開きます。

```powershell
cd C:\Users\aiue1\shinjuku_navi_app
Copy-Item .env.example .env
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

別のPowerShell:

```powershell
cd C:\Users\aiue1\shinjuku_navi_app\frontend
corepack enable
corepack pnpm install --frozen-lockfile
Copy-Item .env.example .env.local
corepack pnpm dev
```

利用者画面は `http://localhost:3000`、管理画面は `http://localhost:3000/admin`、API仕様は `http://localhost:8000/docs` です。開発用管理キーは `.env` の `SHINJUKU_ADMIN_KEY` に自分で設定します。`.env` はGitへ登録しないでください。

## 2回目以降

```powershell
cd C:\Users\aiue1\shinjuku_navi_app
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

別のPowerShell:

```powershell
cd C:\Users\aiue1\shinjuku_navi_app\frontend
corepack pnpm dev
```

## 版の違い

- ローカル開発版: SQLiteと開発用キー認証。コード変更を即時反映。
- 公開Web版: VercelのNext.jsとRenderのAPI、永続PostgreSQLを想定。
- PWA版: HTTPSでインストール可能。初回オンライン時に経路網・地点・施設をIndexedDBへ保存。
- Android版: Capacitor構成。`frontend/android`をAndroid Studioで開く。
- iOS版: macOSとXcodeが必要。現在のWindows成果物にはiOSプロジェクトを含めません。
- 管理者画面: 投稿の絞り込み、詳細・類似・公式データ比較、審査、監査、CSV/JSON出力。

## データ更新

原本は変更せず `data/raw` に保存し、加工結果を `data/processed`、根拠付き手動補正を `data/overrides` に分離します。

```powershell
backend\.venv\Scripts\python.exe scripts\normalize_open_data.py
```

取得URL、取得時刻、SHA-256、ライセンス、件数、警告、加工履歴は `data/raw/manifest.json` と `data/processed/manifest.json` に記録します。未知の階層や不足情報を推測で補いません。本番データにサンプル店舗は含めません。

## 検証

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe app
cd ..\frontend
corepack pnpm test
corepack pnpm typecheck
corepack pnpm lint
corepack pnpm build
corepack pnpm pwa:check
```

## 認証

ローカルの `development-key` は学習・開発専用です。キー自体をフロントエンドへ埋め込まず、ログイン成功後は署名付きHttpOnly Cookieを使います。本番では `SHINJUKU_ENV=production` と `SHINJUKU_AUTH_MODE=oidc-proxy` を設定し、認証プロキシからの署名付きヘッダーだけを受け付けます。公開前には Auth0、Microsoft Entra ID、Cloudflare Access等のOIDCと、多要素認証・権限管理を導入してください。

## 文書

- [構成](docs/architecture.md)
- [Windows設定](docs/windows-setup.md)
- [ローカル開発](docs/local-development.md)
- [公開](docs/deployment.md)
- [Android](docs/android-build.md)
- [オフライン設計](docs/offline-design.md)
- [データ出典](docs/data-sources.md)
- [管理運用](docs/admin-operation.md)
- [現地確認](docs/field-verification.md)
- [プライバシー](PRIVACY.md) / [セキュリティ](SECURITY.md)
