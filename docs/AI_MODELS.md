# Modelos e provedores — verificação em 26/09/2026

Fontes primárias: [modelos Gemini](https://ai.google.dev/gemini-api/docs/models), [preços Gemini](https://ai.google.dev/gemini-api/docs/pricing), [limites Groq](https://console.groq.com/docs/rate-limits), [structured outputs](https://console.groq.com/docs/structured-outputs), [visão Groq](https://console.groq.com/docs/vision), [STT Groq](https://console.groq.com/docs/speech-to-text).

| Uso | Principal | Alternativa |
| --- | --- | --- |
| Conversa/raciocínio | Groq `openai/gpt-oss-120b` | Gemini `gemini-3.8-flash`, GPT-OSS 20B, Flash-Lite |
| PDF/extração | Gemini `gemini-3.8-flash` | `gemini-3.5-flash-lite` |
| Simples | `gemini-3.5-flash-lite` | GPT-OSS 20B |
| Imagem | Gemini Flash | Groq `qwen/qwen3.8-27b` |
| Embeddings | `gemini-embedding-2` | busca textual local, explicitamente não semântica |
| STT | Groq `whisper-large-v3-turbo` | áudio no Gemini Flash |
| TTS opcional | `gemini-3.8-flash-lite-tts` | voz do navegador, quando disponível |

O catálogo contém somente opções com faixa gratuita documentada. O modo pago fica desativado e não há configuração de cobrança. Uma chave vinculada a uma conta que já possui billing segue as regras dessa conta: o aplicativo não consegue transformar essa conta em gratuita nem garantir gratuidade a partir do texto da chave. Use contas/chaves free-tier para não incorrer em cobrança. O sistema nunca ativa billing.

IDs e rotas ficam exclusivamente em `ai/config.py`; overrides selecionam entradas auditadas do catálogo. Limites reais variam por conta e devem ser vistos no console do provedor. O limite diário interno é um teto do Sirius, não uma declaração de saldo de quota do provedor. Respostas 429 ativam cooldown/fallback gratuito.

Groq não combina structured output com streaming/tool use na mesma requisição; os modos ficam separados. JSON é validado localmente, e mensagens inválidas não se transformam silenciosamente em saída sem schema. Conteúdo recuperado nunca ocupa o papel de instrução interna.
