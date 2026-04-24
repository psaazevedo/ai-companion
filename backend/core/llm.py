from __future__ import annotations

from typing import AsyncIterator

from openai import AsyncOpenAI

from config import get_settings


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = (
            AsyncOpenAI(
                api_key=self.settings.groq_api_key,
                base_url=self.settings.groq_base_url,
            )
            if self.settings.groq_api_key
            else None
        )

    @property
    def is_mock_mode(self) -> bool:
        return not self.settings.llm_enabled

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.llm_enabled or self.client is None:
            return self._mock_reply(user_prompt)

        completion = await self.client.chat.completions.create(
            model=self.settings.groq_chat_model,
            max_tokens=400,
            temperature=0.4,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
        )
        text = completion.choices[0].message.content
        if isinstance(text, str) and text.strip():
            return text.strip()
        return self._mock_reply(user_prompt)

    async def complete_stream(
        self, system_prompt: str, user_prompt: str
    ) -> AsyncIterator[str]:
        if not self.settings.llm_enabled or self.client is None:
            for chunk in self._chunk_mock_reply(self._mock_reply(user_prompt)):
                yield chunk
            return

        stream = await self.client.chat.completions.create(
            model=self.settings.groq_chat_model,
            max_tokens=400,
            temperature=0.4,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
        )

        async for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta.content
            if isinstance(delta, str) and delta:
                yield delta

    def _mock_reply(self, user_prompt: str) -> str:
        message = self._extract_current_message(user_prompt)
        return (
            "I’m here with you. "
            "Groq is not configured yet, so this is a scaffolded reply. "
            f"What I heard was: \"{message}\""
        )

    def _extract_current_message(self, prompt: str) -> str:
        marker = "Current user message:"
        if marker not in prompt:
            return prompt.strip()
        return prompt.split(marker, maxsplit=1)[1].strip()

    def _chunk_mock_reply(self, text: str) -> list[str]:
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= 28:
                current = candidate
                continue

            chunks.append(current + " ")
            current = word

        if current:
            chunks.append(current)

        return chunks
