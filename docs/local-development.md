# ローカル開発

バックエンドはFastAPI、SQLAlchemy、Alembic、NetworkX、SQLite、フロントエンドはNext.js、React、TypeScript、MapLibre GL JSです。APIを先に8000番、フロントを3000番で起動します。

スキーマ変更時:

```powershell
cd backend
.\.venv\Scripts\alembic.exe -c alembic.ini revision --autogenerate -m "change"
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

データ加工は `scripts/normalize_open_data.py` だけで行い、原本を編集しません。経路不具合は再現テストを先に追加し、切断ノードに架空の線を足さないでください。
