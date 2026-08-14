# AIRI Vietnamese Speech

Máy chủ tiếng Việt chạy local cho AIRI, dùng VieNeu TTS. Bản này có web UI để tạo TTS, clone WAV, quản lý voice clone và chép lời audio (STT).

## Chạy trên Windows

1. Cài **Python 3.10 64-bit** và chọn `Add Python to PATH` khi cài.
2. Giải nén project.
3. Double-click **`start-ui.bat`**.
4. Đợi lần đầu cài package; AIRI Vietnamese Speech sẽ mở trong **cửa sổ app riêng**.

Để dừng app, chỉ cần đóng cửa sổ AIRI Vietnamese Speech.

## Kết nối AIRI

Trong OpenAI Compatible TTS của AIRI, điền:

```text
Base URL: http://127.0.0.1:23333/v1/
API key:  airi-local
Model:    vieneu-tts-v3-turbo
Voice:    truc-ly
```

Ngay trong UI app có thẻ **Kết nối AIRI** để sao chép các thông số này và xem AIRI đã gọi vào server hay chưa. Sau khi lưu cấu hình trong AIRI, bấm **Kiểm tra kết nối**; trạng thái chuyển xanh khi app nhận request thật từ AIRI.

Bạn có thể dùng UI để xem ID chính xác của mọi voice. AIRI dùng ID (`truc-ly`), còn server tự đổi thành tên VieNeu (`Trúc Ly`). Voice clone sẽ có ID ổn định, ví dụ `giong-cua-toi`.

## Linux Mint

### Chạy từ source

```bash
chmod +x scripts/start_linux.sh
./scripts/start_linux.sh
```

Nếu thiếu WebKit/GTK, cài một lần:

```bash
sudo apt update
sudo apt install python3-venv python3-gi gir1.2-webkit2-4.0 ffmpeg espeak-ng
```

### Build và cài `.deb`

Trên Linux Mint, trong thư mục source:

```bash
chmod +x build-linux-mint-deb.sh
./build-linux-mint-deb.sh
sudo apt install ./dist/airi-vietnamese-speech_0.1.0_all.deb
```

Sau khi cài, mở **AIRI Vietnamese Speech** từ menu ứng dụng. Lần mở đầu cần mạng để cài các package Python và tải model; các lần sau chạy local.

## Clone voice

Mở UI, nhập tên, chọn WAV và bấm **Clone voice**. WAV nên là một người nói rõ ràng, ít noise, dài khoảng 3–10 giây. Voice clone được lưu tại `~/.airi-vietnamese-speech/voices` và được nạp lại sau khi restart.

Lần chạy đầu, `start-ui.bat` tự cài PyTorch CPU cho tính năng clone (download lớn một lần). Nếu UI báo thiếu PyTorch, đóng app và chạy lại `start-ui.bat`. Chỉ clone giọng của bạn hoặc giọng bạn có quyền sử dụng.

## Speech to Text

Phần STT dùng `faster-whisper`; model mặc định là `base` và chỉ tải ở lần chép lời đầu tiên. Nó chạy CPU INT8 để không cần cài CUDA/NVIDIA. Có thể đặt biến môi trường `AIRI_STT_MODEL` thành `tiny`, `small` hoặc model Whisper phù hợp khác trước khi chạy để đổi model.

## Build thành ứng dụng Windows

1. Chạy `start-ui.bat` một lần để tạo môi trường và cài dependency.
2. Đóng server.
3. Chạy **`build-windows.bat`**.
4. Bản portable nằm ở `dist\AIRI Vietnamese Speech\AIRI Vietnamese Speech.exe` và mở bằng cửa sổ app riêng, không cần mở trình duyệt.

Chép nguyên thư mục `dist\AIRI Vietnamese Speech` khi chuyển máy, không chỉ riêng file `.exe`. Lần đầu chạy, VieNeu/Whisper vẫn có thể tải model về máy; vì vậy bản `--onedir` ổn định hơn `--onefile`.

## API

- `GET /health`
- `GET /v1/models`
- `GET /v1/voices`
- `POST /v1/audio/speech`
- `POST /api/voices/clone`
- `DELETE /api/voices/{voice_id}`
- `POST /api/transcribe`
