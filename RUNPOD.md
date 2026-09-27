# RunPod deployment

After GitHub Actions finishes, use this Docker image in RunPod:

`ghcr.io/YOUR_GITHUB_USERNAME/wan-animate-plus:latest`

The image contains ComfyUI, WanAnimatePlus, WanVideoWrapper, VideoHelperSuite,
FeiHou Toolbox, the Python dependencies, SageAttention, and the model files
referenced by the included workflow.

If the GHCR package is private, make it public in GitHub:
Package settings -> Change visibility -> Public.
