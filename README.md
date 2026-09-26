# AIRI Vietnamese Speech

Ứng dụng giọng nói tiếng Việt chạy local cho AIRI Desktop:

- **AIRI nói:** VieNeu TTS, 14 giọng có sẵn và clone giọng WAV.
- **AIRI nghe:** faster-whisper nhận audio/microphone, trả văn bản theo chuẩn OpenAI.
- **Riêng tư:** API chỉ lắng nghe tại `127.0.0.1`; audio không được gửi lên dịch vụ bên ngoài sau khi model đã tải xong.

## Chạy bằng một cú nhấp

### Bản portable (dễ nhất)

Mở `dist\AIRI Vietnamese Speech\AIRI Vietnamese Speech.exe`. Khi chuyển sang máy khác, hãy chép **nguyên thư mục** `AIRI Vietnamese Speech`, không chỉ file `.exe`.

### Chạy từ mã nguồn

1. Cài Python **3.10 64-bit** và bật `Add Python to PATH`.
2. Nhấp đúp `start-ui.bat`.
3. Lần đầu ứng dụng cài thư viện và tải model nên sẽ lâu. Các lần sau mở ngay, không chạy cài đặt lại.

Nếu project được chép từ máy khác và báo `.venv` không hợp lệ, chỉ cần xóa/đổi tên thư mục `.venv`, sau đó chạy lại `start-ui.bat`.

## Kết nối AIRI Desktop

Dùng cùng thông tin này cho cả hai provider:

```text
Base URL: http://127.0.0.1:23333/v1
API key:  airi-local
```

### Để AIRI nói (TTS)

1. Vào **Settings → Providers → Speech → OpenAI Compatible**.
2. Model: `vieneu-tts-v3-turbo`.
3. Vào **Settings → Modules → Speech**, chọn provider vừa tạo và voice, ví dụ `truc-ly`.
4. Dùng phần Test Voice để kiểm tra.

### Để AIRI nghe và chuyển lời nói vào AI (STT)

1. Vào **Settings → Providers → Transcription → OpenAI Compatible**.
2. Model: `whisper` như giao diện AIRI trong ảnh. Server cũng chấp nhận `whisper-1`, `base` và `faster-whisper-base`.
3. Vào **Settings → Modules → Hearing**, chọn provider vừa tạo, chọn microphone và bấm **Start Monitoring**.
4. AIRI thu mic → gọi `/v1/audio/transcriptions` → nhận văn bản → đưa văn bản vào cuộc trò chuyện AI.

Trong cửa sổ app, nút **Sao chép cấu hình AIRI** sao chép toàn bộ giá trị trên. Trạng thái sẽ hiện endpoint cuối mà AIRI đã gọi.

## Tốc độ và model

- Danh sách voice hiện ngay, không phải chờ VieNeu tải.
- Lần chạy đầu nạp cả TTS và STT vào cache. Khi hai model hoàn tất, những lần mở sau bật chế độ Hugging Face offline và không kiểm tra mạng.
- STT dùng CPU INT8, VAD và beam nhỏ để phản hồi nhanh trên máy không có NVIDIA.
- Đặt `AIRI_PRELOAD_MODELS=0` nếu muốn tự tải model ở lần dùng đầu thay vì chuẩn bị nền.
- Đặt `AIRI_FORCE_OFFLINE=1` để bắt buộc không dùng mạng ngay cả khi cache chưa đủ (model thiếu sẽ báo lỗi thay vì tải).
- Đặt `AIRI_STT_MODEL=tiny` để nhanh/nhẹ hơn hoặc `small` để chính xác hơn trước khi mở app.
- Bản chạy mã nguồn lưu dữ liệu tại `%USERPROFILE%\.airi-vietnamese-speech`; bản portable lưu trong thư mục `data` cạnh file `.exe` để có thể chép nguyên thư mục sang máy khác.

## API tương thích

- `GET /health`
- `GET /v1/models`
- `GET /v1/voices`
- `POST /v1/audio/speech` — OpenAI-compatible TTS
- `POST /v1/audio/transcriptions` — OpenAI-compatible STT cho AIRI Hearing
- `POST /api/transcribe` — STT dùng bởi giao diện local
- `POST /api/voices/clone`
- `DELETE /api/voices/{voice_id}`

## Build Windows portable

1. Chạy `start-ui.bat` một lần để hoàn tất môi trường.
2. Đóng ứng dụng.
3. Chạy `build-windows.bat`.
4. Kết quả nằm tại `dist\AIRI Vietnamese Speech\AIRI Vietnamese Speech.exe`.
