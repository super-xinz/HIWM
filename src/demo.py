from chat_engine.chat_engine import ChatEngine
import gradio as gr
import importlib.util
import os
import argparse
import signal
import sys

import gradio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger

from engine_utils.directory_info import DirectoryInfo
from service.service_utils.logger_utils import config_loggers
from service.service_utils.service_config_loader import load_configs
from service.service_utils.ssl_helpers import create_ssl_context
from service.frontend_service import require_runtime_control_access
from project_identity import PROJECT_NAME, PROJECT_VERSION

project_dir = DirectoryInfo.get_project_dir()
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, help="service host address")
    parser.add_argument("--port", type=int, help="service host port")
    parser.add_argument(
        "--config",
        type=str,
        default="config/chat_with_hiwm_mac.yaml",
        help="config file to use",
    )
    parser.add_argument("--env", type=str, default="default", help="environment to use in config file")
    return parser.parse_args()

# The API-only runtime intentionally has no PyTorch dependency on macOS.
# GPU-backed handlers still receive the compatibility patch on Linux/CUDA.
if importlib.util.find_spec("torch") is not None:
    import torch

    _original_torch_load = torch.load

    def patched_torch_load(*args, **kwargs):
        if kwargs.get("weights_only") is not True:
            kwargs["weights_only"] = False
        return _original_torch_load(*args, **kwargs)

    torch.load = patched_torch_load

class HIWMWebServer(uvicorn.Server):

    def __init__(self, chat_engine: ChatEngine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_engine = chat_engine

    async def shutdown(self, sockets=None):
        logger.info("Start normal shutdown process")
        self.chat_engine.shutdown()
        await super().shutdown(sockets)


def setup_demo():
    """设置 FastAPI 应用和 Gradio 界面"""
    app = FastAPI(
        title=PROJECT_NAME,
        version=PROJECT_VERSION,
        docs_url=None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def protect_remote_webrtc_control(request: Request, call_next):
        # Fastrtc mounts the offer route internally, so protect it at the app
        # boundary. Static UI, initialization, and health routes stay public so
        # the setup page can explain which credential is required.
        if request.method == "POST" and request.url.path.startswith("/webrtc/"):
            try:
                require_runtime_control_access(request)
            except HTTPException as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                    headers=exc.headers,
                )
        return await call_next(request)

    css = """

    .app {
        @media screen and (max-width: 768px) {
            padding: 8px !important;
        }
    }
    footer {
        display: none !important;
    }
    """
    with gr.Blocks(css=css) as gradio_block:
        with gr.Column():
            with gr.Group() as rtc_container:
                pass

    gradio.mount_gradio_app(app, gradio_block, "/gradio")
    return app, gradio_block, rtc_container


def main():
    args = parse_args()
    config_from_env = os.environ.get("HIWM_CONFIG") or os.environ.get(
        "OPEN_AVATAR_CHAT_CONFIG"
    )
    if  config_from_env:
        args.config = config_from_env
    logger_config, service_config, engine_config = load_configs(args)

    # 设置modelscope的默认下载地址
    if not os.path.isabs(engine_config.model_root):
        os.environ['MODELSCOPE_CACHE'] = os.path.join(DirectoryInfo.get_project_dir(),
                                                      engine_config.model_root.replace('models', ''))

    config_loggers(logger_config)

    demo_app, ui, parent_block = setup_demo()

    chat_engine = ChatEngine()
    chat_engine.initialize(engine_config, app=demo_app, ui=ui, parent_block=parent_block)

    ssl_context = create_ssl_context(args, service_config)

    uvicorn_config = uvicorn.Config(demo_app, host=service_config.host, port=service_config.port, **ssl_context)
    server = HIWMWebServer(chat_engine, uvicorn_config)
    server.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, exiting.")
    finally:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os._exit(0)
