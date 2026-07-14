from __future__ import annotations

import errno
import os
import pty
import select
import signal
import stat
import sys
import termios
import time
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / "install.sh"
TOKEN_PROMPT = "Токен Telegram-бота от @BotFather: ".encode()
IDS_PROMPT = "Разрешённые Telegram ID через запятую: ".encode()
SUCCESS_MESSAGE = "Конфигурация сохранена".encode()
FAKE_TOKEN = b"123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcd"
FAKE_IDS = b"123456789,987654321"


def _spawn_installer(env_file: Path, *, reconnect_piped_stdin: bool = False) -> tuple[int, int]:
    pid, master_fd = pty.fork()
    if pid == 0:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os.tcsetpgrp(0, os.getpgrp())
        environment = os.environ.copy()
        environment["EXPENSE_BOT_ENV_FILE"] = str(env_file)
        if reconnect_piped_stdin:
            os.execvpe(
                "bash",
                [
                    "bash",
                    "-c",
                    'printf "must-not-be-read\\n" | exec bash "$1" --configure-only </dev/tty',
                    "bash",
                    str(INSTALLER),
                ],
                environment,
            )
        os.execvpe(
            "bash",
            ["bash", str(INSTALLER), "--configure-only"],
            environment,
        )
    return pid, master_fd


def _read_until(master_fd: int, needle: bytes, timeout: float = 5.0) -> bytes:
    output = bytearray()
    deadline = time.monotonic() + timeout

    while needle not in output and time.monotonic() < deadline:
        readable, _, _ = select.select([master_fd], [], [], 0.1)
        if not readable:
            continue
        try:
            chunk = os.read(master_fd, 4096)
        except OSError as error:
            if error.errno == errno.EIO:
                break
            raise
        if not chunk:
            break
        output.extend(chunk)

    assert needle in output, output.decode(errors="replace")
    return bytes(output)


def _wait_for_exit(pid: int, timeout: float = 5.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        waited_pid, status = os.waitpid(pid, os.WNOHANG)
        if waited_pid == pid:
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
            if os.WIFSIGNALED(status):
                return 128 + os.WTERMSIG(status)
        time.sleep(0.05)
    raise TimeoutError("installer process did not exit")


def _stop_process(pid: int) -> None:
    try:
        waited_pid, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return
    if waited_pid == pid:
        return

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        _wait_for_exit(pid)
    except (ChildProcessError, TimeoutError):
        pass


def test_installer_reads_secret_without_echo_and_continues(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    pid, master_fd = _spawn_installer(env_file, reconnect_piped_stdin=True)

    try:
        transcript = _read_until(master_fd, TOKEN_PROMPT)
        os.write(master_fd, FAKE_TOKEN + b"\n")
        transcript += _read_until(master_fd, IDS_PROMPT)

        assert FAKE_TOKEN not in transcript

        os.write(master_fd, FAKE_IDS + b"\n")
        _read_until(master_fd, SUCCESS_MESSAGE)
        assert _wait_for_exit(pid) == 0

        contents = env_file.read_text()
        assert f"TELEGRAM_BOT_TOKEN={FAKE_TOKEN.decode()}" in contents
        assert f"ALLOWED_TELEGRAM_USER_IDS={FAKE_IDS.decode()}" in contents
        assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    finally:
        _stop_process(pid)
        os.close(master_fd)


@unittest.skipIf(
    sys.platform == "darwin",
    "macOS Python PTYs do not deliver terminal-generated SIGINT reliably",
)
def test_installer_ctrl_c_exits_and_restores_echo(tmp_path: Path) -> None:
    pid, master_fd = _spawn_installer(tmp_path / ".env")

    try:
        _read_until(master_fd, TOKEN_PROMPT)
        foreground_process_group = os.tcgetpgrp(master_fd)
        assert foreground_process_group == pid
        os.write(master_fd, b"\x03")

        assert _wait_for_exit(pid) == 130
        terminal_flags = termios.tcgetattr(master_fd)[3]
        assert terminal_flags & termios.ECHO
    finally:
        _stop_process(pid)
        os.close(master_fd)
