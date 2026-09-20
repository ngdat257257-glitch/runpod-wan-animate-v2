# ==============================================================================
# Dockerfile (BAN NHE) — ComfyUI + Wan-Animate cho RunPod Serverless
# KHONG bake model vao image -> nhe hon nhieu (~3-5GB thay vi ~20GB)
# Model se duoc tai vao Network Volume luc container khoi dong lan dau
#
# QUAN TRONG neu build tren Mac (M1/M2/M3 - chip ARM):
# RunPod GPU server chay tren CPU x86_64 (Intel/AMD), khac kien truc voi Mac (ARM).
# Phai build image cho dung kien truc x86_64, neu khong container se khong chay
# duoc tren RunPod. Dung lenh nay khi build (xem chi tiet trong README):
#
#   docker buildx build --platform linux/amd64 -t <ten>/wan-animate-worker:latest --push .
#
# ==============================================================================

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /workspace

# ------------------------------------------------------------------------------
# 1. Cai ComfyUI
# ------------------------------------------------------------------------------
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI
WORKDIR /workspace/ComfyUI
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# 2. Cai custom node (nhe, chi la code Python, khong phai model)
# ------------------------------------------------------------------------------
WORKDIR /workspace/ComfyUI/custom_nodes

RUN git clone https://github.com/wuwukaka/ComfyUI-WanAnimatePlus.git
RUN pip install --no-cache-dir -r ComfyUI-WanAnimatePlus/requirements.txt || true

RUN git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
RUN pip install --no-cache-dir -r ComfyUI-WanVideoWrapper/requirements.txt || true

RUN git clone https://github.com/rgthree/rgthree-comfy.git
RUN pip install --no-cache-dir -r rgthree-comfy/requirements.txt || true

RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git comfyui-kjnodes
RUN pip install --no-cache-dir -r comfyui-kjnodes/requirements.txt || true

RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git comfyui-videohelpersuite
RUN pip install --no-cache-dir -r comfyui-videohelpersuite/requirements.txt || true

RUN git clone https://github.com/M1kep/ComfyLiterals.git comfyliterals

# XAC NHAN MOI: repo nay chua 5 node quan trong dung trong workflow:
# SCAIL2ColoredMaskV2, ComfySwitchNodeV2, InvertBoolean, ImageBatchMultiV2,
# FastGroupsBypassSwitch (xac nhan qua README chinh thuc cua repo, khong doan)
RUN git clone https://github.com/FX-FeiHou/ComfyUI-FeiHou-Toolbox.git

# SAM3_VideoTrack / SAM3_TrackToMask la node built-in cua ComfyUI core (PR #13408)
# -> khong can cai them gi, chi can ComfyUI ban moi (git clone o tren la ban moi nhat)

WORKDIR /workspace/ComfyUI

# ------------------------------------------------------------------------------
# 3. Cai RunPod SDK
# ------------------------------------------------------------------------------
RUN pip install --no-cache-dir runpod requests

# ------------------------------------------------------------------------------
# 4. Copy code (khong copy model - model tai luc runtime)
# ------------------------------------------------------------------------------
COPY handler.py /workspace/handler.py
COPY download_models.py /workspace/download_models.py
COPY workflow_template.json /workspace/workflow_template.json
COPY model_manifest.json /workspace/model_manifest.json

# ------------------------------------------------------------------------------
# 5. Entry point
# ------------------------------------------------------------------------------
WORKDIR /workspace
CMD ["python3", "-u", "handler.py"]
