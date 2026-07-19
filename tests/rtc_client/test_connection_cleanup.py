from __future__ import annotations

import pytest

from handlers.client.rtc_client.client_handler_rtc import close_webrtc_session


class _PeerConnection:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _Stream:
    def __init__(self):
        self.peer = _PeerConnection()
        self.connection = _Connection()
        self.pcs = {"rtc-1": self.peer}
        self.cleaned = []

    def clean_up(self, webrtc_id):
        self.cleaned.append(webrtc_id)
        return [self.connection] if webrtc_id == "rtc-1" else []


@pytest.mark.asyncio
async def test_explicit_close_releases_peer_and_media_callbacks_immediately():
    stream = _Stream()

    assert await close_webrtc_session(stream, "rtc-1") is True
    assert stream.pcs == {}
    assert stream.peer.closed is True
    assert stream.connection.stopped is True
    assert stream.cleaned == ["rtc-1"]


@pytest.mark.asyncio
async def test_explicit_close_is_idempotent_for_unknown_session():
    stream = _Stream()

    assert await close_webrtc_session(stream, "missing") is False
    assert stream.peer.closed is False
    assert stream.cleaned == ["missing"]
