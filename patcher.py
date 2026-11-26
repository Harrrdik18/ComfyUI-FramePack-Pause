"""Runtime adapters for Kijai's FramePack sampler and node classes."""
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
    from .node_hook import patch_framepack_node_module
except ImportError:
    from pause_controller import CONTROLLER
    from node_hook import patch_framepack_node_module

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
                # Fetch each step lazily; after yielding a step, the next call
                # waits before the following step reaches the sampler.
                for index in original(*args, **kwargs):
                    CONTROLLER.wait_if_paused()
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
        patch_framepack_node_module(module)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped_loader, name)


class _PatchingFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        is_sampler = fullname == MODULE_SUFFIX or fullname.endswith("." + MODULE_SUFFIX)
        # Kijai's custom node imports the FramePackSampler classes from its
        # package's nodes.py; inspect modules named "nodes" without changing
        # unrelated modules unless they actually export FramePackSampler.
        is_node_module = fullname == "nodes" or fullname.endswith(".nodes")
        if not (is_sampler or is_node_module):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec
        if not isinstance(spec.loader, _PatchingLoader):
            spec.loader = _PatchingLoader(spec.loader)
        return spec


def install_import_hook() -> None:
    """Patch loaded modules and intercept future sampler/node imports."""
    for module in tuple(sys.modules.values()):
        if isinstance(module, ModuleType):
            patch_sampler_module(module)
            patch_framepack_node_module(module)
    if not any(isinstance(item, _PatchingFinder) for item in sys.meta_path):
        sys.meta_path.insert(0, _PatchingFinder())
        LOGGER.info("FramePack Pause import hooks installed")
