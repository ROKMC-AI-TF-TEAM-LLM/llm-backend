"""폐쇄망 대응: vendor/ 의 aiomysql, pymysql 을 import 경로에 추가한다."""

import sys
from pathlib import Path

_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"

if _VENDOR_DIR.is_dir():
    _vendor_path = str(_VENDOR_DIR)
    if _vendor_path not in sys.path:
        sys.path.append(_vendor_path)
