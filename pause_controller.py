"""Thread-safe cooperative pause and aggregate progress controller."""
from __future__ import annotations

import atexit
import sys
from contextlib import contextmanager
from threading import Event, Lock
from typing import Callable, Iterator


InterruptChecker = Callable[[], None]


def _check_comfyui_interrupt() -> None:
    """Raise ComfyUI's normal interrupt exception when one is pending."""
    module = sys.modules.get("comfy.model_management")
    checker = getattr(module, "throw_exception_if_processing_interrupted", None)
    if callable(checker):
        checker()


class PauseController:
    """Pause FramePack at sampler-iteration boundaries and track whole-job progress."""

    def __init__(self, poll_interval: float = 0.2) -> None:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")
        self._resume_event = Event()
        self._resume_event.set()
        self._lock = Lock()
        self._poll_interval = poll_interval
        self._active_loops = 0
        self._waiting_loops = 0
        self._job_active = False
        self._phase = "idle"
        self._step = 0
        self._total_steps: int | None = None
        self._section = 0
        self._total_sections: int | None = None
        self._progress_current = 0
        self._progress_total: int | None = None
        self._last_error: str | None = None

    def pause(self) -> None:
        """Pause at the next checkpoint; while idle, arm the next FramePack run."""
        with self._lock:
            self._resume_event.clear()

    def resume(self) -> None:
        """Resume a paused sampler and clear any pending idle pause request."""
        with self._lock:
            self._resume_event.set()

    def shutdown(self) -> None:
        """Release a paused worker during interpreter shutdown."""
        self.resume()

    def wait_if_paused(self, check_interrupted: InterruptChecker | None = None) -> None:
        """Wait without holding the lock and periodically check ComfyUI interrupts."""
        checker = check_interrupted or _check_comfyui_interrupt
        with self._lock:
            if self._resume_event.is_set():
                return
            self._waiting_loops += 1
        try:
            while not self._resume_event.wait(self._poll_interval):
                checker()
            checker()
        finally:
            with self._lock:
                self._waiting_loops = max(0, self._waiting_loops - 1)

    @contextmanager
    def framepack_job(self, total_sections: int, steps_per_section: int) -> Iterator[None]:
        """Track one FramePackSampler call, including every generated latent section."""
        total_sections = max(1, int(total_sections))
        steps_per_section = max(1, int(steps_per_section))
        with self._lock:
            self._job_active = True
            self._phase = "preparing"
            self._step = 0
            self._total_steps = steps_per_section
            self._section = 0
            self._total_sections = total_sections
            self._progress_current = 0
            self._progress_total = total_sections * steps_per_section
            self._last_error = None
        try:
            yield
        except BaseException as exc:
            with self._lock:
                self._phase = "interrupted"
                self._last_error = f"{type(exc).__name__}: {exc}"
            raise
        else:
            with self._lock:
                self._phase = "complete"
                if self._progress_total is not None:
                    self._progress_current = self._progress_total
                self._step = self._total_steps or self._step
        finally:
            with self._lock:
                self._job_active = False
                self._active_loops = 0
                self._waiting_loops = 0
                self._resume_event.set()

    @contextmanager
    def sampler_loop(self, total_steps: int | None = None) -> Iterator[None]:
        """Track one UniPC pass (one FramePack latent section)."""
        with self._lock:
            self._active_loops += 1
            self._step = 0
            if total_steps is not None:
                self._total_steps = total_steps
            if self._job_active:
                self._section = min(
                    self._section + 1,
                    self._total_sections or self._section + 1,
                )
                self._phase = "denoising"
                if self._progress_total is None and total_steps is not None:
                    self._progress_total = (self._total_sections or 1) * total_steps
        try:
            yield
        finally:
            with self._lock:
                self._active_loops = max(0, self._active_loops - 1)

    def set_step(self, completed_steps: int, total_steps: int | None) -> None:
        """Record steps completed in the current section and aggregate job progress."""
        with self._lock:
            self._step = max(0, int(completed_steps))
            if total_steps is not None:
                self._total_steps = int(total_steps)
            if self._job_active:
                sections = self._total_sections or 1
                steps = self._total_steps or total_steps or 1
                section_base = max(0, self._section - 1) * steps
                self._progress_total = sections * steps
                self._progress_current = min(
                    section_base + self._step,
                    self._progress_total,
                )
            else:
                self._progress_current = self._step
                self._progress_total = total_steps

    def snapshot(self) -> dict[str, int | bool | float | str | None]:
        with self._lock:
            progress_percent = 0.0
            if self._progress_total:
                progress_percent = round(
                    min(100.0, self._progress_current * 100.0 / self._progress_total),
                    1,
                )
            return {
                "paused": self._waiting_loops > 0,
                "pause_requested": not self._resume_event.is_set(),
                "active": self._job_active or self._active_loops > 0,
                "job_active": self._job_active,
                "active_loops": self._active_loops,
                "waiting_loops": self._waiting_loops,
                "phase": self._phase,
                "step": self._step,
                "total_steps": self._total_steps,
                "section": self._section,
                "total_sections": self._total_sections,
                "progress_current": self._progress_current,
                "progress_total": self._progress_total,
                "progress_percent": progress_percent,
                "last_error": self._last_error,
            }


CONTROLLER = PauseController()
atexit.register(CONTROLLER.shutdown)
