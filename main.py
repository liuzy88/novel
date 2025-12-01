from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

import cache
from book import Book, load_book
from config import Config, CONFIG_PATH, load_config, save_config, validate_rate
from progress import load_progress, save_progress
from player import Player


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def settings_mode() -> None:
    config = load_config()
    print("=== 小说阅读播放器：设置模式 ===")
    print(f"当前 voice: {config.voice}")
    print(f"当前 rate : {config.rate}")
    print("按回车保留原值。")

    new_voice = input("输入新的 voice (示例 zh-CN-YunxiNeural): ").strip()
    if new_voice:
        config.voice = new_voice

    while True:
        new_rate = input("输入新的 rate (示例 +20% / -10%): ").strip()
        if not new_rate:
            break
        if validate_rate(new_rate):
            config.rate = new_rate
            break
        print("格式错误，请按 +20% 或 -10% 这种格式输入。")

    save_config(config)
    print(f"配置已保存到 {CONFIG_PATH}")


def reading_mode(txt_path: str) -> None:
    config = load_config()
    try:
        book = load_book(txt_path, split_type=config.split_type)
    except Exception as exc:
        print(f"加载文本失败：{exc}")
        return

    if not book.segments:
        print("未找到可阅读的内容。")
        return

    player = Player(config.voice, config.rate)
    resolved_path = Path(txt_path).expanduser().resolve()
    current_idx = _load_start_index(resolved_path, book, config)
    _preload_and_play(book, current_idx, config, player, autoplay=True)
    save_progress(resolved_path, config.split_type, current_idx)

    prev_state = player.state
    redraw = True
    manual_stop = False

    try:
        while True:
            if redraw:
                clear_screen()
                render(book, current_idx, player, config)
                redraw = False

            key = read_key(timeout=0.2)
            manual_stop = False

            if key == "ESC":
                player.stop()
                break
            if key in {"UP", "LEFT"} and current_idx > 0:
                current_idx -= 1
                _preload_and_play(book, current_idx, config, player, autoplay=True)
                save_progress(resolved_path, config.split_type, current_idx)
                redraw = True
            elif key in {"DOWN", "RIGHT"} and current_idx < len(book.segments) - 1:
                current_idx += 1
                _preload_and_play(book, current_idx, config, player, autoplay=True)
                save_progress(resolved_path, config.split_type, current_idx)
                redraw = True
            elif key == "SPACE":
                segment_text = book.segments[current_idx].text
                if player.state == "PLAYING":
                    manual_stop = True
                    player.stop()
                    redraw = True
                else:
                    if not _play_segment(segment_text, player):
                        break
                    redraw = True

            player.refresh_state()
            if prev_state == "PLAYING" and player.state == "STOPPED" and not manual_stop:
                if current_idx < len(book.segments) - 1:
                    current_idx += 1
                    _preload_and_play(book, current_idx, config, player, autoplay=True)
                    save_progress(resolved_path, config.split_type, current_idx)
                    redraw = True
            if player.state != prev_state:
                redraw = True
            prev_state = player.state
    except KeyboardInterrupt:
        player.stop()
        print("\n已退出。")
    save_progress(resolved_path, config.split_type, current_idx)


def _preload_neighbors(book: Book, index: int, config: Config) -> None:
    window = config.preload_segments
    texts = []
    for offset in range(1, window + 1):
        prev_idx = index - offset
        next_idx = index + offset
        if prev_idx >= 0:
            texts.append(book.segments[prev_idx].text)
        if next_idx < len(book.segments):
            texts.append(book.segments[next_idx].text)
    cache.preload_segments(texts, config.voice, config.rate)

def _load_start_index(path: Path, book: Book, config: Config) -> int:
    stored = load_progress(path, config.split_type)
    if stored is None:
        return 0
    if 0 <= stored < len(book.segments):
        return stored
    return 0


def _play_segment(text: str, player: Player) -> bool:
    try:
        player.play_text(text, autoplay=True)
        return True
    except Exception as exc:
        print(f"播放失败：{exc}")
        return False


def _preload_and_play(book: Book, index: int, config: Config, player: Player, autoplay: bool) -> None:
    player.stop()
    _preload_neighbors(book, index, config)
    if autoplay:
        _play_segment(book.segments[index].text, player)


def render(book: Book, current_idx: int, player: Player, config: Config) -> None:
    current_segment = book.segments[current_idx]
    status_line = (
        f"[{book.title or '未命名'}] 段 {current_idx + 1} / {len(book.segments)} "
        f"| 状态: {player.state} | voice: {config.voice} | rate: {config.rate}"
    )
    print(status_line)
    print()
    print(current_segment.text)
    print("\n" + "-" * 50)
    print("Ctrl C: 退出  ←上一段  →下一段  空格: 播放/暂停")


def read_key(timeout: float | None = None) -> Optional[str]:
    """读取按键，支持超时返回 None。"""
    if os.name == "nt":
        import msvcrt

        if timeout is None:
            ch = msvcrt.getch()
            return _parse_windows_key(ch, msvcrt)

        end = time.time() + timeout
        while time.time() < end:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                return _parse_windows_key(ch, msvcrt)
            time.sleep(0.02)
        return None

    import tty
    import termios
    import select

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        rlist, _, _ = select.select([fd], [], [], timeout)
        if not rlist:
            return None
        ch1 = sys.stdin.read(1)
        if ch1 == "\x1b":
            if select.select([fd], [], [], 0.01)[0]:
                ch2 = sys.stdin.read(1)
                if ch2 == "[" and select.select([fd], [], [], 0.01)[0]:
                    ch3 = sys.stdin.read(1)
                    mapping = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}
                    return mapping.get(ch3, "")
            return "ESC"
        if ch1 == " ":
            return "SPACE"
        if ch1 in {"\x03", "\x04"}:
            raise KeyboardInterrupt
        return ch1
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _parse_windows_key(ch: bytes, msvcrt_module) -> str:
    if ch in (b"\x1b",):
        return "ESC"
    if ch in (b"\x00", b"\xe0"):
        ch2 = msvcrt_module.getch()
        mapping = {b"H": "UP", b"P": "DOWN", b"K": "LEFT", b"M": "RIGHT"}
        return mapping.get(ch2, "")
    if ch == b" ":
        return "SPACE"
    return ch.decode(errors="ignore")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="小说阅读播放器（CLI 版）")
    parser.add_argument("txt", nargs="?", help="要朗读的 TXT 文件路径")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    if args.txt:
        reading_mode(args.txt)
    else:
        settings_mode()
