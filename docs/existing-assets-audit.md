# 既存資産監査

監査日: 2026-07-27

## 全体所見

ワークスペース内の全ファイルと空ディレクトリを確認した。既存実装は
FastAPI + React/Vite の試作品で、公開データ取得・正規化の骨格と NetworkX 経路探索はあるが、
公開データ本体は存在しない。日本語の文字化けが文書、CSV、JSON、Python、TypeScript に広がり、
そのまま本番用に継ぎ足せる状態ではない。

`ui_mock.html`、`.ipynb`、既存の Colab ノートブック、`platform_gate_mapping_template.csv` は
現在のフォルダには存在しない。

## ファイル別の役割と再利用方針

### ルート

| ファイル | 現在の役割 | 再利用方針 |
|---|---|---|
| `AGENTS.md` | データ品質・距離・補正・到達不能の開発規則 | 全項目を必須制約として維持 |
| `.gitignore` | Python/Node生成物と data raw/processed の除外 | raw 原本の保存方針と矛盾しないよう見直す |
| `docker-compose.yml` | Vite + FastAPI の2サービス | Next.js のポート/環境変数へ更新 |
| `LICENSE` | アプリコードの MIT ライセンス | 維持 |
| `LICENSE_NOTES.md` | 公開データと地図のライセンス注記 | 正しい日本語と採用データへ更新 |
| `README.md` | 起動・ETL・API・制約 | 構成は参考、内容は全面更新 |
| `start-dev.ps1` | 2プロセス起動 | Next.js/FastAPI 用に更新 |
| `TEST_RESULTS.md` | 過去の試作テスト結果 | 新しい実行結果で置換 |

### `backend/`

| ファイル | 現在の役割 | 再利用方針 |
|---|---|---|
| `pyproject.toml` | FastAPI/NetworkX/PyProj とテスト依存 | GeoPandas/Shapely を追加し構成を再利用 |
| `Dockerfile` | API コンテナ | データマウントを保ち更新 |
| `app/config.py` | データ場所、CORS、重み設定 | 型付き Settings の考え方を再利用 |
| `app/data_loader.py` | GeoJSON→MultiDiGraph | 厳密な検証とランドマーク対応を加えて分割 |
| `app/models.py` | Pydantic API スキーマ | 契約の出発点として再利用 |
| `app/routing.py` | 最短経路、階層分割、案内文 | 距離・到達不能方針を再利用し文字列と重み処理を修正 |
| `app/main.py` | API ルートと lifespan 読込 | ルーター/サービス分割へ移行 |
| `tests/*` | API のサンプル回帰テスト | fixtures と明示し、ETL/経路/APIテストを拡充 |

### `frontend/`

| ファイル | 現在の役割 | 再利用方針 |
|---|---|---|
| `package.json` / lock | React/Vite/MapLibre | Next.js 用に置換 |
| `src/api.ts` | 型付き fetch ラッパー | エラー契約を明確にして `lib/` へ移植 |
| `src/types.ts` | API 型 | OpenAPI と対応させて再利用 |
| `src/MapView.tsx` | MapLibre の通路・経路・地点描画 | レイヤー設計を参考に Next.js client component 化 |
| `src/App.tsx` | 検索・経路・状態管理 | 画面要件の参考。検索可能 UI へ分割 |
| `src/styles.css` | PC/スマホレスポンシブ | 色・レイアウトの一部を参考、CSS Modules へ分割 |
| Vite/TS/ESLint/Docker 設定 | 試作ビルド | Next.js 標準へ置換 |

### `data/`

| ファイル | 現在の役割 | 再利用方針 |
|---|---|---|
| `sources.json` | 旧MLITデータURL | 補助候補として履歴保存し、主データを東京都へ更新 |
| `sample/*` | 8ノードの動作確認用架空ネットワーク | `fixtures/` に移し、公開データと明示的に分離 |
| `overrides/places.csv` | 未検証の架空改札・出口 | 事実データとして使わず、根拠列付きテンプレートへ置換 |
| `processed/.gitkeep` | 正規化出力先 | 維持 |

### `scripts/`

| ファイル | 現在の役割 | 再利用方針 |
|---|---|---|
| `fetch_open_data.py` | GeoJSON2ファイル取得、SHA-256記録 | 原子保存・ハッシュ記録を再利用し ZIP/PDF 取得へ対応 |
| `build_dataset.py` | 別仕様GeoJSONの正規化と地点スナップ | 測地線距離・raw/processed分離を再利用し、東京都Nav仕様向けに再実装 |

### `docs/`

既存の計画、仮定、データ監査、提出概要は短く、文字化けもある。
新しい実データ仕様、実行結果、未検証事項を反映して更新する。

## 技術的リスク

- 日本語破損により既存コードは構文チェック前提で扱う必要がある。
- 試作フロントは Next.js 要件、検索可能セレクタ、コンポーネントテストを満たさない。
- 既存 ETL は東京都データの Nav Node/Nav Link 仕様を扱えない。
- 既存経路重みは階段へ常時 80 m の追加ペナルティを課し、「距離を基本コスト」と一致しない。
- MultiDiGraph の重み関数が選んだ辺と、後段で選び直す辺が一致する保証を強化する必要がある。
- 不明階層を `UNKNOWN` としてグラフへ入れており、隔離が必要。
- 地点をノードだけへスナップしており、長いリンク中央付近では誤差が大きくなり得る。
- ランドマーク、ホーム対応 CSV、フロントエンドテストが未実装。

## データ上の不確実性

- 公開データは調査時点の状態で、現況との差が明記されている。
- 改札・出口の名称・事業者・方向・階層が全件揃うかは ZIP 実査前には断定できない。
- 設備種別や利用時間が全リンクで機械判読できるか不明。
- 異なる公開データ版を結合すると接続・版整合性を損なう恐れがある。
- 現地確認をしていない経路を「検証済み」と表示できない。

