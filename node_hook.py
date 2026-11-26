"""FramePack node wrapper used to aggregate per-section sampler progress."""
from __future__ import annotations

import inspect
import logging
from functools import wraps
from types import ModuleType
from typing import Any

try:
    from .pause_controller import CONTROLLER
except ImportError:
    from pause_controller import CONTROLLER

LOGGER = logging.getLogger("ComfyUI-FramePack-Pause")
_PATCHED_CLASSES: set[str] = set()


def _section_count(arguments: dict[str, Any], class_name: str) -> int:
    if class_name == "FramePackSingleFrameSampler":
        return 1
    try:
        seconds = float(arguments.get("total_second_length", 5.0))
        window = max(1, int(arguments.get("latent_window_size", 9)))
        sections = int(max(round((seconds * 30.0) / (window * 4.0)), 1))
        return sections
    except (TypeError, ValueError, OverflowError):
        LOGGER.warning("Could not determine FramePack section count; using 1")
        return 1


def patch_framepack_node_module(module: ModuleType) -> bool:
    """Wrap Kijai's FramePack sampler node process methods, if present."""
    patched_any = False
    for class_name in ("FramePackSampler", "FramePackSingleFrameSampler"):
        node_class = getattr(module, class_name, None)
        if node_class is None:
            continue
        original = getattr(node_class, "process", None)
        if not callable(original):
            continue
        if getattr(original, "__framepack_pause_job_wrapped__", False):
            _PATCHED_CLASSES.add(class_name)
            patched_any = True
            continue

        @wraps(original)
        def wrapped(self, *args, __original=original, __class_name=class_name, **kwargs):
            try:
                signature = inspect.signature(__original)
                bound = signature.bind_partial(self, *args, **kwargs)
                bound.apply_defaults()
                arguments = bound.arguments
            except (TypeError, ValueError):
                arguments = kwargs

            sections = _section_count(arguments, __class_name)
            try:
                steps = max(1, int(arguments.get("steps", 1)))
            except (TypeError, ValueError, OverflowError):
                steps = 1

            with CONTROLLER.framepack_job(sections, steps):
                return __original(self, *args, **kwargs)

        setattr(wrapped, "__framepack_pause_job_wrapped__", True)
        setattr(node_class, "process", wrapped)
        _PATCHED_CLASSES.add(class_name)
        LOGGER.info("Installed aggregate progress hook on %s", class_name)
        patched_any = True
    return patched_any


def patched_node_classes() -> list[str]:
    return sorted(_PATCHED_CLASSES)
