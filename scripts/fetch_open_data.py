from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = PROJECT_ROOT / "data" / "sources.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
USER_AGENT = "ShinjukuOpenNav/1.0 (+Tokyo-open-data-hackathon)"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"HTTP {status}: {url}")
        with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent) as temp:
            shutil.copyfileobj(response, temp)
            temporary_path = Path(temp.name)
        headers = {
            "content_type": response.headers.get("Content-Type"),
            "content_length": response.headers.get("Content-Length"),
            "last_modified": response.headers.get("Last-Modified"),
            "etag": response.headers.get("ETag"),
        }
    temporary_path.replace(destination)
    return headers


def main() -> int:
    parser = argparse.ArgumentParser(description="東京都の新宿駅オープンデータを取得します。")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="既存原本を再ダウンロードせず、ハッシュとマニフェストだけを更新します。",
    )
    args = parser.parse_args()

    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    retrieval_time = datetime.now(UTC).isoformat()

    for resource in sources["resources"]:
        destination = RAW_DIR / resource["filename"]
        headers: dict[str, Any] = {}
        if not args.reuse_existing or not destination.is_file():
            print(f"Downloading {resource['name']} -> {destination}")
            headers = download(resource["url"], destination)
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError(f"Downloaded resource is empty: {destination}")
        records.append(
            {
                **resource,
                "retrieved_at": retrieval_time,
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
                "http": headers,
            }
        )

    manifest = {
        "dataset": sources["dataset"],
        "resources": records,
        "warnings": [
            "公開データは調査時点の情報であり、現況と異なる可能性があります。",
            "原本ZIPの内部ディレクトリ名はレガシー文字コードのため、正規化処理はファイル末尾名で識別します。",
        ],
    }
    (RAW_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Download complete. Review data/raw/manifest.json.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

