"""Thin wrapper over the OpenAI Realtime WebSocket."""
from __future__ import annotations

import asyncio
import base64
import json
import os

import websockets

from . import tools

SYSTEM_INSTRUCTIONS = (
    "You are a concise voice assistant. Speak naturally and briefly. "
    "Before answering anything factual, call search_knowledge_base. "
    "When you cite a fact, mention the source in your speech (e.g. 'according to the returns policy doc')."
)


class RealtimeAgent:
    def __init__(self, on_audio_out, on_event=None):
        self.url = "wss://api.openai.com/v1/realtime?model=" + os.getenv(
            "REALTIME_MODEL", "gpt-4o-realtime-preview"
        )
        self.headers = {
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "OpenAI-Beta": "realtime=v1",
        }
        self.on_audio_out = on_audio_out
        self.on_event = on_event or (lambda e: None)
        self.ws = None
        self._reader_task: asyncio.Task | None = None

    async def __aenter__(self):
        # websockets 13 renamed extra_headers -> additional_headers. Support
        # both so we don't pin downstream apps to a single websockets release.
        try:
            self.ws = await websockets.connect(
                self.url,
                additional_headers=self.headers,
                max_size=10 * 1024 * 1024,
            )
        except TypeError:
            self.ws = await websockets.connect(
                self.url,
                extra_headers=self.headers,
                max_size=10 * 1024 * 1024,
            )
        await self._send({
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "instructions": SYSTEM_INSTRUCTIONS,
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {"type": "server_vad", "threshold": 0.5},
                "tools": tools.TOOL_SPECS,
                "tool_choice": "auto",
            },
        })
        # Retain a strong reference so the reader task isn't garbage-collected
        # mid-stream (asyncio only holds a weak ref to background tasks).
        self._reader_task = asyncio.create_task(self._reader())
        return self

    async def __aexit__(self, *_):
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None
        if self.ws:
            await self.ws.close()

    async def _send(self, payload: dict):
        await self.ws.send(json.dumps(payload))

    async def send_audio_chunk(self, pcm: bytes):
        await self._send({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm).decode("ascii"),
        })

    async def cancel_response(self):
        """Barge-in handler."""
        await self._send({"type": "response.cancel"})

    async def _reader(self):
        async for raw in self.ws:
            evt = json.loads(raw)
            t = evt.get("type")
            self.on_event(evt)
            if t == "response.audio.delta":
                pcm = base64.b64decode(evt["delta"])
                self.on_audio_out(pcm)
            elif t == "response.function_call_arguments.done":
                name = evt["name"]
                args = json.loads(evt["arguments"] or "{}")
                result = tools.execute(name, args)
                await self._send({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": evt["call_id"],
                        "output": result,
                    },
                })
                await self._send({"type": "response.create"})
            elif t == "input_audio_buffer.speech_started":
                # user is speaking — interrupt any in-flight response
                await self.cancel_response()
