"""CLI entrypoint — push-to-talk; press Enter to stop."""
from __future__ import annotations

import asyncio
import sys

from .audio import Microphone, Speaker
from .realtime_client import RealtimeAgent


async def amain():
    speaker = Speaker()
    mic = Microphone()

    def on_event(evt: dict) -> None:
        t = evt.get("type", "")
        # surface a few interesting events; everything else is silent
        if t in {"response.audio_transcript.done", "response.text.done"}:
            print(f"\n[agent] {evt.get('transcript') or evt.get('text', '')}")
        elif t == "conversation.item.input_audio_transcription.completed":
            print(f"\n[you  ] {evt.get('transcript', '')}")
        elif t == "error":
            print(f"\n[error] {evt}")

    async with RealtimeAgent(on_audio_out=speaker.write, on_event=on_event) as agent:
        print("Voice agent is listening. Press Ctrl+C to quit.")
        mic.start()
        try:
            async for frame in mic.frames():
                await agent.send_audio_chunk(frame)
        finally:
            mic.stop()


def main():
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("\nBye.")
        sys.exit(0)


if __name__ == "__main__":
    main()
