# Contributing

Thanks for helping improve ComfyUI-FramePack-Pause.

1. Keep integration isolated from Kijai's upstream files.
2. Do not copy or vendor upstream sampler implementation.
3. Run `python -m unittest discover -s tests -v`.
4. Run `python -m compileall -q .`.
5. For sampler or frontend changes, report ComfyUI and FramePackWrapper versions used in manual tests.
6. Do not claim end-to-end support based only on unit tests; GPU-backed validation is required.

For bug reports, include ComfyUI version, FramePackWrapper version/commit, Python version, sampler details and relevant startup logs. Do not attach model weights or private user media.
