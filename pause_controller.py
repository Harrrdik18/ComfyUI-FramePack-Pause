"""Thread-safe cooperative pause gate for FramePack sampler loops."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Event, Lock
from typing import Iterator


class PauseController:
    """Wait at sampler checkpoints without interrupting an active CUDA operation."""

    def __init__(self) -> None:
        self._running = Event()
        self._running.set()
        self._lock = Lock()
        self._active_loops = 0
        self._step = 0
        self._total_steps: int | None = None

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    def wait_if_paused(self) -> None:
        self._running.wait()

    def set_step(self, step: int, total_steps: int | None) -> None:
        with self._lock:
            self._step = max(0, int(step))
            self._total_steps = total_steps

    @contextmanager
    def sampler_loop(self, total_steps: int | None = None) -> Iterator[None]:
        with self._lock:
            self._active_loops += 1
            self._step = 0
            self._total_steps = total_steps
        try:
            yield
        finally:
            with self._lock:
                self._active_loops = max(0, self._active_loops - 1)

    def snapshot(self) -> dict[str, int | bool | None]:
        with self._lock:
            return {
                "paused": not self._running.is_set(),
                "active": self._active_loops > 0,
                "active_loops": self._active_loops,
                "step": self._step,
                "total_steps": self._total_steps,
            }


CONTROLLER = PauseController()
