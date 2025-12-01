from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which
from threading import RLock
from typing import Optional

import cache

try:
    from pydub import AudioSegment
    import simpleaudio  # type: ignore

    _AUDIO_BACKEND = "pydub"
except Exception:
    _AUDIO_BACKEND = None


class Player:
    def __init__(self, voice: str, rate: str) -> None:
        self.voice = voice
        self.rate = rate
        self.state = "IDLE"
        self._play_obj = None
        self._process: Optional[subprocess.Popen] = None
        self._lock = RLock()
        self._subprocess_cmd = self._detect_subprocess_cmd()

    def _detect_subprocess_cmd(self) -> Optional[list[str]]:
        if which("afplay"):
            return ["afplay"]
        if which("aplay"):
            return ["aplay"]
        if which("mpg123"):
            return ["mpg123", "-q"]
        return None

    def play_text(self, text: str, *, autoplay: bool = True) -> Path:
        mp3_path = cache.ensure_mp3(text, self.voice, self.rate)
        if autoplay:
            self.play_file(mp3_path)
        return mp3_path

    def play_file(self, path: str | Path) -> None:
        target = Path(path)
        with self._lock:
            self._stop_locked()
            # 优先使用系统播放器，其次回退 pydub
            if self._subprocess_cmd and self._play_with_subprocess(target):
                return
            if _AUDIO_BACKEND == "pydub" and self._play_with_pydub(target):
                return
            print("未找到可用的音频播放方式，请安装 simpleaudio+pydub 或确保系统有 afplay/aplay/mpg123。")
            self.state = "IDLE"

    def _play_with_pydub(self, path: Path) -> bool:
        try:
            segment = AudioSegment.from_file(path)
            self._play_obj = simpleaudio.play_buffer(
                segment.raw_data,
                num_channels=segment.channels,
                bytes_per_sample=segment.sample_width,
                sample_rate=segment.frame_rate,
            )
            self.state = "PLAYING"
            return True
        except Exception as exc:
            print(f"pydub 播放失败，尝试系统播放器。错误: {exc}")
            self._play_obj = None
            return False

    def _play_with_subprocess(self, path: Path) -> bool:
        if not self._subprocess_cmd:
            return False
        cmd = [*self._subprocess_cmd, str(path)]
        try:
            self._process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.state = "PLAYING"
            return True
        except Exception:
            self._process = None
            self.state = "STOPPED"
            return False

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        if _AUDIO_BACKEND == "pydub" and self._play_obj is not None:
            try:
                self._play_obj.stop()
            finally:
                self._play_obj = None
        if self._process is not None:
            try:
                self._process.terminate()
            finally:
                self._process = None
        self.state = "STOPPED"

    def pause(self) -> None:
        # 暂无真正暂停能力，等同于停止
        self.stop()

    def resume(self, text: str) -> None:
        # 暂无真正恢复能力，重新播放当前文本
        self.play_text(text, autoplay=True)

    def refresh_state(self) -> None:
        """检查底层播放器状态，更新为 STOPPED（用于检测播放结束）。"""
        with self._lock:
            if _AUDIO_BACKEND == "pydub" and self._play_obj is not None:
                try:
                    if not self._play_obj.is_playing():
                        self._stop_locked()
                except Exception:
                    pass
            if self._process is not None and self._process.poll() is not None:
                self._stop_locked()
