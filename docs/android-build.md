# Androidビルド

CapacitorのWeb出力先は `frontend/out` です。API URLはHTTPS公開APIへ設定します。

```powershell
cd frontend
$env:NEXT_PUBLIC_API_BASE_URL="https://your-api.example"
corepack pnpm cap:sync
corepack pnpm android:open
```

Android StudioでGradle同期後、Debug APKを作成します。CLIならJDK 21とAndroid SDKを設定して `cd android; .\gradlew.bat assembleDebug` です。WindowsではiOSビルド不可です。iOSはmacOS、Xcode、Apple開発者署名が必要です。

CapacitorのWebViewではIndexedDBによる経路網・投稿キューを利用します。アプリ初回はオンライン接続が必要です。APK公開前に実機で機内モード経路、復帰後投稿同期、保存容量不足を確認してください。
