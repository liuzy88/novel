from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from config import CONFIG_DIR, ensure_config_dir


PROGRESS_PATH = CONFIG_DIR / "progress.json"


def _load_raw() -> Dict[str, Dict[str, int]]:
    ensure_config_dir()
    if not PROGRESS_PATH.exists():
        return {}
    try:
        return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_raw(data: Dict[str, Dict[str, int]]) -> None:
    ensure_config_dir()
    PROGRESS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_progress(txt_path: Path, split_type: str) -> Optional[int]:
    data = _load_raw()
    split_map = data.get(split_type, {})
    return split_map.get(str(txt_path))


def save_progress(txt_path: Path, split_type: str, index: int) -> None:
    data = _load_raw()
    split_map = data.setdefault(split_type, {})
    split_map[str(txt_path)] = index
    _save_raw(data)
