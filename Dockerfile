# RunPod official ComfyUI base. RunPod's current ComfyUI image uses
# /workspace/runpod-slim/ComfyUI and CUDA 12.8.
FROM runpod/comfyui:latest

ENV PYTHONUNBUFFERED=1 \
    PIP_PREFER_BINARY=1 \
    COMFY_ROOT=/workspace/runpod-slim/ComfyUI

WORKDIR /workspace/runpod-slim/ComfyUI

# Install the custom nodes required by THIS workflow.
RUN git clone --depth 1 https://github.com/wuwukaka/ComfyUI-WanAnimatePlus.git custom_nodes/ComfyUI-WanAnimatePlus \
 && git clone --depth 1 https://github.com/kijai/ComfyUI-WanVideoWrapper.git custom_nodes/ComfyUI-WanVideoWrapper \
 && git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git custom_nodes/ComfyUI-VideoHelperSuite \
 && git clone --depth 1 https://github.com/FX-FeiHou/ComfyUI-FeiHou-Toolbox.git custom_nodes/ComfyUI-FeiHou-Toolbox

# The RunPod ComfyUI base creates/uses this venv at runtime. Create it at build
# time too, so dependencies for user-installed custom nodes are present before
# the Serverless worker starts.
RUN python3.12 -m venv --system-site-packages /workspace/runpod-slim/ComfyUI/.venv-cu128 \
 && /workspace/runpod-slim/ComfyUI/.venv-cu128/bin/python -m pip install --upgrade pip \
 && for r in custom_nodes/*/requirements.txt; do \
      if [ -f "$r" ]; then /workspace/runpod-slim/ComfyUI/.venv-cu128/bin/pip install --no-cache-dir -r "$r"; fi; \
    done \
 && /workspace/runpod-slim/ComfyUI/.venv-cu128/bin/pip install --no-cache-dir runpod requests

# WanAnimatePlus workflow explicitly requests SageAttention. Install a CUDA 12.8
# wheel compatible with the current RunPod ComfyUI base (Torch 2.10/cu128).
RUN /workspace/runpod-slim/ComfyUI/.venv-cu128/bin/pip install --no-cache-dir \
      --index-url https://wheels.astral.sh/simple/cu128/ \
      --extra-index-url https://pypi.org/simple \
      sageattention==2.2.0

# Bake the exact model files referenced by workflow.json into the image.
# This keeps Serverless workers independent of a Network Volume.
RUN mkdir -p \
      models/diffusion_models \
      models/vae \
      models/checkpoints \
      models/clip_vision \
      models/text_encoders \
      models/loras \
 && wget -q --show-progress -O models/diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors \
      https://huggingface.co/Comfy-Org/SCAIL-2/resolve/main/diffusion_models/wan2.1_14B_SCAIL_2_fp8_scaled.safetensors \
 && wget -q --show-progress -O models/vae/Wan2_1_VAE_bf16.safetensors \
      https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors \
 && wget -q --show-progress -O models/checkpoints/sam3.1_multiplex_fp16.safetensors \
      https://huggingface.co/Comfy-Org/sam3.1/resolve/main/checkpoints/sam3.1_multiplex_fp16.safetensors \
 && wget -q --show-progress -O models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors \
      https://huggingface.co/Comfy-Org/CLIP-ViT-H-14-laion2B-s32B-b79K_repackaged/resolve/main/split_files/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors \
 && wget -q --show-progress -O models/text_encoders/umt5-xxl-enc-bf16.safetensors \
      https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors \
 && wget -q --show-progress -O models/loras/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank128_bf16.safetensors \
      https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank128_bf16.safetensors \
 && wget -q --show-progress -O models/loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors \
      https://huggingface.co/Comfy-Org/SCAIL-2/resolve/main/loras/wan2.1_SCAIL_2_DPO_lora_bf16.safetensors

# Worker files. workflow.json is copied unchanged.
COPY requirements.txt /worker-requirements.txt
RUN /workspace/runpod-slim/ComfyUI/.venv-cu128/bin/pip install --no-cache-dir -r /worker-requirements.txt
COPY handler.py /handler.py
COPY workflow.json /workflow.json
COPY start-serverless.sh /start-serverless.sh
RUN chmod +x /start-serverless.sh

# The base image's own start script initializes the baked ComfyUI workspace and
# starts ComfyUI. Our wrapper runs it in the background, then starts the worker.
ENTRYPOINT ["/start-serverless.sh"]
