"""
RunPod Serverless handler — WanAnimatePlus (SCAIL-2)

NGUYÊN TẮC BẮT BUỘC:
- KHÔNG sửa workflow.json gốc trên disk (chỉ đọc, không ghi đè).
- KHÔNG sửa/thêm/xoá bất kỳ node, connection, model, LoRA, sampler, resolution,
  frame count hay BlockSwap nào trong workflow.
- CHỈ patch 2 field trên một bản COPY trong memory:
    node "199".inputs.image  <- tên file ảnh vừa lưu
    node "221".inputs.video  <- tên file video vừa lưu
- Nếu workflow không đúng như kỳ vọng (node 199 không phải LoadImage, node 221
  không phải VHS_LoadVideoFFmpeg) -> báo lỗi ngay, KHÔNG tự sửa.

Input job["input"] hỗ trợ:
{
  "image_url": "https://...",   hoặc  "image_base64": "<base64>",
  "video_url": "https://...",   hoặc  "video_base64": "<base64>"
}

Output:
{
  "status": "success",
  "filename": "wanimate_..._00001.mp4",
  "video_base64": "<base64 mp4>"
}
hoặc:
{
  "status": "error",
  "stage": "<bước bị lỗi>",
  "error": "<mô tả lỗi>"
}
"""

import base64
import copy
import json
import os
import sys
import time
import uuid
import urllib.request

import requests
import runpod

# ---------------------------------------------------------------------------
# CẤU HÌNH ĐƯỜNG DẪN — khớp đúng môi trường pod hiện có
# ---------------------------------------------------------------------------
COMFY_ROOT = os.environ.get("COMFY_ROOT", "/workspace/runpod-slim/ComfyUI")
COMFY_INPUT_DIR = os.path.join(COMFY_ROOT, "input")
COMFY_OUTPUT_DIR = os.path.join(COMFY_ROOT, "output")
COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1:8188")

# workflow.json luôn nằm cạnh handler.py, KHÔNG được ghi đè file này
WORKFLOW_PATH = os.environ.get(
    "WORKFLOW_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow.json"),
)

# Node id đã xác nhận thủ công từ workflow.json — không tự dò tìm, không suy đoán
NODE_LOAD_IMAGE = "199"
NODE_LOAD_VIDEO = "221"
NODE_VIDEO_COMBINE = "220"  # node xuất video cuối (VHS_VideoCombine)

EXPECTED_CLASS_LOAD_IMAGE = "LoadImage"
EXPECTED_CLASS_LOAD_VIDEO = "VHS_LoadVideoFFmpeg"

COMFY_SERVER_READY_TIMEOUT_SEC = int(os.environ.get("COMFY_SERVER_READY_TIMEOUT_SEC", "180"))
COMFY_JOB_TIMEOUT_SEC = int(os.environ.get("COMFY_JOB_TIMEOUT_SEC", "1800"))  # 30 phút
COMFY_POLL_INTERVAL_SEC = 2


def log(msg):
    print(f"[handler] {msg}", flush=True)


# ---------------------------------------------------------------------------
# 0. Chờ ComfyUI API sẵn sàng
# ---------------------------------------------------------------------------
def wait_for_comfy_server(timeout=COMFY_SERVER_READY_TIMEOUT_SEC):
    log("Đang kiểm tra ComfyUI API...")
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            r = requests.get(f"http://{COMFY_HOST}/system_stats", timeout=5)
            if r.status_code == 200:
                log("ComfyUI API đã sẵn sàng.")
                return
        except requests.exceptions.RequestException as e:
            last_err = e
        time.sleep(2)
    raise RuntimeError(f"ComfyUI API không phản hồi sau {timeout}s. Lỗi cuối: {last_err}")


# ---------------------------------------------------------------------------
# 1-3. Nhận & lưu file input vào đúng thư mục ComfyUI/input
# ---------------------------------------------------------------------------
def save_input_file(url=None, b64=None, out_path=None, kind="file"):
    if not url and not b64:
        raise ValueError(f"Thiếu input cho {kind}: cần '{kind}_url' hoặc '{kind}_base64'.")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if b64:
        log(f"Đang decode base64 cho {kind}...")
        raw = base64.b64decode(b64.split(",", 1)[1] if b64.startswith("data:") else b64)
        with open(out_path, "wb") as f:
            f.write(raw)
    else:
        log(f"Đang tải {kind} từ URL: {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)

    size_kb = os.path.getsize(out_path) / 1024
    log(f"Đã lưu {kind} -> {out_path} ({size_kb:.1f} KB)")
    return out_path


# ---------------------------------------------------------------------------
# 4-8. Đọc workflow gốc (KHÔNG SỬA FILE), copy trong memory, patch đúng 2 field
# ---------------------------------------------------------------------------
def load_and_patch_workflow(image_filename, video_filename):
    log(f"Đọc workflow gốc: {WORKFLOW_PATH}")
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        original = json.load(f)

    # Validate đúng 2 node trước khi đụng vào — không tự sửa nếu sai
    node_img = original.get(NODE_LOAD_IMAGE)
    node_vid = original.get(NODE_LOAD_VIDEO)

    if not node_img or node_img.get("class_type") != EXPECTED_CLASS_LOAD_IMAGE:
        raise RuntimeError(
            f"Node {NODE_LOAD_IMAGE} không phải '{EXPECTED_CLASS_LOAD_IMAGE}' như kỳ vọng "
            f"(thực tế: {node_img.get('class_type') if node_img else 'không tồn tại'}). "
            "Dừng lại, không tự sửa workflow."
        )
    if not node_vid or node_vid.get("class_type") != EXPECTED_CLASS_LOAD_VIDEO:
        raise RuntimeError(
            f"Node {NODE_LOAD_VIDEO} không phải '{EXPECTED_CLASS_LOAD_VIDEO}' như kỳ vọng "
            f"(thực tế: {node_vid.get('class_type') if node_vid else 'không tồn tại'}). "
            "Dừng lại, không tự sửa workflow."
        )

    # Copy trong memory — file gốc trên disk không hề bị đụng tới
    workflow = copy.deepcopy(original)
    workflow[NODE_LOAD_IMAGE]["inputs"]["image"] = image_filename
    workflow[NODE_LOAD_VIDEO]["inputs"]["video"] = video_filename

    log(f"Đã patch node {NODE_LOAD_IMAGE}.inputs.image = {image_filename}")
    log(f"Đã patch node {NODE_LOAD_VIDEO}.inputs.video = {video_filename}")
    log("Toàn bộ node/model/LoRA/sampler/resolution/frame/BlockSwap khác giữ nguyên 100%.")

    return workflow


# ---------------------------------------------------------------------------
# 9. Gửi workflow tới ComfyUI API
# ---------------------------------------------------------------------------
def queue_prompt(workflow, client_id):
    log("Gửi prompt tới ComfyUI (/prompt)...")
    r = requests.post(
        f"http://{COMFY_HOST}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ComfyUI từ chối prompt (HTTP {r.status_code}): {r.text}")
    prompt_id = r.json().get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI không trả về prompt_id: {r.text}")
    log(f"Đã queue, prompt_id = {prompt_id}")
    return prompt_id


# ---------------------------------------------------------------------------
# 10. Chờ ComfyUI xử lý xong
# ---------------------------------------------------------------------------
def wait_for_completion(prompt_id, timeout=COMFY_JOB_TIMEOUT_SEC):
    log("Đang chờ ComfyUI xử lý (poll /history)...")
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"http://{COMFY_HOST}/history/{prompt_id}", timeout=30)
        if r.status_code == 200 and r.json():
            history = r.json().get(prompt_id, {})
            status = history.get("status", {})
            status_str = status.get("status_str")

            if status_str == "error":
                raise RuntimeError(f"ComfyUI báo lỗi khi chạy workflow: {json.dumps(status)}")

            if status.get("completed") is True or status_str == "success":
                elapsed = time.time() - start
                log(f"ComfyUI xử lý xong sau {elapsed:.1f}s.")
                return history

        time.sleep(COMFY_POLL_INTERVAL_SEC)

    raise TimeoutError(f"ComfyUI không xử lý xong sau {timeout}s (timeout).")


# ---------------------------------------------------------------------------
# 11. Lấy file MP4 output
# ---------------------------------------------------------------------------
def extract_output_video(history):
    outputs = history.get("outputs", {})
    node_out = outputs.get(NODE_VIDEO_COMBINE, {})

    for key in ("gifs", "videos", "files"):
        items = node_out.get(key)
        if items:
            item = items[0]
            filename = item["filename"]
            subfolder = item.get("subfolder", "")
            full_path = os.path.join(COMFY_OUTPUT_DIR, subfolder, filename)
            if not os.path.exists(full_path):
                raise RuntimeError(f"ComfyUI báo có output nhưng không tìm thấy file: {full_path}")
            log(f"Tìm thấy output video: {full_path}")
            return full_path, filename

    raise RuntimeError(
        f"Không tìm thấy video output ở node {NODE_VIDEO_COMBINE}. "
        f"Outputs nhận được: {json.dumps(outputs)}"
    )


# ---------------------------------------------------------------------------
# HANDLER CHÍNH
# ---------------------------------------------------------------------------
def handler(job):
    job_input = job.get("input", {}) or {}
    run_id = uuid.uuid4().hex[:10]
    stage = "init"

    try:
        log(f"===== Bắt đầu job, run_id={run_id} =====")

        stage = "wait_comfy_server"
        wait_for_comfy_server()

        stage = "save_image"
        image_filename = f"input_image_{run_id}.png"
        save_input_file(
            url=job_input.get("image_url"),
            b64=job_input.get("image_base64"),
            out_path=os.path.join(COMFY_INPUT_DIR, image_filename),
            kind="image",
        )

        stage = "save_video"
        video_filename = f"input_video_{run_id}.mp4"
        save_input_file(
            url=job_input.get("video_url"),
            b64=job_input.get("video_base64"),
            out_path=os.path.join(COMFY_INPUT_DIR, video_filename),
            kind="video",
        )

        stage = "build_workflow"
        workflow = load_and_patch_workflow(image_filename, video_filename)

        stage = "queue_prompt"
        client_id = uuid.uuid4().hex
        prompt_id = queue_prompt(workflow, client_id)

        stage = "wait_completion"
        history = wait_for_completion(prompt_id)

        stage = "extract_output"
        video_path, out_filename = extract_output_video(history)

        stage = "encode_output"
        with open(video_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("utf-8")

        log(f"===== Hoàn tất job run_id={run_id} =====")
        return {
            "status": "success",
            "filename": out_filename,
            "video_base64": video_b64,
        }

    except Exception as e:
        log(f"LỖI tại bước '{stage}': {e}")
        return {
            "status": "error",
            "stage": stage,
            "error": str(e),
        }


# RunPod tự spawn nhiều job song song theo hàng đợi/worker; mỗi job ở đây dùng
# run_id riêng nên nhiều job có thể chạy đồng thời mà không đụng file của nhau.
runpod.serverless.start({"handler": handler})
