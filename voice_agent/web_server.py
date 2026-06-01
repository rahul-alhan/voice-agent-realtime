"""Browser demo — relays WebSocket audio between browser <-> Realtime API."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .realtime_client import RealtimeAgent

app = FastAPI()

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.websocket("/ws")
async def ws(client: WebSocket):
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
