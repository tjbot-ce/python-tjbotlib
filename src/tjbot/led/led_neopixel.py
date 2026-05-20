"""NeoPixel LED controller using a privileged helper subprocess (RPi 3/4)."""

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Optional

from ..utils.errors import TJBotError
from ..utils.logging import LogEmoji, get_logger

_logger = get_logger(__name__)
_EMO = LogEmoji.LED

_HELPER_SCRIPT = Path(__file__).parent / "led_neopixel_ws281x.py"

_SUDO_MESSAGE = """
The NeoPixel LED on Raspberry Pi 3/4 requires elevated hardware access.
TJBot will now request sudo authentication to launch a dedicated LED helper
process. This is a one-time authentication per session.
"""


class LEDNeopixel:
    """Drives a ws281x NeoPixel LED via a root subprocess.

    On RPi 3/4, rpi_ws281x requires root privileges for PWM/DMA access. This
    class spawns ``led_neopixel_ws281x.py`` under ``sudo`` and communicates
    with it over newline-delimited JSON on stdin/stdout — matching the pattern
    used by the Node.js implementation.
    """

    def __init__(self, pin: int) -> None:
        self._helper: Optional[subprocess.Popen] = None
        self._pending: dict[int, Future] = {}
        self._pending_lock = threading.Lock()
        self._next_id = 1
        self._helper_dead: Optional[TJBotError] = None
        self._stderr_tail: list[str] = []
        self._ready = threading.Event()
        self._ready_error: Optional[Exception] = None

        is_root = os.geteuid() == 0

        if is_root:
            spawn_cmd = [sys.executable, str(_HELPER_SCRIPT)]
        else:
            # Probe whether passwordless sudo is available.
            probe = subprocess.run(["sudo", "-n", "true"], capture_output=True)
            if probe.returncode != 0:
                print(_SUDO_MESSAGE)
                auth = subprocess.run(["sudo", "-v"])
                if auth.returncode != 0:
                    raise TJBotError(
                        "sudo authentication failed. The NeoPixel LED requires root privileges on "
                        "Raspberry Pi 3/4. Enable passwordless sudo or run `sudo -v` before "
                        "starting TJBot."
                    )
            spawn_cmd = ["sudo", "-n", sys.executable, str(_HELPER_SCRIPT)]

        _logger.debug("%s spawning NeoPixel helper: %s", _EMO, " ".join(spawn_cmd))

        self._helper = subprocess.Popen(
            spawn_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self._stderr_thread.start()

        import atexit

        atexit.register(self._kill_helper)

        # Fire the init command; initialize() blocks until the response arrives.
        threading.Thread(target=self._do_init, args=(pin,), daemon=True).start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Block until the helper has finished initialising the LED hardware."""
        self._ready.wait()
        if self._ready_error is not None:
            raise self._ready_error

    def render(self, color: int) -> None:
        """Set the LED to *color* (24-bit 0xRRGGBB integer)."""
        self.initialize()
        self._send_and_wait({"cmd": "render", "color": color}, timeout=2.0)

    def cleanup(self) -> None:
        """Turn off the LED and shut down the helper process."""
        if self._helper_dead is not None:
            return
        try:
            self._send_and_wait({"cmd": "shutdown"}, timeout=2.0)
        except Exception:
            pass
        finally:
            self._kill_helper()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _do_init(self, pin: int) -> None:
        try:
            self._send_and_wait({"cmd": "init", "pin": pin, "numLeds": 1}, timeout=10.0)
            self._ready.set()
        except Exception as e:
            self._ready_error = e
            self._ready.set()

    def _send_and_wait(self, payload: dict, timeout: float) -> None:
        """Write a command to the helper and block until the response arrives."""
        if self._helper_dead is not None:
            raise self._helper_dead

        future: Future = Future()
        with self._pending_lock:
            msg_id = self._next_id
            self._next_id += 1
            self._pending[msg_id] = future

        try:
            data = json.dumps({**payload, "id": msg_id}) + "\n"
            assert self._helper is not None and self._helper.stdin is not None
            self._helper.stdin.write(data.encode())
            self._helper.stdin.flush()
        except Exception as exc:
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise TJBotError(
                f"failed to send '{payload.get('cmd')}' to NeoPixel helper: {exc}"
            ) from exc

        try:
            future.result(timeout=timeout)
        except TimeoutError:
            with self._pending_lock:
                self._pending.pop(msg_id, None)
            raise TJBotError(
                f"NeoPixel helper timed out waiting for '{payload.get('cmd')}' "
                f"response ({timeout}s)"
            )

    def _read_loop(self) -> None:
        assert self._helper is not None and self._helper.stdout is not None
        try:
            for raw in self._helper.stdout:
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self._handle_response(line)
        except Exception:
            pass

        # Helper process exited.
        code = self._helper.wait()
        stderr_summary = " | ".join(self._stderr_tail)
        msg = f"NeoPixel helper exited unexpectedly (code={code})"
        if stderr_summary:
            msg += f"; stderr: {stderr_summary}"
        self._helper_dead = TJBotError(msg)

        with self._pending_lock:
            pending = dict(self._pending)
            self._pending.clear()
        for fut in pending.values():
            if not fut.done():
                fut.set_exception(self._helper_dead)

    def _stderr_loop(self) -> None:
        assert self._helper is not None and self._helper.stderr is not None
        try:
            for raw in self._helper.stderr:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    sys.stderr.write(line + "\n")
                    self._stderr_tail.append(line)
                    if len(self._stderr_tail) > 8:
                        self._stderr_tail = self._stderr_tail[-8:]
        except Exception:
            pass

    def _handle_response(self, line: str) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _logger.warning("%s NeoPixel helper sent unparseable response: %s", _EMO, line)
            return

        msg_id = msg.get("id")
        with self._pending_lock:
            future = self._pending.pop(msg_id, None)

        if future is None or future.done():
            return

        if msg.get("ok"):
            future.set_result(None)
        else:
            future.set_exception(
                TJBotError(f"NeoPixel helper error: {msg.get('error', 'unknown')}")
            )

    def _kill_helper(self) -> None:
        if self._helper is not None and self._helper.poll() is None:
            try:
                if self._helper.stdin:
                    self._helper.stdin.close()
            except Exception:
                pass
            try:
                self._helper.terminate()
            except Exception:
                pass
