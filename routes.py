"""Local ComfyUI HTTP endpoints for pause and whole-video progress status."""
from __future__ import annotations

import logging

from aiohttp import web
from server import PromptServer

try:
    from .pause_controller import CONTROLLER
    from .patcher import (
        is_pipeline_patched,
        is_sampler_patched,
        patched_modules,
        patch_registered_framepack_nodes,
    )
except ImportError:
    from pause_controller import CONTROLLER
    from patcher import (
        is_pipeline_patched,
        is_sampler_patched,
        patched_modules,
        patch_registered_framepack_nodes,
    )

LOGGER = logging.getLogger("ComfyUI-FramePack-Pause")
_REGISTERED = False


def _status_payload() -> dict:
    patched_nodes = patch_registered_framepack_nodes()
    state = CONTROLLER.snapshot()
    sampler_patched = is_sampler_patched()
    pipeline_patched = is_pipeline_patched()
    return {
        **state,
        "patched": sampler_patched,
        "sampler_patched": sampler_patched,
        "pipeline_patched": pipeline_patched,
        "node_patched": bool(patched_nodes),
        "patched_node_classes": patched_nodes,
        "patched_modules": patched_modules(),
    }


def register_routes() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    routes = PromptServer.instance.routes

    async def pause(request: web.Request) -> web.Response:
        CONTROLLER.pause()
        return web.json_response(_status_payload())

    async def resume(request: web.Request) -> web.Response:
        CONTROLLER.resume()
        return web.json_response(_status_payload())

    async def status(request: web.Request) -> web.Response:
        return web.json_response(_status_payload())

    routes.post("/framepack-pause/pause")(pause)
    routes.post("/framepack-pause/resume")(resume)
    routes.get("/framepack-pause/status")(status)
    _REGISTERED = True
    LOGGER.info("FramePack Pause API routes registered")
