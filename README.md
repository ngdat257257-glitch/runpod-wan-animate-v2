# runpod-wan-animate-plus

RunPod Serverless worker for the tested WanAnimatePlus / SCAIL-2 workflow.

## Important

- `workflow.json` is the original API-format workflow and is kept unchanged.
- `handler.py` only patches two fields on an in-memory copy:
  - node `199` → `inputs.image`
  - node `221` → `inputs.video`
- The Docker image is built directly by RunPod from GitHub.
- No Network Volume is required for the models because the Docker build downloads the exact model files referenced by the workflow.

## Required RunPod setup

Use **Deploy from GitHub / Start from GitHub Repo** and point it at the repository root containing this Dockerfile. RunPod's GitHub integration builds the Docker image and deploys the endpoint.

Recommended for the first test:

- GPU: RTX A4500 20GB (or another GPU that you have already verified with this workflow)
- Container disk: **at least 60 GB** because the image bakes roughly 38 GB of model weights plus ComfyUI and dependencies.
- Workers: 1
- Network Volume: none

## Input

```json
{
  "input": {
    "image_url": "https://.../character.jpg",
    "video_url": "https://.../motion.mp4"
  }
}
```

Base64 input is also supported:

```json
{
  "input": {
    "image_base64": "...",
    "video_base64": "..."
  }
}
```

## Output

For the first integration test the worker returns the MP4 as base64:

```json
{
  "status": "success",
  "filename": "...mp4",
  "video_base64": "..."
}
```

For the production website, change the output layer later to upload the MP4 to R2/S3 and return a URL instead of putting the whole MP4 in JSON.
