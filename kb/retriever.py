"""Tiny retrieval wrapper, shared with the tool layer."""
from __future__ import annotations

import os
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .build_index import COLLECTION


@lru_cache(maxsize=1)
def _vec():
    return Chroma(
        persist_directory=os.getenv("KB_CHROMA_DIR", ".chroma"),
        collection_name=COLLECTION,
        embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    )


def search(query: str, top_k: int = 4) -> list[dict]:
    hits = _vec().similarity_search(query, k=top_k)
    return [
        {"text": h.page_content, "source": h.metadata.get("source", "")}
        for h in hits
    ]
