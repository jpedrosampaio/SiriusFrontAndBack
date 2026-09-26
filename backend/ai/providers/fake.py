"""Deterministic provider for tests; never enabled through production configuration."""
from ai.providers.base import Provider
from ai.types import AIResult


class FakeAIProvider(Provider):
    def __init__(self, *responses):
        super().__init__()
        self.responses = list(responses)
        self.calls = []

    async def generate(self, model, key, request):
        self.calls.append((model, request))
        value = self.responses.pop(0) if self.responses else 'Resposta de teste'
        if isinstance(value, Exception):
            raise value
        return AIResult(text=value, provider=model.provider, model=model.name)
