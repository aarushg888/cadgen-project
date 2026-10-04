"""Thin OpenAI-compatible chat client (works with OpenAI, vLLM, Ollama, llama.cpp server, LM Studio)."""
from __future__ import annotations

import os


class ChatClient:
    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 2048):
        from openai import OpenAI  # pip install openai
        self.client = OpenAI(base_url=base_url, api_key=api_key or os.environ.get("OPENAI_API_KEY", "none"))
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens

    def complete(self, messages: list[dict], n: int = 1) -> list[str]:
        r = self.client.chat.completions.create(model=self.model, messages=messages, n=n,
                                                temperature=self.temperature, max_tokens=self.max_tokens)
        return [c.message.content or "" for c in r.choices]
