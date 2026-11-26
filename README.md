# ComfyUI-FramePack-Pause

Cooperative Pause / Resume controls and whole-video denoising progress for [Kijai's ComfyUI-FramePackWrapper](https://github.com/kijai/ComfyUI-FramePackWrapper).

**Status: experimental 0.2.0.** Unit tests and GitHub Actions validate the controller, import adapters, node-registry integration and aggregate callback mapping. A live CUDA/FramePack run is still required before calling the integration production-ready.

## Features

- **Pause / Resume:** pause at a safe boundary between UniPC sampling iterations without discarding the live latent or sampler history.
- **Whole-video denoising progress:** aggregate per-step callback updates across all FramePack latent sections, rather than resetting the reported step count at each section.
- **ComfyUI progress callback:** scale Kijai's callback from `step / steps` within a section to `completed denoising steps / total denoising steps` for the whole video.
- **Sidebar controller:** live pause state, section/step, aggregate percentage and Pause/Resume controls.
- **API:** local ComfyUI endpoints for Pause, Resume and Status.
- **Interrupt-safe pause:** periodically check ComfyUI's interrupt flag while paused and release stale pause requests after completion or failure.
- **No edits to Kijai's files:** this extension uses narrow runtime adapters.

## Progress semantics

The percentage is **whole-video denoising progress**, calculated as:

```
completed denoising steps across sections
----------------------------------------- × 100
total latent sections × steps per section
```

Kijai's FramePack sampler can call the UniPC sampler repeatedly, once for each latent section. Its original preview callback reports the same per-section step range on every call; this extension offsets the callback step by the current section and increases the callback total to cover all sections.

The progress indicator does not include model loading, prompt/image preprocessing, latent preparation, VAE decoding or final video saving. Those phases can still make ComfyUI's overall workflow progress appear coarse. The sidebar labels the metric as denoising progress to avoid implying it represents every operation.

## Pause semantics and limitations

Pause is cooperative. The current CUDA/model operation finishes, then the sampling loop waits before starting the next iteration. Resume continues with the same in-memory latent and UniPC history.

- Pause does not interrupt an in-flight CUDA kernel.
- Model and latent tensors remain in memory. VRAM is **not** freed.
- Pause state is not a disk checkpoint and cannot survive a ComfyUI restart or process crash.
- A normal ComfyUI interrupt is checked while waiting; it aborts the current node through ComfyUI's regular interrupt mechanism.
- If Pause is clicked while idle, the next FramePack run is paused at its first sampler checkpoint until Resume.

## Compatibility

The initial adapter targets Kijai's `diffusers_helper/k_diffusion/uni_pc_fm.py` and `diffusers_helper/pipelines/k_diffusion_hunyuan.py`, plus the registered `FramePackSampler` and `FramePackSingleFrameSampler` node classes.

The node classes are discovered through ComfyUI's core `nodes.NODE_CLASS_MAPPINGS` registry after custom-node loading. The frontend uses ComfyUI's documented `registerSidebarTab` extension API and `api.fetchApi`.

Other FramePack implementations, alternate samplers, old frontend builds and future upstream refactors are not guaranteed. CI cannot replace a real ComfyUI + CUDA integration test.

## Install

1. Install [Kijai's ComfyUI-FramePackWrapper](https://github.com/kijai/ComfyUI-FramePackWrapper).
2. Clone this repository into the same `ComfyUI/custom_nodes` directory:

   ```bash
   git clone https://github.com/Harrrdik18/ComfyUI-FramePack-Pause.git
   ```

3. Restart ComfyUI Desktop completely.
4. Open the **FramePack Pause** sidebar once. The extension performs a backend registry scan at startup and when the Status endpoint is requested.
5. Check that the status reports the sampler, pipeline and FramePack node hooks as detected.

To update an existing clone:

```bash
git -C custom_nodes/ComfyUI-FramePack-Pause pull
```

No additional Python packages are intended beyond ComfyUI's own environment.

## Use

- **Pause:** request a pause at the next safe sampler boundary.
- **Resume:** release a paused sampler.
- **Refresh:** retrieve current hook, section, step and progress state.

The sidebar displays:
- hook detection status,
- current phase (preparing, denoising, complete or interrupted),
- current section and step,
- aggregate whole-video denoising percentage.

API endpoints (same ComfyUI host/port):

- `POST /framepack-pause/pause`
- `POST /framepack-pause/resume`
- `GET /framepack-pause/status`

Do not expose your ComfyUI server to untrusted networks. The endpoints are intended for the local ComfyUI frontend.

## Test

Run the unit tests in the Python environment used by ComfyUI:

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
node --input-type=module --check < web/framepack_pause.js
```

The tests do not require ComfyUI, PyTorch or a GPU. GitHub Actions runs the unit tests on supported Python versions and checks frontend syntax.

### Manual CUDA test checklist

1. Restart ComfyUI and open the FramePack Pause sidebar.
2. Verify `sampler_patched`, `pipeline_patched` and `node_patched` are all `true` in `/framepack-pause/status`.
3. Run a short FramePack generation with a small number of steps and a short output duration.
4. Confirm denoising progress advances across section boundaries instead of resetting to the first section's percentage.
5. Click Pause during denoising; wait 10 seconds and confirm the percentage/step remains unchanged.
6. Click Resume; confirm the same generation continues and completes.
7. Start another generation and use ComfyUI's normal Interrupt while paused; confirm it exits instead of remaining blocked.
8. Confirm the next queued FramePack generation is not left paused after the interrupted job.

GPU-backed manual validation is required before tagging a stable release.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). Keep the integration isolated from upstream files and do not vendor the FramePack sampler implementation.

## Roadmap

- [x] Cooperative pause controller and safe sampler checkpoints
- [x] Kijai UniPC sampler adapter
- [x] Aggregate progress across FramePack latent sections
- [x] Forward aggregate progress to ComfyUI's preview/progress callback
- [x] Live sidebar progress and Pause/Resume controls
- [x] ComfyUI node-registry discovery after startup
- [x] ComfyUI interrupt checks while paused
- [x] Clear stale pause state after completion, failure or shutdown
- [x] Unit tests and CI workflow
- [x] Document checkpoint/VRAM feasibility and limitations
- [ ] Run end-to-end GPU tests on Windows + CUDA and verify pause/resume, progress and interrupt behaviour
- [ ] Verify compatibility against multiple ComfyUI frontend and FramePackWrapper revisions

### Checkpoint and VRAM-offload research

This release deliberately retains the live sampler state in RAM/VRAM while paused. A real restart-safe checkpoint would need to serialize the current latent, UniPC model-history tensors, timestep history, current sigma/step, random-generator state and relevant model/pipeline configuration. A sampler-only snapshot is not enough to resume the whole FramePack node safely across latent sections. Similarly, moving a live transformer or its temporary state to CPU during a pause could conflict with ComfyUI's model management and Kijai's dynamic-swapping logic. These are separate engineering projects and are not advertised as supported features.

## License and attribution

This project is licensed under MIT; see [LICENSE](LICENSE). It does not bundle or copy Kijai's implementation. The upstream FramePackWrapper and its sampler retain their own license and attribution.
