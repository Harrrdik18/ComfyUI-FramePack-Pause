# Changelog

## 0.2.0 — Aggregate progress and interrupt safety

- Aggregate denoising progress across all FramePack latent sections.
- Forward whole-video step counts to Kijai's ComfyUI preview/progress callback.
- Add live section/step/percentage display in the FramePack Pause sidebar.
- Discover and wrap registered FramePack node classes through ComfyUI's node registry.
- Check ComfyUI interrupts while paused and clear stale pause state after completion, failure or shutdown.
- Expand unit tests and CI coverage.
- Document exact progress semantics and the limitations of checkpointing and VRAM offload.

## 0.1.0 — Experimental initial implementation

- Add cooperative pause controller.
- Add runtime adapter for Kijai's FlowMatchUniPC iterator.
- Add ComfyUI API endpoints and frontend sidebar/menu controls.
- Add initial unit tests and GitHub Actions checks.
