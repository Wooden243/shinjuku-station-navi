# Shinjuku Open Nav

東京都オープンデータ・ハッカソンへの提出を想定した、新宿駅周辺の階層別歩行ナビゲーションMVPです。

利用者が出発地点（改札）と目的地点（出口）を選ぶと、東京都都市整備局「新宿駅周辺の施設情報等」のオープンデータから最短経路を計算し、階層別2D地図に表示します。

## 重要な状態表示

- `open-data`: 取得・正規化済みの公開データを使用
- `sample`: 同梱の小規模な動作確認用データを使用

`sample`をハッカソンの実データ動作として提出しないでください。画面上部と`GET /api/health`にデータ状態が表示されます。

## 使用するオープンデータ

主データ:

- 名称: 新宿駅周辺の施設情報等
- 提供者: 東京都都市整備局
- カタログ: https://catalog.data.metro.tokyo.lg.jp/dataset/t000008d0000000037
- ライセンス: クリエイティブ・コモンズ 表示（CC BY 4.0）
- リソース: `shisetsu_root.zip`、`shisetsu_siyousho.pdf`
- 取得日、SHA-256、仕様改訂、変換警告は `data/raw/manifest.json` と `data/processed/manifest.json` に記録

補助データ:

- `data/overrides/places.csv`
- 改札・出口をネットワークへ結び付ける、人手確認可能な補正表
- `source_url`、`verified_on_site`、`note`を必須管理項目とする

公開原本は`data/raw/`、正規化結果は`data/processed/`、人手補正は`data/overrides/`に分離します。

## 1. 必要環境

- Python 3.11以上
- Node.js 20以上
- pnpm 10（Corepackで有効化）
- Windows PowerShell 7、macOS、Linuxのいずれか

## 2. Python環境の準備

```powershell
cd shinjuku-open-nav
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cd ..
```

## 3. オープンデータの取得と変換

```powershell
python scripts/fetch_open_data.py
.\backend\.venv\Scripts\python.exe scripts/build_dataset.py
```

取得先URLは`data/sources.json`に固定し、SHA-256、取得日時、ライセンスを`data/raw/manifest.json`へ記録します。

ネットワーク全域から新宿駅近傍のみを切り出す場合:

```powershell
.\backend\.venv\Scripts\python.exe scripts/build_dataset.py --center-lon 139.7006 --center-lat 35.6900 --radius-m 1800
```

変換後に以下が生成されます。

```text
data/processed/nodes.geojson
data/processed/links.geojson
data/processed/places.json
data/processed/manifest.json
```

## 4. バックエンド起動

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000/api/health
- OpenAPI: http://localhost:8000/docs

## 5. フロントエンド起動

別のPowerShellを開きます。

```powershell
cd frontend
corepack enable
pnpm install --frozen-lockfile
Copy-Item .env.example .env.local
pnpm dev
```

画面: http://localhost:3000

## 6. 一括起動（Windows）

依存関係をインストールした後、リポジトリ直下で実行します。

```powershell
.\start-dev.ps1
```

Docker Composeを使う場合:

```powershell
docker compose up --build
```

画面は http://localhost:3000、APIは http://localhost:8000 です。

## 7. テスト

```powershell
cd backend
pytest

cd ..\frontend
pnpm test
pnpm typecheck
pnpm lint
pnpm build
```

## 8. API

- `GET /api/health`: データ読込状態
- `GET /api/gates`: 改札一覧
- `GET /api/exits`: 出口一覧
- `GET /api/network?floor=B1`: 表示用歩行ネットワーク
- `POST /api/routes`: 経路計算

リクエスト例:

```json
{
  "start_gate_id": "sample-gate-west",
  "destination_exit_id": "sample-exit-a1",
  "preferences": {
    "avoid_stairs": false
  }
}
```

## 9. データ補正の方法

`data/overrides/places.csv`へ地点を追加します。

```csv
id,type,name,operator,floor,lon,lat,source_url,verified_on_site,note
```

- `type`: `gate`または`exit`
- `floor`: `B2`、`B1`、`1F`等
- `lon` / `lat`: WGS84（EPSG:4326）
- `source_url`: 根拠となる公開ページ
- `verified_on_site`: 現地確認済みなら`true`

変換時に最寄りノードへスナップされます。既定の許容距離を超える地点は除外され、警告として記録されます。

## 10. 提出前の確認

1. `python scripts/fetch_open_data.py`が成功する。
2. `python scripts/build_dataset.py`が`data_mode=open-data`を生成する。
3. `/api/health`の`data_mode`が`open-data`である。
4. 少なくとも3組の改札・出口で経路を手動確認する。
5. 改札・出口の位置を現地確認し、`verified_on_site`を更新する。
6. 全テスト、型検査、Lint、本番ビルドを実行する。
7. `docs/data-audit.md`へ確認結果を記録する。

## 11. 現時点の制約

- 公開データの更新日以後に生じた通路変更・工事規制は自動反映しません。
- 営業時間、一時閉鎖、混雑度を考慮しません。
- 補正表の初期行は実装確認用であり、提出前の現地検証が必要です。
- ナビゲーション結果は参考情報です。現地の案内表示・係員の指示を優先してください。
