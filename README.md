# Wan-Animate Worker — BẢN NHẸ (Network Volume)

Bản này KHÔNG bake model vào Docker image → build nhanh, nhẹ, chạy được
trên máy yếu như MacBook Air M2 8GB. Model sẽ tự tải vào **RunPod Network
Volume** khi container chạy lần đầu tiên.

## Vì sao cần đổi cách này trên Mac M2

1. **Dung lượng**: bản cũ bake ~15-20GB model vào image → cần nhiều ổ trống
   tạm khi build. Bản này chỉ ~3-5GB (ComfyUI + code), nhẹ hơn nhiều.
2. **Kiến trúc CPU khác nhau**: Mac M2 dùng chip ARM, RunPod GPU server dùng
   CPU x86_64 (Intel/AMD). Phải build "cross-platform" — xem lệnh ở Bước 3.

## Các file trong bộ này

- `Dockerfile` — chỉ cài ComfyUI + custom node (không có model)
- `model_manifest.json` — danh sách model cần tải (dễ sửa URL nếu cần)
- `download_models.py` — chạy lúc container khởi động, tải model vào Network Volume nếu chưa có
- `handler.py` — nhận request, đảm bảo model sẵn sàng, gọi ComfyUI API
- `workflow_template.json` — workflow gốc (API-format)

## ⚠️ Việc cần kiểm tra trước khi build

Mở `model_manifest.json`, đối chiếu từng URL với
https://huggingface.co/Comfy-Org/SCAIL-2/tree/main — sửa lại nếu tên
thư mục/file thực tế khác.

## Bước 1 — Cài Docker Desktop cho Mac (hỗ trợ multi-platform build)

Tải bản Apple Silicon tại https://www.docker.com/products/docker-desktop
Mở app, chờ Docker khởi động xong (icon cá voi trên thanh menu hết animation).

## Bước 2 — Bật buildx (thường có sẵn trong Docker Desktop mới)

```bash
docker buildx create --use --name multiplatform-builder
docker buildx inspect --bootstrap
```

## Bước 3 — Build image CHO ĐÚNG KIẾN TRÚC x86_64 (bắt buộc trên Mac)

```bash
cd ~/wan-animate-v2
docker login   # nếu chưa đăng nhập

docker buildx build \
  --platform linux/amd64 \
  -t <ten-dockerhub-cua-ban>/wan-animate-worker:latest \
  --push .
```

Lưu ý:
- `--platform linux/amd64` bắt buộc phải có — nếu bỏ qua, Docker Desktop
  trên Mac sẽ build cho ARM (kiến trúc của chính con Mac), image đó
  **sẽ không chạy được** trên GPU server của RunPod (x86_64).
- `--push` gộp luôn bước build + đẩy lên Docker Hub trong 1 lệnh.
- Lần build đầu vẫn mất thời gian (cài ComfyUI + custom node + biên dịch
  vài thư viện qua giả lập QEMU do khác kiến trúc), nhưng KHÔNG tải model
  nên nhẹ hơn nhiều so với bản cũ. Ước tính 10-25 phút tùy mạng.

## Bước 4 — Tạo Network Volume trên RunPod

1. Vào https://console.runpod.io/storage → **New Network Volume**
2. Đặt tên (vd `wan-animate-models`), chọn dung lượng ≥30GB (để dư cho model
   ~20GB + đệm), chọn Region trùng với nơi bạn sẽ chạy GPU.
3. Tạo xong, ghi nhớ tên volume.

## Bước 5 — Deploy Serverless Endpoint, gắn kèm Network Volume

1. Vào https://console.runpod.io/serverless → **New Endpoint**
2. Chọn **Custom Image**, điền `<ten-dockerhub-cua-ban>/wan-animate-worker:latest`
3. Ở phần **Network Volume**, chọn volume vừa tạo ở Bước 4 — RunPod sẽ tự
   mount vào `/runpod-volume` bên trong container (đúng path mà
   `download_models.py` đang dùng).
4. Chọn GPU ≥24GB VRAM (RTX 4090, A5000, A6000...)
5. Deploy.

## Bước 6 — Test lần đầu (sẽ chậm vì phải tải model)

```bash
curl -X POST https://api.runpod.ai/v2/<endpoint-id>/runsync \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "image_base64": "<base64 anh>",
      "video_base64": "<base64 video mau>",
      "seed": 123456789
    }
  }'
```

Lần chạy đầu tiên trên mỗi Network Volume mới sẽ mất thêm 10-20 phút để tải
model (~15-20GB). Có thể cần tăng timeout hoặc dùng endpoint `/run` (bất đồng
bộ) thay vì `/runsync` cho lần đầu, rồi poll `/status/<job-id>`.

Từ lần thứ 2 trở đi: model đã có sẵn trong Network Volume → chạy nhanh như
bản cũ, không phải tải lại.

## Lỗi thường gặp riêng của bản Network Volume

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `Khong tim thay Network Volume tai /runpod-volume` | Chưa gắn Network Volume cho endpoint | Quay lại Bước 5, kiểm tra đã chọn đúng volume chưa |
| Container chạy được trên Mac (local test) nhưng lỗi trên RunPod | Build thiếu `--platform linux/amd64` | Build lại đúng lệnh ở Bước 3 |
| Lần đầu test bị timeout | Đang tải model lần đầu (mất chục phút) | Dùng `/run` async thay vì `/runsync`, hoặc tăng timeout client |
| Model tải xong nhưng ComfyUI báo thiếu file | Tên `dest` trong `model_manifest.json` không khớp cấu trúc thư mục ComfyUI mong đợi | Kiểm tra lại đúng tên thư mục con (`diffusion_models/`, `vae/`...) |
