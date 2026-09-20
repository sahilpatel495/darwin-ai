"""Scripted LLM for tests: no network, deterministic, records what it was sent."""

from __future__ import annotations

from app.llm.client import LLMResult, Role


class FakeLLM:
    def __init__(self, scripted: dict[str, list[str]]):
        self._scripted = {role: list(items) for role, items in scripted.items()}
        self.calls: list[dict] = []

    def complete(
        self, *, role: Role, messages: list[dict[str, str]], json_schema: dict | None = None
    ) -> LLMResult:
        self.calls.append({"role": role, "messages": messages, "json_schema": json_schema})
        queue = self._scripted.get(role) or []
        assert queue, f"FakeLLM has no scripted response left for role {role!r}"
        return LLMResult(content=queue.pop(0), provider="fake", model=f"fake-{role}")
