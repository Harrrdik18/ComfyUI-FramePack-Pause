# Contributing

Thanks for helping improve ComfyUI-FramePack-Pause.

## Guidelines

1. Keep integration isolated from Kijai's upstream files.
2. Do not copy, vendor or patch upstream sampler implementation files.
3. Keep the pause gate cooperative and outside the model/sampling math.
4. Keep progress clearly labelled as denoising progress; do not present it as total wall-clock or workflow completion.
5. Report ComfyUI, frontend and FramePackWrapper versions used in manual tests.
6. Do not claim end-to-end support based only on unit tests; GPU-backed validation is required.

## Local checks

Run these from the repository root:

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
node --input-type=module --check < web/framepack_pause.js
```

## Bug reports

Include ComfyUI version, frontend version, FramePackWrapper commit, Python version, sampler settings and relevant startup logs. For progress issues, include the configured video duration, latent window size, steps, observed section count and sidebar status JSON. Do not attach model weights or private user media.
