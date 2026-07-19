#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH=""
ENV_VARS=()

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -config | --config )
            if [[ "$#" -lt 2 ]]; then
                echo "Missing value for $1" >&2
                exit 2
            fi
            CONFIG_PATH="$2"
            shift 2
            ;;
    esac
done

# Determine config file path
CONFIG_FILE="${CONFIG_PATH:-config/chat_with_hiwm_zeabur.yaml}"

# Check for AvatarMusetalk module and set environment variables（if Musetalk is used, set PYTORCH_JIT=0）
if grep -q "AvatarMusetalk:" "$CONFIG_FILE" 2>/dev/null && grep -q "module: avatar/musetalk/avatar_handler_musetalk" "$CONFIG_FILE" 2>/dev/null; then
    echo "Detected AvatarMusetalk module, adding PYTORCH_JIT=0 environment variable"
    ENV_VARS=(-e PYTORCH_JIT=0)
else
    echo "No AvatarMusetalk module detected in config, skipping PYTORCH_JIT environment variable"
fi

docker run --rm --gpus all -it --name hiwm-interaction-engine \
    --network=host \
    "${ENV_VARS[@]}" \
    -v "$(pwd)"/build:/root/hiwm-interaction-engine/build \
    -v "$(pwd)"/models:/root/hiwm-interaction-engine/models \
    -v "$(pwd)"/ssl_certs:/root/hiwm-interaction-engine/ssl_certs \
    -v "$(pwd)"/config:/root/hiwm-interaction-engine/config \
    -v "$(pwd)"/.env:/root/hiwm-interaction-engine/.env \
    -v "$(pwd)"/models/musetalk/s3fd-619a316812/:/root/.cache/torch/hub/checkpoints/ \
    -v "$(pwd)"/exp:/root/hiwm-interaction-engine/exp \
    -v "$(pwd)"/resource:/root/hiwm-interaction-engine/resource \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=compute,video,utility \
    -p 8080:8080 \
    hiwm-interaction-engine:latest \
    --config "${CONFIG_PATH:-config/chat_with_hiwm_zeabur.yaml}"
