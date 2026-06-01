"""Mic capture + speaker playback in 16 kHz mono PCM16."""
from __future__ import annotations

import asyncio
import queue

import numpy as np

SAMPLE_RATE = 16_000
DTYPE = "int16"
CHUNK_MS = 40
FRAMES_PER_CHUNK = SAMPLE_RATE * CHUNK_MS // 1000


class Microphone:
    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        import sounddevice as sd
        self._sd = sd
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        # sounddevice invokes _callback on a native PortAudio thread, so we
        # must hop back onto the asyncio loop before touching the Queue —
        # asyncio.Queue is NOT thread-safe.
        self._loop = loop or asyncio.get_event_loop()
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"mic status: {status}")
        self._loop.call_soon_threadsafe(self._queue.put_nowait, bytes(indata))

    def start(self):
        self._stream = self._sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAMES_PER_CHUNK,
            dtype=DTYPE,
            channels=1,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def frames(self):
        while True:
            yield await self._queue.get()


class Speaker:
    """Simple PCM16 ring-buffer playback."""

    def __init__(self):
        import sounddevice as sd
        self._sd = sd
        self._stream = self._sd.RawOutputStream(
            samplerate=SAMPLE_RATE, dtype=DTYPE, channels=1,
        )
        self._stream.start()

    def write(self, pcm: bytes) -> None:
        if pcm:
            self._stream.write(pcm)

    def clear(self) -> None:
        # crude — for true barge-in, drop pending writes by recreating the stream
        try:
            self._stream.abort()
        except Exception:
            pass
        self._stream = self._sd.RawOutputStream(
            samplerate=SAMPLE_RATE, dtype=DTYPE, channels=1,
        )
        self._stream.start()
