# 新宿駅地下通路ナビゲーション MVP 実装計画

最終更新: 2026-07-27

## 1. 目的

出発改札と目的出口を利用者が選択し、公開されている Nav Node / Nav Link を用いた
重み付き最短経路を、階層別の MapLibre 2D 地図と保守的な案内文で提示する。
GPS、Bluetooth ビーコン、推測した現在地は使用しない。

## 2. 既存資産の監査結果

詳細は `docs/existing-assets-audit.md` を参照する。

- 既存リポジトリは FastAPI + React/Vite の試作 MVP であり、ユーザー指定の
  Next.js 構成ではない。
- NetworkX の有向グラフ、到達不能時の 422、階層別 GeoJSON、PyProj による測地線距離、
  raw/processed/overrides の分離という設計は再利用できる。
- 日本語が文字化けしており、複数の Python/TypeScript/JSON/CSV ファイルは構文自体が
  壊れている可能性があるため、表示文言とデータ変換は原典から作り直す。
- `ui_mock.html`、Colab ノートブック、`platform_gate_mapping_template.csv` は現在の
  ワークスペースには存在しない。存在しない資産の内容は推測して再現しない。
- 既存の公開データ取得先は国土交通省の広域歩行空間ネットワークだが、実データは未取得で、
  改札・出口の補正 CSV は未検証のサンプルである。

## 3. 採用する公開データ

主データとして東京都都市整備局「新宿駅周辺の施設情報等」を使用する。

- カタログ:
  https://catalog.data.metro.tokyo.lg.jp/dataset/t000008d0000000037
- ZIP:
  https://www.toshiseibi.metro.tokyo.lg.jp/kiban/shinjuku_terminal/pdf/shisetsu_root.zip
- 仕様書:
  https://www.toshiseibi.metro.tokyo.lg.jp/kiban/shinjuku_terminal/pdf/shisetsu_siyousho.pdf
- 提供者: 東京都都市整備局
- ライセンス: CC BY
- 内容: 階層別地図、施設情報、Nav Node、Nav Link、リンク距離、方向、階層差
- 仕様上の座標: GeoJSON/API 境界は WGS84（EPSG:4326）、距離はメートル

国土交通省の歩行空間ネットワークデータは補助候補として出典を残すが、異なる版・仕様の
ネットワークを根拠なく結合しない。

## 4. 推奨ディレクトリ構成

```text
.
├─ frontend/
│  ├─ app/                    # Next.js App Router
│  ├─ components/             # 検索、地図、経路情報
│  ├─ lib/                    # API クライアント、型、表示変換
│  └─ tests/                  # React コンポーネントテスト
├─ backend/
│  ├─ app/
│  │  ├─ api/                 # FastAPI ルーター
│  │  ├─ core/                # 設定、例外
│  │  ├─ repositories/        # JSON/GeoJSON 読み込み
│  │  ├─ services/            # 経路探索、案内文、スナップ
│  │  └─ schemas/             # Pydantic API 契約
│  └─ tests/
├─ data/
│  ├─ raw/                    # 取得原本と取得マニフェスト
│  ├─ processed/              # アプリ用正規化成果物
│  ├─ overrides/              # 根拠付き手動補正
│  └─ fixtures/               # テスト専用。公開データと表示しない
├─ scripts/
│  ├─ fetch_open_data.py
│  └─ normalize_open_data.py
├─ tests/                     # ETL 結合テスト
└─ docs/
```

## 5. 実装フェーズ

### Phase A: データ取得と仕様確認

1. 東京都 ZIP、仕様書、参考資料を `data/raw/` に保存する。
2. URL、取得日時、HTTP メタデータ、SHA-256、ライセンスを
   `data/raw/manifest.json` に記録する。
3. ZIP 内の Nav Node、Nav Link、Community Map、Level Geometry、
   Community Entities の対応関係を確認する。
4. 改札・出口分類に使える公開属性を列挙し、分類不能な項目は警告として残す。

### Phase B: 再実行可能な ETL

1. 取得処理と正規化処理を別スクリプトにする。
2. Nav Node のメルカトル座標を EPSG:4326 へ変換する。
3. Nav Link の `dm` をメートル距離として保持し、欠損・不正値だけを
   PyProj の測地線距離で補う。
4. `d` を有向辺へ変換し、`dz` とプロパティから階段・エスカレーター・
   エレベーター・階層移動を表現する。
5. レベル ID と公開レベル属性から `B2`、`B1`、`1F` 等へ正規化する。
   対応不能な階層は `UNKNOWN` のまま隔離し、経路計算に混入させない。
6. 公開施設から改札・出口を抽出し、同一階の最近傍 Nav Node へ測地線でスナップする。
7. 分類・名称・接続の手動補正は `data/overrides/` の根拠列付き CSV/JSON で適用する。
8. 正規化成果物と変換警告を `data/processed/manifest.json` に記録する。

### Phase C: FastAPI と経路探索

1. Pydantic で health、place、route、instruction、landmark の契約を明示する。
2. NetworkX `MultiDiGraph` に Nav Link を読み込む。
3. 距離を基本重みとし、階段回避時は階段辺を除外する。
4. 到達不能、未知 ID、データ未読込を成功レスポンスに変換しない。
5. 経路の実距離は採用辺のメートル距離の合計とする。
6. 経路を階層別 FeatureCollection に分割し、階層移動地点を返す。
7. 案内文は長さ・分岐・階層移動で区間化し、方位を確実に判定できない場合は
   左右を述べない。
8. スナップ距離が警告閾値を超えた場合、応答に明示する。
9. `platform_gate_mapping_template.csv` を任意読込できる検証済み拡張スキーマを用意する。

### Phase D: Next.js UI

1. Next.js App Router + TypeScript + CSS Modules へ移行する。
2. 検索可能な改札・出口コンボボックスを実装し、事業者・方面・階層を併記する。
3. MapLibre に階層別通路、赤い推奨経路、始点、終点、階層移動ラベルを描画する。
4. 現在地マーカーは実装しない。
5. PC は地図中心の 3 カラム、スマートフォンは検索・地図・案内の縦配置とする。
6. 読込中、探索中、エラー、到達不能、実データ未準備を別の文言と ARIA 状態で表示する。
7. 色だけに依存せず、形状・ラベル・アイコン・テキストを併用する。

### Phase E: 検証と文書

1. ETL の階層・方向・距離・スナップ・分類テスト。
2. 経路計算の距離、階段回避、一方通行、到達不能、階層分割の回帰テスト。
3. FastAPI API テスト。
4. React コンポーネントテスト、TypeScript、ESLint、Next.js 本番ビルド。
5. README、データ出典、起動手順、制約、現地未検証事項を更新する。
6. 実データ経路を複数件 API で確認し、サンプル専用機能と混同しない。

## 6. 主要リスクと対策

| リスク | 対策 |
|---|---|
| 公開データが調査時点の状態で現況と異なる | データ年月と未現地検証警告を常時表示 |
| 改札・出口が施設属性だけで完全分類できない | 自動分類結果を保存し、根拠付き overrides で補正 |
| レベル ID と表示階の対応が複雑 | Community Map のレベル属性を唯一の根拠とし、未知値を推定しない |
| 垂直リンクの設備種別が不足 | 不明な場合は `vertical` とし、階段等と断定しない |
| Nav Node が複数図面/レベルに属する | 物理レベルと描画レベルの対応を ETL で明示 |
| 一方通行・利用時間 | 公開属性を保持し、初期版で評価できない時間制約は警告 |
| 地図タイルの利用条件 | 初期版は公開階層図形を主地図にし、無断の第三者タイルを使わない |
| 実データが切断されている | 疑似直線で補完せず、到達不能を返す |

## 7. 完了判定

- `data/processed/manifest.json` が `data_mode: open-data` で、原本ハッシュを参照する。
- 実データから改札・出口・Nav Node・Nav Link が読み込まれる。
- `/api/health`、`/api/gates`、`/api/exits`、`/api/routes` が契約どおり動作する。
- 少なくとも一つの実データ改札→出口経路が計算・階層別表示される。
- 到達不能テストが疑似経路なしで成功する。
- pytest、コンポーネントテスト、型検査、ESLint、本番ビルドが成功する。
- README の Windows PowerShell 手順で再現できる。

