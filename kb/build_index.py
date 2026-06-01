"""Build a tiny Chroma index from the docs/ folder."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

COLLECTION = "voice_kb"


def build(docs_dir: str, persist_dir: str):
    paths = list(Path(docs_dir).rglob("*.md")) + list(Path(docs_dir).rglob("*.txt"))
    docs = []
    for p in paths:
        docs.extend(TextLoader(str(p), encoding="utf-8").load())

    chunks = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40).split_documents(docs)
    for c in chunks:
        c.metadata["source"] = Path(c.metadata.get("source", paths[0])).name

    Chroma.from_documents(
        documents=chunks,
        embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        persist_directory=persist_dir,
        collection_name=COLLECTION,
    )
    print(f"Indexed {len(chunks)} chunks → {persist_dir}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--docs", default="docs")
    p.add_argument("--persist", default=os.getenv("KB_CHROMA_DIR", ".chroma"))
    args = p.parse_args()
    build(args.docs, args.persist)


if __name__ == "__main__":
    main()
