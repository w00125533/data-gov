"""离线构建语义检索索引到 ./data/chroma/ (与 FastAPI 启动构建幂等等价)。"""
from __future__ import annotations

import sys

from backend.config import get_settings
from backend.search.docs import build_docs_from_neo4j
from backend.search.embedder import Embedder
from backend.search.searcher import HybridSearcher


def main() -> int:
    s = get_settings()
    print(f"Loading bge model: {s.search_embed_model}")
    emb = Embedder(model_name=s.search_embed_model, chroma_dir=s.search_chroma_dir)
    if not emb.available:
        print("ERROR: bge model unavailable; index NOT built.", file=sys.stderr)
        return 1
    print("Reading metadata from Neo4j ...")
    docs = build_docs_from_neo4j()
    searcher = HybridSearcher(embedder=emb)
    searcher.build_index(docs)
    print(f"Index built: {len(docs)} docs, version={searcher.get_index_version()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
