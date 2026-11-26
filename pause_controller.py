"""Thread-safe cooperative pause gate for FramePack sampler loops.

The gate is deliberately outside the model/sampling math. It blocks the worker
between UniPC iterations and leaves the live latent and sampler history intact.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from threading import Event, Lock
from typing import Callable, Iterator


InterruptChecker = Callable[[], None]


def _check_comfyui_interrupt() -> None:
    """Ask ComfyUI to raise its normal interrupt exception when available."""
    module = sys.modules.get("comfy.model_management")
    checker = getattr(module, "throw_exception_if_processing_interrupted", None)
    if callable(checker):
        checker()


class PauseController:
    """Wait at sampler checkpoints while remaining responsive to ComfyUI stop."""

    def __init__(self, poll_interval: float = 0.2) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")
        self._resume_event = Event()
        self._resume_event.set()
        self._lock = Lock()
        self._poll_interval = poll_interval
        self._active_loops = 0
        self._waiting_loops = 0
        self._step = 0
        self._total_steps: int | None = None

    def pause(self) -> None:
        """Request a pause at the next sampler checkpoint.

        Calling this while idle arms the pause for the next FramePack run.
        """
        with self._lock:
            self._resume_event.clear()

    def resume(self) -> None:
        """Release any paused sampler and clear an idle pause request."""
        with self._lock:
            self._resume_event.set()

    def shutdown(self) -> None:
        """Unblock a waiting sampler during orderly interpreter shutdown."""
        self.resume()

    def wait_if_paused(
        self,
        check_interrupted: InterruptChecker | None = None,
    ) -> None:
        """Block while paused, checking ComfyUI's interrupt state periodically."""
        checker = check_interrupted or _check_comfyui_interrupt
        with self._lock:
            if self._resume_event.is_set():
                return
            self._waiting_loops += 1

        try:
            while not self._resume_event.wait(self._poll_interval):
                checker()
            # An interrupt may have arrived immediately before Resume.
            checker()
        finally:
            with self._lock:
                self._waiting_loops = max(0, self._waiting_loops - 1)

    @contextmanager
    def sampler_loop(self, total_steps: int | None = None) -> Iterator[None]:
        """Track one sampler invocation and release stale pause on its exit."""
        with self._lock:
            if self._active_loops == 0:
                self._step = 0
                self._total_steps = total_steps
            self._active_loops += 1
            if total_steps is not None:
                self._total_steps = total_steps
        try:
            yield
        finally:
            with self._lock:
                self._active_loops = max(0, self._active_loops - 1)
                if self._active_loops == 0:
                    # A completed or interrupted job must not poison the next job.
                    self._resume_event.set()

    def set_step(self, step: int, total_steps: int | None) -> None:
        with self._lock:
            self._step = max(0, int(step))
            self._total_steps = total_steps

    def snapshot(self) -> dict[str, int | bool | None]:
        with self._lock:
            pause_requested = not self._resume_event.is_set()
            waiting = self._waiting_loops
            return {
                "paused": waiting > 0,
                "pause_requested": pause_requested,
                "active": self._active_loops > 0,
                "active_loops": self._active_loops,
                "waiting_loops": waiting,
                "step": self._step,
                "total_steps": self._total_steps,
            }


CONTROLLER = PauseController()
