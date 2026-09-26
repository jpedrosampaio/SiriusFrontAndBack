"""Model catalogue verified against official provider docs on 2026-09-26."""
import os
from dataclasses import dataclass, field


def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in ('1', 'true', 'yes')


@dataclass(frozen=True)
class Model:
    provider: str
    name: str
    capabilities: frozenset
    free_tier: bool = True


MODELS = {
    'flash': Model('gemini', 'gemini-3.8-flash', frozenset({'text', 'json', 'tools', 'pdf', 'image', 'audio'})),
    'lite': Model('gemini', 'gemini-3.5-flash-lite', frozenset({'text', 'json', 'tools', 'pdf', 'image', 'audio'})),
    'reasoning': Model('groq', 'openai/gpt-oss-120b', frozenset({'text', 'json', 'tools'})),
    'fast': Model('groq', 'openai/gpt-oss-20b', frozenset({'text', 'json', 'tools'})),
    'vision': Model('groq', 'qwen/qwen3.8-27b', frozenset({'text', 'json', 'tools', 'image'})),
    'embedding': Model('gemini', 'gemini-embedding-2', frozenset({'embedding'})),
    'stt': Model('groq', 'whisper-large-v3-turbo', frozenset({'speech_to_text'})),
    'tts': Model('gemini', 'gemini-3.8-flash-lite-tts', frozenset({'text_to_speech'})),
}
TASKS = {
    'assistant_chat': ('reasoning', 'flash', 'fast', 'lite'),
    'assistant_reasoning': ('reasoning', 'flash', 'fast', 'lite'),
    'quick_classification': ('lite', 'fast', 'flash'),
    'structured_extraction': ('flash', 'reasoning', 'lite'),
    'edital_extract': ('flash', 'lite'),
    'edital_verify': ('reasoning', 'fast'),
    'document_analysis': ('flash', 'lite'),
    'image_analysis': ('flash', 'vision', 'lite'),
    'report_analysis': ('reasoning', 'flash', 'lite'),
    'study_explanation': ('reasoning', 'flash', 'lite'),
    'study_question_generation': ('flash', 'reasoning', 'lite'),
    'workout_generation': ('flash', 'reasoning', 'lite'),
    'nutrition_generation': ('flash', 'reasoning', 'lite'),
    'mindmap_generation': ('flash', 'reasoning', 'lite'),
    'embedding': ('embedding',),
    'speech_to_text': ('stt', 'flash'),
    'text_to_speech': ('tts',),
}


@dataclass
class Settings:
    paid: bool = field(default_factory=lambda: flag('AI_PAID_MODELS_ENABLED'))
    agent: bool = field(default_factory=lambda: flag('AI_AGENT_ENABLED', True))
    rag: bool = field(default_factory=lambda: flag('AI_RAG_ENABLED', True))
    voice: bool = field(default_factory=lambda: flag('AI_VOICE_ENABLED', True))
    automations: bool = field(default_factory=lambda: flag('AI_AUTOMATIONS_ENABLED', True))
    auto_actions: bool = field(default_factory=lambda: flag('AI_AUTO_ACTIONS_ENABLED'))
    streaming: bool = field(default_factory=lambda: flag('AI_STREAMING_ENABLED'))
    dry_run: bool = field(default_factory=lambda: flag('AUTOMATION_DRY_RUN', True))
    live_tests: bool = field(default_factory=lambda: flag('RUN_AI_LIVE_TESTS'))
    context_messages: int = field(default_factory=lambda: min(30, max(2, int(os.getenv('AI_CONTEXT_MESSAGES', '12')))))
    context_chars: int = field(default_factory=lambda: min(32000, max(2000, int(os.getenv('AI_CONTEXT_CHARS', '18000')))))
    daily_limit: int = field(default_factory=lambda: max(1, int(os.getenv('AI_INTERNAL_DAILY_LIMIT', '200'))))
    timeout: int = 45

    def route(self, task):
        if task not in TASKS:
            raise ValueError('Unknown AI task')
        # Overrides select catalogue entries, not arbitrary billable model IDs.
        names = os.getenv('AI_ROUTE_' + task.upper(), ','.join(TASKS[task])).split(',')
        return [MODELS[name.strip()] for name in names if name.strip() in MODELS
                and (self.paid or MODELS[name.strip()].free_tier)]

    def flags(self):
        return {name: getattr(self, name) for name in ('agent', 'rag', 'voice', 'automations', 'auto_actions', 'streaming', 'dry_run', 'paid')}
