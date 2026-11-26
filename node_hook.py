"""ComfyUI node-registry adapter for Kijai FramePack progress aggregation."""
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
TARGET_CLASSES = ("FramePackSampler", "FramePackSingleFrameSampler")


def _section_count(arguments: dict[str, Any], class_name: str) -> int:
    if class_name == "FramePackSingleFrameSampler":
        return 1
    try:
        seconds = float(arguments.get("total_second_length", 5.0))
        window = max(1, int(arguments.get("latent_window_size", 9)))
        return max(round((seconds * 30.0) / (window * 4.0)), 1)
    except (TypeError, ValueError, OverflowError):
        LOGGER.warning("Could not determine FramePack section count; using 1")
        return 1


def patch_framepack_class(node_class: type, class_name: str | None = None) -> bool:
    """Wrap a FramePack sampler class exactly once."""
    name = class_name or getattr(node_class, "__name__", "FramePackSampler")
    if name not in TARGET_CLASSES:
        return False
    original = getattr(node_class, "process", None)
    if not callable(original):
        return False
    if getattr(original, "__framepack_pause_job_wrapped__", False):
        _PATCHED_CLASSES.add(name)
        return True

    signature = inspect.signature(original)

    @wraps(original)
    def wrapped(self, *args, __original=original, __signature=signature, __name=name, **kwargs):
        try:
            bound = __signature.bind_partial(self, *args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
        except TypeError:
            arguments = kwargs
        sections = _section_count(arguments, __name)
        try:
            steps = max(1, int(arguments.get("steps", 1)))
        except (TypeError, ValueError, OverflowError):
            steps = 1
        with CONTROLLER.framepack_job(sections, steps):
            return __original(self, *args, **kwargs)

    setattr(wrapped, "__framepack_pause_job_wrapped__", True)
    setattr(node_class, "process", wrapped)
    _PATCHED_CLASSES.add(name)
    LOGGER.info("Installed whole-job progress hook on %s", name)
    return True


def patch_framepack_node_module(module: ModuleType) -> bool:
    """Patch class definitions when a FramePack node module is imported."""
    patched = False
    for class_name in TARGET_CLASSES:
        node_class = getattr(module, class_name, None)
        if isinstance(node_class, type):
            patched = patch_framepack_class(node_class, class_name) or patched
    return patched


def patch_registered_framepack_nodes() -> list[str]:
    """Patch classes after ComfyUI has registered all custom node mappings.

    ComfyUI loads custom-node packages directly from file locations, bypassing
    normal meta-path lookup for the package's own nodes.py. Its core 'nodes'
    registry is the reliable place to discover those registered classes.
    """
    import sys

    core_nodes = sys.modules.get("nodes")
    mapping = getattr(core_nodes, "NODE_CLASS_MAPPINGS", {}) if core_nodes else {}
    for mapping_name, node_class in tuple(mapping.items()):
        class_name = getattr(node_class, "__name__", "")
        if mapping_name in TARGET_CLASSES or class_name in TARGET_CLASSES:
            patch_framepack_class(node_class, mapping_name if mapping_name in TARGET_CLASSES else class_name)
    return sorted(_PATCHED_CLASSES)
