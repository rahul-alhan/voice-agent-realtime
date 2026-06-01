"""Tool implementations exposed to the Realtime API model.

Retrieval is imported lazily so this module — and the TOOL_SPECS / execute()
shape tests — can run without Chroma / OpenAI installed.
"""
from __future__ import annotations

import json

TOOL_SPECS = [
    {
        "type": "function",
        "name": "search_knowledge_base",
        "description": "Search the internal knowledge base for facts before answering.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user's question or key phrase."},
                "top_k": {"type": "integer", "default": 4, "minimum": 1, "maximum": 8},
            },
            "required": ["query"],
        },
    }
]


def execute(name: str, args: dict) -> str:
    if name == "search_knowledge_base":
        from kb.retriever import search  # deferred
        results = search(query=args["query"], top_k=int(args.get("top_k", 4)))
        return json.dumps(results)
    return json.dumps({"error": "unknown_tool", "name": name})
