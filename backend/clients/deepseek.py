"""DeepSeek (OpenAI-compatible) LangChain client -- slice 2a rerank + slice 2b LLM nodes 共用."""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from backend.config import get_settings


def build_chat_client(*, temperature: float = 0.0, **kwargs) -> ChatOpenAI:
    """每次新建一个 client；用于 temperature 不同的场景。"""
    s = get_settings()
    if not s.deepseek_api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is empty. Set it in .env before using DeepSeek."
        )
    return ChatOpenAI(
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        model=s.deepseek_model,
        temperature=temperature,
        **kwargs,
    )


@lru_cache(maxsize=1)
def get_deepseek_client() -> ChatOpenAI:
    """temperature=0 的默认单例，给 rerank / classifier 这类要求确定性的节点用。"""
    return build_chat_client(temperature=0.0)
