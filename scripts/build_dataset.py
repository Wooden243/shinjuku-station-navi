"""後方互換用エントリーポイント。

実装本体は取得処理と分離した ``normalize_open_data.py`` にある。
"""

from __future__ import annotations

from normalize_open_data import main

if __name__ == "__main__":
    raise SystemExit(main())
