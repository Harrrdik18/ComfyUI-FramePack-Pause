"""ComfyUI FramePack Pause extension entry point."""
from __future__ import annotations

import logging

from .patcher import install_import_hook
from .routes import register_routes

LOGGER = logging.getLogger("ComfyUI-FramePack-Pause")
WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

install_import_hook()
register_routes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
