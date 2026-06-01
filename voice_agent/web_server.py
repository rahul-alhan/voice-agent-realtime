"""Browser demo — relays WebSocket audio between browser <-> Realtime API."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .realtime_client import RealtimeAgent

log = logging.getLogger(__name__)

# Require a shared bearer-style token at startup so the /ws endpoint
# cannot be opened by anonymous callers (which would otherwise consume
# the server-side OPENAI_API_KEY-backed Realtime session).
VOICE_AGENT_TOKEN = os.environ.get("VOICE_AGENT_TOKEN")
if not VOICE_AGENT_TOKEN:
    raise RuntimeError(
        "VOICE_AGENT_TOKEN env var is required to start the web server. "
        "Set it to a random secret and pass the same value as ?token=... "
        "from the browser client."
    )

# Hard cap on the size of a single audio frame from the browser.
# 16 kHz mono PCM16 @ ~2s ≈ 64 KB; anything larger is almost certainly
# abuse and would balloon our outbound Realtime traffic.
MAX_AUDIO_BYTES = 64_000

app = FastAPI()

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.websocket("/ws")
async def ws(client: WebSocket):
    # Authenticate BEFORE accepting the upgrade so unauthorized callers
    # never get a Realtime-backed session attached to them.
    token = client.query_params.get("token")
    if not token or token != VOICE_AGENT_TOKEN:
        await client.close(code=1008, reason="unauthorized")
        return

    await client.accept()
    queue: asyncio.Queue[bytes] = asyncio.Queue()

    def on_audio_out(pcm: bytes) -> None:
        queue.put_nowait(pcm)

    async with RealtimeAgent(on_audio_out=on_audio_out) as agent:
        async def relay_out():
            while True:
                pcm = await queue.get()
                await client.send_bytes(pcm)

        out_task = asyncio.create_task(relay_out())
        try:
            while True:
                pcm = await client.receive_bytes()
                if len(pcm) > MAX_AUDIO_BYTES:
                    log.warning(
                        "dropping oversize audio frame from /ws client: %d bytes (max %d)",
                        len(pcm),
                        MAX_AUDIO_BYTES,
                    )
                    await client.close(code=1009, reason="frame too large")
                    return
                await agent.send_audio_chunk(pcm)
        except WebSocketDisconnect:
            pass
        finally:
            out_task.cancel()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
