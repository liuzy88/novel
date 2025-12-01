from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Segment:
    index: int
    title: Optional[str]
    text: str


@dataclass
class Book:
    title: Optional[str]
    segments: List[Segment]


def load_book(path: str | Path, split_type: str = "简单") -> Book:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"找不到文本文件: {file_path}")

    raw_text = _read_file(file_path)
    if split_type == "简单":
        segments = _split_simple(raw_text)
    elif split_type in {"章", "卷章", "卷回节"}:
        # 暂未实现其他切分策略，默认退回简单切分
        segments = _split_simple(raw_text)
    else:
        segments = _split_simple(raw_text)

    title = file_path.stem
    return Book(title=title, segments=segments)


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _split_simple(text: str) -> List[Segment]:
    clean_lines = [line.strip() for line in text.splitlines() if line.strip()]
    segments: List[Segment] = []

    current: List[str] = []
    index = 0
    for line in clean_lines:
        current.append(line)
        if len(current) >= 10:
            segments.append(Segment(index=index, title=None, text="\n".join(current)))
            index += 1
            current = []

    if current:
        segments.append(Segment(index=index, title=None, text="\n".join(current)))

    return segments
