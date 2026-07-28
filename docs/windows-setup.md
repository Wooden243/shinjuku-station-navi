# Windowsセットアップ

Python 3.12、Node.js 22以上、Corepackを用意します。初回コマンドはREADMEをそのままコピーしてください。PowerShellの実行ポリシーで仮想環境を有効化できなくても、`backend\.venv\Scripts\python.exe` を直接呼べます。Docker Desktopは任意です。文字化けを避けるにはPowerShell 7とUTF-8対応エディターを推奨します。

起動確認は `http://localhost:8000/api/health` の `data_loaded=true` と、`http://localhost:3000` の地図表示です。秘密値は `.env` に置き、コミットしません。
