# 検証記録（2026-07-28）

- 公開データ再加工: 成功。2,506ノード、2,647リンク、31改札、35出口、1,188施設。
- Pythonテスト: 26件成功。ヘルス、読込、出口・施設、通常/階段回避/到達不能、投稿検証・重複・頻度、非公開、管理認証・審査・監査・永続化を含む。
- Ruff: 成功。
- mypy: Windowsのアプリケーション制御がmypyのネイティブDLLをブロックしたため未完了。TypeScript型検査とは別の環境制約。
- フロントテスト: 7件成功。出口カード、検索、矢印座標、古い矢印削除、オフライン経路、到達不能を含む。
- TypeScript、ESLint、PWA資産検査: 成功。
- Next.js通常ビルド、Capacitor用静的ビルド: 成功。
- Alembic SQLite migration: 成功。
- ローカルAPI起動と `/api/health`: 成功。DB、公開データ、件数を確認。
- ブラウザ実画面: PCで31改札・35出口読込と230m/B1→1F経路を確認。390×844で横あふれなし、階層ボタン高さ44pxを確認。
- Capacitor Android追加・同期: 成功。
- Android APK: JDK/JAVA_HOMEがないため未生成。
- Docker: Dockerコマンドがないためビルド・コンテナ起動は未実行。

公開前にはDocker環境、PostgreSQL、OIDCプロキシ、Android実機、Service Workerの完全な機内モード、現地情報を別環境で再検証してください。
