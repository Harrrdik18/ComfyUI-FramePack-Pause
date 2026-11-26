"""Narrow runtime adapter for Kijai's FlowMatchUniPC sampler."""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import logging
import sys
from functools import wraps
from types import ModuleType
from typing import Any

try:
    from .pause_controller import CONTROLLER
except ImportError:
    from pause_controller import CONTROLLER

LOGGER = logging.getLogger("ComfyUI-FramePack-Pause")
MODULE_SUFFIX = "diffusers_helper.k_diffusion.uni_pc_fm"
_PATCHED_MODULES: set[str] = set()


def patch_sampler_module(module: ModuleType) -> bool:
    """Wrap a compatible module's trange iterator; safe to call repeatedly."""
    if not hasattr(module, "FlowMatchUniPC") or not hasattr(module, "trange"):
        return False

    original = module.trange
    if getattr(original, "__framepack_pause_wrapped__", False):
        _PATCHED_MODULES.add(getattr(module, "__name__", "<unknown>"))
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
                while True:
                    # Wait before advancing tqdm/range, so progress isn't
                    # incremented until the next model evaluation can proceed.
                    CONTROLLER.wait_if_paused()
                    try:
                        index = next(iterator)
                    except StopIteration:
                        return
                    if isinstance(index, int):
                        CONTROLLER.set_step(index + 1, total_steps)
                    yield index

        return iterate()

    setattr(pausable_trange, "__framepack_pause_wrapped__", True)
    module.trange = pausable_trange
    name = getattr(module, "__name__", "<unknown>")
    _PATCHED_MODULES.add(name)
    LOGGER.info("Installed FramePack pause hook in %s", name)
    return True


def is_patched() -> bool:
    return bool(_PATCHED_MODULES)


def patched_modules() -> list[str]:
    return sorted(_PATCHED_MODULES)


class _PatchingLoader(importlib.abc.Loader):
    def __init__(self, wrapped_loader: Any) -> None:
        self._wrapped_loader = wrapped_loader

    def create_module(self, spec):
        create = getattr(self._wrapped_loader, "create_module", None)
        return create(spec) if create else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped_loader.exec_module(module)
        patch_sampler_module(module)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped_loader, name)


class _SamplerImportFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname != MODULE_SUFFIX and not fullname.endswith("." + MODULE_SUFFIX):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        if not isinstance(spec.loader, _PatchingLoader):
            spec.loader = _PatchingLoader(spec.loader)
        return spec


def install_import_hook() -> None:
    """Patch a loaded sampler and intercept future imports, idempotently."""
    for name, module in tuple(sys.modules.items()):
        if (name == MODULE_SUFFIX or name.endswith("." + MODULE_SUFFIX)) and isinstance(module, ModuleType):
            patch_sampler_module(module)
    if not any(isinstance(item, _SamplerImportFinder) for item in sys.meta_path):
        sys.meta_path.insert(0, _SamplerImportFinder())
        LOGGER.info("FramePack pause import hook installed")
