from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict


CONFIG_DIR = Path.home() / ".novel_player"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class Config:
    voice: str = "zh-CN-YunxiNeural"
    rate: str = "+20%"
    split_type: str = "简单"
    preload_segments: int = 2

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        return cls(
            voice=str(data.get("voice", cls.voice)),
            rate=str(data.get("rate", cls.rate)),
            split_type=str(data.get("split_type", cls.split_type)),
            preload_segments=int(data.get("preload_segments", cls.preload_segments)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def validate_rate(rate: str) -> bool:
    # 速率格式示例：+20%、-10%、0%
    return bool(re.match(r"^[+-]?\d+%$", rate.strip()))


def load_config() -> Config:
    ensure_config_dir()
    if not CONFIG_PATH.exists():
        return Config()

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return Config.from_dict(raw)
    except Exception:
        # 文件损坏或格式不对时回退默认
        return Config()


def save_config(config: Config) -> None:
    ensure_config_dir()
    CONFIG_PATH.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
