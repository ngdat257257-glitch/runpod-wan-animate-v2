"""
download_models.py — Tải model vào Network Volume, CHỈ 1 LẦN DUY NHẤT.
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
    """Symlink tất cả file model từ Network Volume vào ComfyUI/models/."""
    os.makedirs(COMFYUI_MODELS_DIR, exist_ok=True)
    if not os.path.isdir(MODELS_DIR):
        return
    for root, dirs, files in os.walk(MODELS_DIR):
        rel_path = os.path.relpath(root, MODELS_DIR)
        target_dir = COMFYUI_MODELS_DIR if rel_path == "." else os.path.join(COMFYUI_MODELS_DIR, rel_path)
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            if f.endswith(".tmp"):
                continue
            src_file = os.path.join(root, f)
            dst_file = os.path.join(target_dir, f)
            if os.path.islink(dst_file) or os.path.exists(dst_file):
                continue
            try:
                os.symlink(src_file, dst_file)
                print(f"[link] {dst_file} -> {src_file}")
            except Exception as e:
                print(f"[link error] {dst_file}: {e}")


if __name__ == "__main__":
    ensure_models_downloaded()
    link_models_to_comfyui()
