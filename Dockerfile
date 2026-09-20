# ==============================================================================
# Dockerfile (BAN NHE) — ComfyUI + Wan-Animate cho RunPod Serverless
# KHONG bake model vao image -> nhe hon nhieu (~3-5GB thay vi ~20GB)
# Model se duoc tai vao Network Volume luc container khoi dong lan dau
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
# FastGroupsBypassSwitch
RUN git clone https://github.com/FX-FeiHou/ComfyUI-FeiHou-Toolbox.git

WORKDIR /workspace/ComfyUI

# ------------------------------------------------------------------------------
# 3. Patch tuong thich cho comfy_kitchen & nang cap PyTorch 2.5+
# ------------------------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade comfy_kitchen || true

# Fix loi: Parameter stride has unsupported type list[int] trong comfy_kitchen
RUN python3 -c 'import glob, os; \
    files = glob.glob("/usr/local/lib/python3.11/dist-packages/comfy_kitchen/**/*.py", recursive=True); \
    [open(f, "w").write("import typing\n" + open(f).read().replace("stride: list[int]", "stride: typing.List[int]").replace("tuple[int, int, int]", "typing.Tuple[int, int, int]")) for f in files if os.path.isfile(f)]' || true

# Fix loi: AttributeError: module comfy_kitchen has no attribute int8_attention_is_available
RUN python3 -c 'import site, os; \
    [open(os.path.join(p, "comfy_kitchen/__init__.py"), "a").write("\ndef int8_attention_is_available():\n    return False\n") for p in site.getsitepackages() if os.path.exists(os.path.join(p, "comfy_kitchen/__init__.py"))]' || true

RUN sed -i 's/comfy_kitchen.int8_attention_is_available()/getattr(comfy_kitchen, "int8_attention_is_available", lambda: False)()/g' /workspace/ComfyUI/comfy/ldm/modules/attention.py || true

RUN pip install --no-cache-dir --upgrade "torch>=2.5.0" "torchvision>=0.20.0" --index-url https://download.pytorch.org/whl/cu124 || true

# ------------------------------------------------------------------------------
# 4. Cai RunPod SDK
# ------------------------------------------------------------------------------
RUN pip install --no-cache-dir runpod requests

# ------------------------------------------------------------------------------
# 5. Copy code (khong copy model - model tai luc runtime)
# ------------------------------------------------------------------------------
COPY handler.py /workspace/handler.py
COPY download_models.py /workspace/download_models.py
COPY workflow_template.json /workspace/workflow_template.json
COPY model_manifest.json /workspace/model_manifest.json

# ------------------------------------------------------------------------------
# 6. Entry point
# ------------------------------------------------------------------------------
WORKDIR /workspace
CMD ["python3", "-u", "handler.py"]
