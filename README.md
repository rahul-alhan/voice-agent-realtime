# Voice Agent — Realtime API + RAG

A minimal but production-shaped **voice agent**: speak a question into your mic, the agent retrieves from a RAG knowledge base, and answers back in voice — sub-second turn-around. Built on the **OpenAI Realtime API** (WebSocket) with **function-calling** into the same retriever used elsewhere in this portfolio.

> Targets the fastest-growing agentic surface of 2026: real-time voice. A single repo demonstrates streaming audio, tool use, and RAG together — the three primitives every voice-agent JD asks about.

---

## What This Demonstrates

| Capability | How |
|---|---|
| Real-time **speech-in** | mic → WebSocket → server-side VAD |
| Real-time **speech-out** | streamed PCM frames → speaker |
| **Function calling** mid-conversation | model calls `search_knowledge_base` during the turn |
| **Barge-in / interrupt** | user can speak over the agent; the agent stops talking |
| **Grounded answers** | every spoken answer cites a `source` (mentioned in speech) |

---

## Architecture

```
   🎙  mic ──▶  PCM frames ──▶  WebSocket  ──▶  OpenAI Realtime API
                                                        │
                                          ┌─────────────┤
                                          ▼             │
                              tool call: search_kb      │
                                          │             │
                                          ▼             │
                                   kb/retriever.py      │
                                          │             │
                                          ▼             │
                                 retrieved context  ────┘
                                          │
                                          ▼
                              streamed audio response
                                          │
                                          ▼
                                       🔊 speaker
```

---

## Quickstart

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...

# 1. Build the small KB index (re-uses the same indexing pattern as rag-pipeline-demo)
python -m kb.build_index --docs docs/ --persist .chroma/

# 2. Run the voice agent (push-to-talk style; press Enter to start/stop)
python -m voice_agent.run

# Or: web demo — browser handles mic + speaker
python -m voice_agent.web_server --port 8000
# open http://localhost:8000
```

---

## Running Tests

Dev dependencies (including `pytest`) are kept separate from runtime deps so the production install stays slim.

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Pytest config lives in `pyproject.toml` (`testpaths`, `pythonpath`, and `cache_dir` are pinned there so `pytest` works the same locally and in CI).

---

## Audio Pipeline

| Stage | Choice | Why |
|---|---|---|
| Input format | 16 kHz mono PCM16 | Realtime API requirement |
| Capture | `sounddevice` (PortAudio) | minimal deps, cross-platform |
| Server VAD | `server_vad` mode | Realtime API detects start/end of speech — no client-side VAD needed |
| Output buffering | small ring buffer | reduces audio glitches under variable network |
| Barge-in | `response.cancel` event | sent the moment new user audio is detected |

---

## Function Calling

The agent has one tool registered: `search_knowledge_base(query, top_k)`. When the model decides it needs facts, it emits a `response.function_call_arguments.delta` stream, the client executes the tool against the local Chroma index, and returns the result. The model then resumes speaking with the retrieved context.

```python
TOOLS = [
    {
        "type": "function",
        "name": "search_knowledge_base",
        "description": "Search the internal knowledge base for facts.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
    }
]
```

---

## Repository Layout

```
voice-agent-realtime/
├── README.md
├── requirements.txt
├── LICENSE
├── .gitignore
├── .env.example
├── docs/
│   └── kb_sample.md
├── kb/
│   ├── __init__.py
│   ├── build_index.py
│   └── retriever.py
├── voice_agent/
│   ├── __init__.py
│   ├── audio.py              # mic / speaker capture + playback
│   ├── realtime_client.py    # WebSocket + protocol handling
│   ├── tools.py              # function-call implementations
│   ├── run.py                # CLI push-to-talk
│   └── web_server.py         # browser demo (WebSocket bridge)
├── web/
│   └── index.html            # tiny static page for the web demo
└── tests/
    └── test_audio_buffer.py
```

---

## Design Choices

| Decision | Rationale |
|---|---|
| **Realtime API over chained STT→LLM→TTS** | Lower latency, native barge-in, single connection |
| **Server-side VAD** | One less component to tune; Realtime API does it well |
| **PCM16 over Opus** | Realtime API expects PCM; reduces complexity |
| **Local retrieval** | Round-tripping retrieval to a remote service adds 100ms+; we want sub-second |
| **`response.cancel` on barge-in** | The single most important UX detail in voice agents |

---

## Production Notes

In a real deployment this would be:
- **Twilio Voice** as the carrier — audio piped over Twilio Media Streams → WebSocket → Realtime API
- **Latency budget**: 50ms network in, 200ms model + first audio frame, 50ms network out — ≤300ms total turn-around
- **Cost guardrails**: maximum session length, max tool-call depth, hangup on inactivity (kills runaway $$$)
- **Recording + redaction**: every call recorded for QA, but with PII redaction on storage
- **Fallback to text chat** if audio quality drops below a threshold (silent fail is worse than asking the user to type)

---

## Why this is short

Voice-agent demos look impressive but are *less code* than people expect — the value is the **handful of UX details done right**: low-latency, barge-in, grounded retrieval, sane cost guardrails. This repo focuses on those, not on padding.

---

## License

MIT
