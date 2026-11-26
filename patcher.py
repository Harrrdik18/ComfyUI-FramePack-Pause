"""Runtime adapters for Kijai's FramePack sampler and pipeline callbacks."""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import inspect
import logging
from functools import wraps
import sys
from types import ModuleType
from typing import Any

try:
    from .pause_controller import CONTROLLER
    from .node_hook import patch_framepack_node_module, patch_registered_framepack_nodes
except ImportError:
    from pause_controller import CONTROLLER
    from node_hook import patch_framepack_node_module, patch_registered_framepack_nodes

LOGGER = logging.getLogger("ComfyUI-FramePack-Pause")
SAMPLER_SUFFIX = "diffusers_helper.k_diffusion.uni_pc_fm"
PIPELINE_SUFFIX = "diffusers_helper.pipelines.k_diffusion_hunyuan"
_PATCHED_SAMPLER_MODULES: set[str] = set()
_PATCHED_PIPELINE_MODULES: set[str] = set()


def patch_sampler_module(module: ModuleType) -> bool:
    """Pause between UniPC iterations without changing its sampling algorithm."""
    if not hasattr(module, "FlowMatchUniPC") or not hasattr(module, "trange"):
        return False
    original = module.trange
    if getattr(original, "__framepack_pause_wrapped__", False):
        _PATCHED_SAMPLER_MODULES.add(getattr(module, "__name__", "<unknown>"))
        return True

    @wraps(original)
    def pausable_trange(*args: Any, **kwargs: Any):
        count = kwargs.get("iterable")
        if count is None and args:
            count = args[0]
        total_steps = count if isinstance(count, int) and count >= 0 else None

        def iterate():
            with CONTROLLER.sampler_loop(total_steps):
                iterator = iter(original(*args, **kwargs))
                try:
                    next_item = next(iterator)
                except StopIteration:
                    return
                while True:
                    CONTROLLER.wait_if_paused()
                    yield next_item
                    try:
                        # This resumes only after the current model iteration and
                        # its callback have completed. It also detects the final
                        # item before waiting, avoiding a pause after the last step.
                        next_item = next(iterator)
                    except StopIteration:
                        return

        return iterate()

    setattr(pausable_trange, "__framepack_pause_wrapped__", True)
    module.trange = pausable_trange
    name = getattr(module, "__name__", "<unknown>")
    _PATCHED_SAMPLER_MODULES.add(name)
    LOGGER.info("Installed FramePack sampler pause hook in %s", name)
    return True


def patch_pipeline_module(module: ModuleType) -> bool:
    """Scale Kijai's callback to whole-video denoising progress across sections."""
    original = getattr(module, "sample_hunyuan", None)
    if not callable(original):
        return False
    if getattr(original, "__framepack_pause_progress_wrapped__", False):
        _PATCHED_PIPELINE_MODULES.add(getattr(module, "__name__", "<unknown>"))
        return True
    signature = inspect.signature(original)

    @wraps(original)
    def with_aggregate_progress(*args: Any, __original=original, __signature=signature, **kwargs: Any):
        try:
            bound = __signature.bind_partial(*args, **kwargs)
            callback = bound.arguments.get("callback")
        except TypeError:
            bound = None
            callback = kwargs.get("callback")
        if not callable(callback):
            return __original(*args, **kwargs)

        def aggregate_callback(step, x0, x, total_steps):
            state = CONTROLLER.snapshot()
            try:
                local_step = int(step)
                local_total = int(total_steps)
            except (TypeError, ValueError):
                callback(step, x0, x, total_steps)
                return

            if state["job_active"] and state["total_sections"]:
                section = max(1, int(state["section"] or 1))
                total_sections = int(state["total_sections"])
                adjusted_step = (section - 1) * local_total + local_step
                adjusted_total = total_sections * local_total
                CONTROLLER.set_step(local_step + 1, local_total)
                callback(adjusted_step, x0, x, adjusted_total)
            else:
                CONTROLLER.set_step(local_step + 1, local_total)
                callback(step, x0, x, total_steps)

        if bound is not None:
            bound.arguments["callback"] = aggregate_callback
            return __original(*bound.args, **bound.kwargs)
        kwargs["callback"] = aggregate_callback
        return __original(*args, **kwargs)

    setattr(with_aggregate_progress, "__framepack_pause_progress_wrapped__", True)
    module.sample_hunyuan = with_aggregate_progress
    name = getattr(module, "__name__", "<unknown>")
    _PATCHED_PIPELINE_MODULES.add(name)
    LOGGER.info("Installed whole-video progress hook in %s", name)
    return True


def is_sampler_patched() -> bool:
    return bool(_PATCHED_SAMPLER_MODULES)


def is_pipeline_patched() -> bool:
    return bool(_PATCHED_PIPELINE_MODULES)


def patched_modules() -> list[str]:
    return sorted(_PATCHED_SAMPLER_MODULES | _PATCHED_PIPELINE_MODULES)


class _PatchingLoader(importlib.abc.Loader):
    def __init__(self, wrapped_loader: Any) -> None:
        self._wrapped_loader = wrapped_loader

    def create_module(self, spec):
        create = getattr(self._wrapped_loader, "create_module", None)
        return create(spec) if create else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped_loader.exec_module(module)
        patch_sampler_module(module)
        patch_pipeline_module(module)
        patch_framepack_node_module(module)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped_loader, name)


class _PatchingFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        should_patch = (
            fullname == SAMPLER_SUFFIX
            or fullname.endswith("." + SAMPLER_SUFFIX)
            or fullname == PIPELINE_SUFFIX
            or fullname.endswith("." + PIPELINE_SUFFIX)
        )
        if not should_patch:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        if not isinstance(spec.loader, _PatchingLoader):
            spec.loader = _PatchingLoader(spec.loader)
        return spec


def install_import_hook() -> None:
    """Patch already-loaded Kijai modules and intercept future imports."""
    for name, module in tuple(sys.modules.items()):
        if not isinstance(module, ModuleType):
            continue
        if name.endswith(SAMPLER_SUFFIX):
            patch_sampler_module(module)
        elif name.endswith(PIPELINE_SUFFIX):
            patch_pipeline_module(module)
    if not any(isinstance(item, _PatchingFinder) for item in sys.meta_path):
        sys.meta_path.insert(0, _PatchingFinder())
        LOGGER.info("FramePack Pause import hooks installed")
