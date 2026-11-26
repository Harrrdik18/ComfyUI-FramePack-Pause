# ComfyUI-FramePack-Pause

Experimental cooperative Pause / Resume controls for the UniPC sampler used by [Kijai's ComfyUI-FramePackWrapper](https://github.com/kijai/ComfyUI-FramePackWrapper).

**Status: experimental MVP.** Unit tests cover the pause gate and import hook, but a real GPU-backed FramePack run is still required before treating this as production-ready.

## What it does

- Adds a FramePack Pause sidebar panel and menu commands.
- Adds local ComfyUI API endpoints for pause, resume and status.
- Hooks the module-level `trange` iterator used by Kijai's `FlowMatchUniPC.sample()`.
- Pauses at sampler-iteration boundaries, keeping Python tensors and sampler history in memory.
- Does not modify or replace Kijai's custom node files.

## What pause means

Pause is cooperative: an in-progress CUDA/model operation finishes, then the sampler waits before starting the next iteration. Resume releases it. This retains the model, current latent and sampler history in memory; it does **not** free VRAM, create a disk checkpoint, survive a ComfyUI restart, or guarantee recovery after a crash.

If Pause is pressed while idle, it is armed and the next matching FramePack sampler waits at its first checkpoint until Resume.

## Compatibility

The initial adapter targets Kijai's `diffusers_helper/k_diffusion/uni_pc_fm.py`, the `FlowMatchUniPC` class and its module-level `trange` iterator. Other FramePack implementations and future upstream refactors are not guaranteed.

## Install

1. Install Kijai's ComfyUI-FramePackWrapper.
2. Clone this repository into the same `ComfyUI/custom_nodes` directory:

   ```bash
   git clone https://github.com/Harrrdik18/ComfyUI-FramePack-Pause.git
   ```

3. Restart ComfyUI and refresh the browser.
4. Open the **FramePack Pause** sidebar panel. Check that the Kijai sampler hook is detected.

No additional Python dependencies are intended beyond ComfyUI's own environment.

## Use

- **Pause**: finish the current sampler iteration, then wait.
- **Resume**: continue from the next iteration.
- **Refresh status**: check hook detection, active sampler and step count.

API endpoints:

- `POST /framepack-pause/pause`
- `POST /framepack-pause/resume`
- `GET /framepack-pause/status`

Do not expose your ComfyUI server to untrusted networks.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```

Unit tests do not load ComfyUI or a GPU. Manual end-to-end FramePack validation is still required.

## Roadmap

- [x] Cooperative pause controller
- [x] Kijai UniPC iterator adapter
- [x] ComfyUI API endpoints
- [x] Initial sidebar and menu controls
- [x] Unit tests and CI workflow
- [ ] Validate frontend API compatibility across ComfyUI builds
- [ ] End-to-end FramePack GPU test
- [ ] Handle ComfyUI interrupt / shutdown while paused
- [ ] Investigate checkpoint resume and optional VRAM offload

## License and attribution

This project integrates with an existing FramePack installation and does not bundle Kijai's implementation. Upstream files retain their own license and attribution. This project is licensed under MIT; see [LICENSE](LICENSE).
