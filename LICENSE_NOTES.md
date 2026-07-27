# Data and software licensing notes

## Open data

The application uses the following dataset.

- Dataset: 新宿駅周辺の施設情報等
- Provider: 東京都都市整備局
- Catalog URL: https://catalog.data.metro.tokyo.lg.jp/dataset/t000008d0000000037
- Terms: クリエイティブ・コモンズ 表示 4.0 国際（CC BY 4.0）
- Attribution example: 「東京都都市整備局『新宿駅周辺の施設情報等』」を加工して作成

The public-data terms and the catalog page must be checked again immediately
before publication. The generated `data/raw/manifest.json` records the URLs,
retrieval timestamps and checksums of the actual downloaded resources.

## Basemap

The current MapLibre style is intentionally blank. This avoids silently
depending on a third-party tile service. If a basemap is added, include its
attribution and comply with its usage policy.

## Software

Project source code is provided under the MIT License in `LICENSE`.
