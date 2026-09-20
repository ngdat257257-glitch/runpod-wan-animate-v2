"""
download_models.py — Tải model vào Network Volume, CHỈ 1 LẦN DUY NHẤT.

Cách hoạt động:
- RunPod Network Volume được mount vào container tại /runpod-volume (mặc định).
- Script kiểm tra từng file trong model_manifest.json:
    - Nếu đã tồn tại trong /runpod-volume/models/... -> bỏ qua (không tải lại)
    - Nếu chưa có -> tải về, lưu vào Network Volume
- ComfyUI models/ sẽ được symlink trỏ tới /runpod-volume/models để dùng lại
  giữa các lần chạy (container có thể bị huỷ/tạo mới nhưng Network Volume thì giữ nguyên).

Lần chạy đầu tiên sẽ chậm (phải tải hết model, ~15-20GB).
Các lần chạy sau NHANH vì model đã có sẵn trong Network Volume.
"""

import json
import os
import requests

VOLUME_PATH = "/runpod-volume"
MODELS_DIR = os.path.join(VOLUME_PATH, "models")
COMFYUI_MODELS_DIR = "/workspace/ComfyUI/models"
MANIFEST_PATH = "/workspace/model_manifest.json"


def download_file(url: str, dest_path: str):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    print(f"[download] {url} -> {dest_path}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(dest_path + ".tmp", "wb") as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    print(f"  {pct}%", end="\r")
    os.rename(dest_path + ".tmp", dest_path)
    print(f"[done] {dest_path}")


def ensure_models_downloaded():
    """Kiểm tra + tải các model còn thiếu vào Network Volume."""
    if not os.path.isdir(VOLUME_PATH):
        raise RuntimeError(
            f"Khong tim thay Network Volume tai {VOLUME_PATH}. "
            "Kiem tra lai da attach Network Volume cho endpoint chua."
        )

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for item in manifest["models"]:
        dest_path = os.path.join(MODELS_DIR, item["dest"])
        if os.path.exists(dest_path):
            print(f"[skip] da co san: {dest_path}")
            continue
        download_file(item["url"], dest_path)

    print("Tat ca model da san sang trong Network Volume.")


def link_models_to_comfyui():
    """Symlink từng thư mục con trong models/ (Network Volume) vào ComfyUI/models/."""
    os.makedirs(COMFYUI_MODELS_DIR, exist_ok=True)
    if not os.path.isdir(MODELS_DIR):
        return
    for subfolder in os.listdir(MODELS_DIR):
        src = os.path.join(MODELS_DIR, subfolder)
        dst = os.path.join(COMFYUI_MODELS_DIR, subfolder)
        if os.path.islink(dst) or os.path.exists(dst):
            continue
        os.symlink(src, dst)
        print(f"[link] {dst} -> {src}")


if __name__ == "__main__":
    ensure_models_downloaded()
    link_models_to_comfyui()
