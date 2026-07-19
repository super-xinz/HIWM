# HIWM Interaction Engine runtime

HIWM Interaction Engine combines a maintained RTC/VAD/ASR/TTS/Avatar runtime
with the project's own HIWM decision gate, verified ledger, API, and dashboard.
It is an interaction-decision demo, not a calibrated or independently trained
human world-model checkpoint. Upstream provenance remains documented separately.

## What is implemented

The runtime order is intentionally fixed:

1. Existing WebRTC receives the real microphone and camera.
2. Existing Silero VAD and Bailian ASR establish a finalized user turn.
3. The browser derives visible face landmarks/head pose and speech-prosody
   measurements. Only a bounded numeric summary is sent as client perception.
4. User-confirmed initial task context is stored locally, sent only after
   consent, and attached to the current session as cited history evidence.
5. HIWM freezes the observation, extracts needs/concerns/commitments/questions/
   unknowns, and asks a structured-output model for exactly
   three candidate actions with non-duplicate contract fields and predicted
   next responses. Semantic diversity is not claimed or calibrated yet.
6. A server-side planner scores goal, expected information gain, risk, and
   uncertainty. If every normal branch is weak or unsafe it forces an explicit
   clarification/wait branch.
7. The complete prediction is appended to a per-session JSONL ledger, flushed,
   `fsync`'d, and SHA-256 locked before any selected utterance enters TTS.
8. Existing Bailian TTS speaks only the locked action. Real playback completion,
   not text submission, promotes the prediction as the next feedback baseline.
9. The next finalized user response is compared with that locked prediction and
   updates the versioned working beliefs.

The WebUI shows the user's working profile, real camera view, observable visual
and speech evidence, exactly three predicted action branches, the auto-selected
branch, and a derived evidence/prediction/feedback/profile-update timeline.
Replay stores bounded text and numeric evidence snapshots, never raw audio,
video, images, or face landmarks; seeking therefore locates the derived event
time rather than replaying media that was never retained.

## Scientific and safety boundary

Face and voice analysis reports only observable features such as landmarks,
head yaw/pitch, tracking stability, `browInnerUp`, `jawOpen`, waveform, relative
pitch, energy, voiced/silent windows, and pauses. It does **not** infer or label
hidden emotion, personality, deception, mental health, protected traits, or
fitness for employment. Model probabilities are displayed as
`uncalibrated_model_estimate` / "模型预测·演示估计" until a separate
real-data calibration study exists.

The server enforces the same boundary after model generation. Prohibited hidden
emotion, personality, deception, diagnosis, protected-trait, and high-impact
employment claims reject the complete response and enter the configured
retry/safe-fallback path. The low-cost macOS profile uses one attempt, so it
falls back immediately. Unknown or missing evidence references are rejected rather than
silently rewritten into apparently valid citations.

Normal turns are automatic and have no approval button. Mute, camera off,
interrupt, consent withdrawal, and ending the session remain global safety
controls. Raw microphone dumps are disabled. The browser timeline stores only
derived events and text by default; it does not silently record raw face video
or microphone audio.

## Configure

Create the local environment once:

```bash
bash scripts/setup_macos.sh
```

Start the service without editing `.env`, open the local UI, and enter a Model
Studio key on the combined setup screen. One application action submits the
key to process memory, records consent, and requests the required device
permissions. The public configuration response remains secret-free, and the
client neither writes the key to browser storage nor persists it to `.env`.
The key must be entered again after a service restart.

An ignored project-root `.env` remains an optional fallback for unattended
startup. The setup and start scripts use `umask 077` and force any such file to
owner-only mode `0600`.

The runtime-key and explicit RTC-release endpoints accept loopback clients by
default. If the service is bound to a non-loopback interface, set a long random
`HIWM_RUNTIME_CONTROL_TOKEN` and configure the same value as the Web UI access
token. Without it, remote clients receive `403` and must use the `.env`
credential fallback.

The prepared HIWM profile uses one Alibaba Cloud credential for:

- `fun-asr-realtime` for streaming transcription;
- `qwen3-vl-flash` for lower-latency image/text structured HIWM inference;
- `cosyvoice-v3-flash` for speech synthesis.

`qwen3-vl-flash` supports image input and JSON mode with lower interactive
latency than the Omni Plus fallback. The handler uses a compact 2,048-token
response cap. Most turns make one request; only a strict-contract failure can
trigger one bounded repair request before the safe local fallback.
It is not a downloadable pre-trained HIWM. A dedicated, calibrated HIWM would
require consented state/action/response/outcome data and held-out evaluation.

## Run

```bash
bash scripts/start_macos.sh
```

Open <http://127.0.0.1:8283>. The UI and local perception can start with a
blank key; entering a real key on the setup screen enables cloud ASR/HIWM/TTS
for new sessions immediately, without restarting the service.

The original Qwen-Omni profile remains available:

```bash
HIWM_CONFIG=config/chat_with_qwen_omni_mac.yaml \
  bash scripts/start_macos.sh
```

## Verification

```bash
.venv/bin/python -m pytest -q tests/hiwm tests/rtc_client tests/security \
  tests/service tests/tts tests/chat_engine
```

The frontend must be built from source; do not copy the stale `dist` output
from another checkout:

```bash
cd frontend
pnpm install
pnpm run build
```

## Data locations

- Local service process memory: the API key entered on the setup screen; never
  returned by the API and cleared when the service stops.
- `.env`: optional ignored credential fallback for unattended startup; never
  returned by the API.
- `temp/hiwm_ledger/*.jsonl`: server prediction locks, mode `0600`.
- `temp/cloud_smoke_result.json`: aggregate component smoke result, mode `0600`.
- `temp/cloud_smoke_attempts/*.lock`: permanent per-mode one-shot cost guards,
  mode `0600` inside a `0700` directory. They are claimed before key access.
- Browser local storage: bounded derived event timeline and user-confirmed
  initial profile; both are removable in the UI.
- Raw ASR PCM dumps: disabled in `config/chat_with_hiwm_mac.yaml`.

## Manual device check

Automated tests cover permission timeout/recovery, bounded simulated face and
prosody frames, TTS echo gating, and derived event replay. They do not execute
a real MediaPipe camera or Web Audio hardware session. A final real-device check still requires this Mac's camera,
microphone, speaker, and a consenting person. The MediaPipe face model is loaded
from its configured CDN, so the first face-tracking run also needs network
access unless the model assets are vendored locally.
