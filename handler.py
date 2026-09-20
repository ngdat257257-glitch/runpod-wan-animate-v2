"""
handler.py (BAN NHE, dung Network Volume) — RunPod Serverless handler

Khac biet so voi ban truoc:
- Goi download_models.ensure_models_downloaded() + link_models_to_comfyui()
  TRUOC khi start ComfyUI server, thay vi model da co san trong image.
- Lan chay dau tien se cham hon (phai tai model), cac lan sau nhanh vi model
  da nam san trong Network Volume.
"""

import base64
import json
import os
import subprocess
import time
import uuid

import requests
import runpod

import download_models

COMFYUI_DIR = "/workspace/ComfyUI"
COMFYUI_PORT = 8188
COMFYUI_URL = f"http://127.0.0.1:{COMFYUI_PORT}"

_server_started = False
_models_ready = False


def ensure_models():
    global _models_ready
    if _models_ready:
        return
    download_models.ensure_models_downloaded()
    download_models.link_models_to_comfyui()
    _models_ready = True


def start_comfyui_server():
    global _server_started
    if _server_started:
        return
    log_file = open("/workspace/comfyui.log", "w")
    proc = subprocess.Popen(
        ["python3", "main.py", "--listen", "0.0.0.0", "--port", str(COMFYUI_PORT)],
        cwd=COMFYUI_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    for _ in range(180):
        if proc.poll() is not None:
            log_file.flush()
            try:
                with open("/workspace/comfyui.log", "r") as f:
                    err_log = f.read()[-1500:]
            except Exception:
                err_log = ""
            raise RuntimeError(
                f"ComfyUI server exited with code {proc.returncode}.\nLogs:\n{err_log}"
            )
        try:
            r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=2)
            if r.status_code == 200:
                _server_started = True
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    raise RuntimeError("ComfyUI server khong khoi dong duoc sau 180s")


def save_input_file(b64_data: str, filename: str) -> str:
    input_dir = os.path.join(COMFYUI_DIR, "input")
    os.makedirs(input_dir, exist_ok=True)
    path = os.path.join(input_dir, filename)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return filename


def build_prompt(image_filename: str, video_filename: str, seed: int, prompt_text: str) -> dict:
    with open("/workspace/workflow_template.json", "r", encoding="utf-8") as f:
        wf = json.load(f)

    if "199" in wf:
        wf["199"]["inputs"]["image"] = image_filename
    if "221" in wf:
        wf["221"]["inputs"]["video"] = video_filename
    if "198" in wf:
        wf["198"]["inputs"]["seed"] = seed
    if prompt_text and "218" in wf:
        wf["218"]["inputs"]["positive_prompt"] = prompt_text

    return wf


def submit_and_wait(prompt: dict, timeout: int = 600) -> dict:
    client_id = str(uuid.uuid4())
    resp = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": prompt, "client_id": client_id},
        timeout=30,
    )
    resp.raise_for_status()
    prompt_id = resp.json()["prompt_id"]

    start = time.time()
    while time.time() - start < timeout:
        h = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10).json()
        if prompt_id in h:
            return h[prompt_id]
        time.sleep(2)
    raise TimeoutError("ComfyUI xu ly qua lau, vuot timeout")


def extract_video_path(history_entry: dict) -> str:
    outputs = history_entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        if "gifs" in node_output:
            files = node_output["gifs"]
            if files:
                f = files[0]
                subfolder = f.get("subfolder", "")
                filename = f["filename"]
                return os.path.join(COMFYUI_DIR, "output", subfolder, filename)
    raise RuntimeError("Khong tim thay video output trong history")


def handler(job):
    job_input = job["input"]

    image_b64 = job_input.get("image_base64")
    video_b64 = job_input.get("video_base64")
    seed = job_input.get("seed", 123456789)
    prompt_text = job_input.get("prompt", "")

    if not image_b64 or not video_b64:
        return {"error": "Thieu image_base64 hoac video_base64 trong input"}

    # Buoc quan trong khac voi ban truoc: dam bao model co san (Network Volume)
    ensure_models()
    start_comfyui_server()

    image_filename = f"{uuid.uuid4().hex}.jpg"
    video_filename = f"{uuid.uuid4().hex}.mp4"
    save_input_file(image_b64, image_filename)
    save_input_file(video_b64, video_filename)

    prompt = build_prompt(image_filename, video_filename, seed, prompt_text)
    history_entry = submit_and_wait(prompt)
    output_path = extract_video_path(history_entry)

    with open(output_path, "rb") as f:
        video_b64_out = base64.b64encode(f.read()).decode("utf-8")

    return {"video_base64": video_b64_out}


runpod.serverless.start({"handler": handler})
