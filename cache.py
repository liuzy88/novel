from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, date
from pathlib import Path
from typing import Iterable, Dict


CACHE_ROOT = Path.home() / ".novel_player"
MP3_DIR = CACHE_ROOT / "mp3"
LOG_DIR = CACHE_ROOT / "logs"

_executor = ThreadPoolExecutor(max_workers=4)
_inflight: Dict[Path, Future] = {}
_lock = threading.Lock()


def _ensure_dirs() -> None:
    MP3_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_mp3_path(text: str, voice: str, rate: str) -> Path:
    _ensure_dirs()
    md5 = hashlib.md5()
    md5.update(f"{voice}|{rate}|{text}".encode("utf-8"))
    filename = f"{md5.hexdigest()[:16]}.mp3"
    return MP3_DIR / filename


def ensure_mp3(text: str, voice: str, rate: str) -> Path:
    target = get_mp3_path(text, voice, rate)
    if target.exists():
        return target

    with _lock:
        future = _inflight.get(target)
        if future is None:
            future = _executor.submit(_download_and_log, text, voice, rate, target)
            _inflight[target] = future

    try:
        future.result()
    finally:
        with _lock:
            if target in _inflight and _inflight[target].done():
                _inflight.pop(target, None)
    return target


def preload_segments(texts: Iterable[str], voice: str, rate: str) -> None:
    for text in texts:
        if not text:
            continue
        target = get_mp3_path(text, voice, rate)
        if target.exists():
            continue
        with _lock:
            if target in _inflight:
                continue
            future = _executor.submit(_download_and_log, text, voice, rate, target)
            _inflight[target] = future


def _download_and_log(text: str, voice: str, rate: str, path: Path) -> None:
    _ensure_dirs()
    start = time.time()
    start_ts = datetime.now().isoformat()
    _download_tts(text=text, voice=voice, rate=rate, path=path)
    end = time.time()
    log_line = {
        "start": start_ts,
        "end": datetime.now().isoformat(),
        "duration": round(end - start, 3),
        "voice": voice,
        "rate": rate,
        "text_preview": text[:20],
        "mp3_path": str(path),
    }
    _write_log(log_line)


def _download_tts(text: str, voice: str, rate: str, path: Path) -> None:
    try:
        import edge_tts
    except Exception as exc:  # pragma: no cover - 依赖缺失时提示
        raise RuntimeError("需要安装 edge-tts 才能下载 TTS 音频，请先安装依赖。") from exc

    async def _save() -> None:
        communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await communicator.save(str(path))

    asyncio.run(_save())


def _write_log(entry: Dict[str, object]) -> None:
    log_file = LOG_DIR / f"tts_{date.today().isoformat()}.log"
    try:
        with log_file.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # 日志失败不应影响主流程
        pass
