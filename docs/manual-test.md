# Manual Windows + CUDA acceptance test

This is the release gate for real FramePack integration. Unit tests and GitHub Actions cannot verify CUDA execution, Kijai model swapping, or the ComfyUI browser UI.

## Test environment

Record Windows version, ComfyUI Desktop version, frontend version, Kijai FramePackWrapper commit, FramePack Pause commit, GPU/VRAM and PyTorch version.

## 1. Verify installation and hooks

Open the FramePack Pause sidebar once after ComfyUI has fully started. Then run:

```powershell
.\scripts\test-api.ps1
```

Expected: sampler_patched, pipeline_patched and node_patched are all True, and the API pause/resume smoke test passes.

The maintainer has confirmed all three hook flags on one Windows installation. That confirms detection only; it is not an end-to-end render test.

## 2. Verify whole-video denoising progress

Use a short test workflow (for example, 3 seconds) with a modest number of sampling steps (for example, 6). Keep latent window and other settings fixed.

Open a second PowerShell window:

```powershell
.\scripts\watch-status.ps1
```

Start FramePack generation. Confirm:
- phase changes to preparing and then denoising.
- total_sections matches Kijai's section calculation: max(round((total_second_length * 30) / (latent_window_size * 4)), 1).
- section advances through the expected number of sections.
- progress_percent rises across section boundaries and does not reset.
- denoising progress reaches 100% at the end of sampling. VAE decoding and video saving may still remain.

Capture the sidebar and watcher output near the end of each section.

## 3. Verify pause and resume

During active denoising:
1. Record progress_percent, section and step.
2. Click Pause in the sidebar.
3. Wait for paused: True.
4. Wait 10 seconds; progress_percent, section and step should remain unchanged.
5. Click Resume.
6. Verify the same generation advances and completes without restarting.

Pause is cooperative: the in-flight model/CUDA operation finishes before the sampler waits. A pause request may take until the current iteration completes to become paused: True.

## 4. Verify interrupt while paused

Run another short generation, pause it, then trigger ComfyUI's normal Interrupt action. The wait loop should observe ComfyUI's interrupt within the polling interval and the node should exit as interrupted. The next queued FramePack run must not inherit a stale pause request.

## 5. Record the result

For each test, record Pass/Fail, logs and a screenshot. Do not upload prompts, input images, generated videos or model files unless safe to share.

A stable release requires all four test sections to pass on at least one Windows + CUDA machine. Compatibility claims across versions require additional machines/builds.
