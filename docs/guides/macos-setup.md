# HIWM Interaction Engine on Apple Silicon macOS

The upstream 0.6.0 CUDA profiles target NVIDIA Linux/Windows. This checkout
adds macOS profiles that keep the upstream RTC/WebUI architecture without a
local CUDA avatar. The default profile is now the additive HIWM demo; the
original prepared Qwen-Omni profile remains selectable.

## Prepared profile

- Web UI, camera, microphone, WebRTC, interrupt handling, and Silero VAD
- Streaming ASR, an HIWM three-branch/lock/feedback gate, and cloud TTS
- Local face-landmark and speech-prosody overlays (observable features only)
- CPU ONNX Runtime on macOS
- Local URL: <http://127.0.0.1:8283/ui/index.html>

The UI boots without a real API key. Start the local service:

```bash
bash scripts/start_macos.sh
```

Open <http://127.0.0.1:8283/ui/index.html>. The combined setup screen lets you
enter one DashScope / Model Studio key for ASR, HIWM, and TTS, confirm the data
use, and request camera/microphone access with one application action. The key
is sent only to the local service process memory. It is not written to `.env`,
browser storage, the public configuration response, or logs. Enter it again
after restarting the service.

Browsers still require their own native Allow confirmation the first time a
camera or microphone is requested; a web page cannot bypass that prompt.

For unattended startup, `.env` remains an optional fallback:

```dotenv
DASHSCOPE_API_KEY=
```

Both macOS scripts create credential files with `umask 077` and force `.env`
to owner-only mode `0600`; they never print the key.

For a clean reinstall:

```bash
bash scripts/setup_macos.sh
```

For architecture, privacy, model, and test details see
[`hiwm-runtime.md`](hiwm-runtime.md). The
upstream LiteAvatar, MuseTalk, and FlashHead profiles remain in the repository
but require NVIDIA CUDA and are intentionally not selected here.
