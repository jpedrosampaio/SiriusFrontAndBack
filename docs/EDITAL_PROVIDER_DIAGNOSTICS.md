# Edital: structured transport, recovery and controlled homologation

## Issue65 — current transport follow-up

### Real pilot after PR66: still blocked

Latest follow-up: PR67 published diagnostics as merge
`b44e864b5ee541e20d6c1d41d72640c29e9f05ba`, with all four head/merge workflows,
clean Codex review and exact Vercel/Northflank/read-only production checks passed.
The owner's next separately authorized attempt at `2026-10-21T11:52:53.174Z`
also failed: reference `0434ab82-659a-4f94-be93-cd88fc3ff0a0`, same inventory
unit/model/schema and transport/3, HTTP400, no fallback, 4930.2 ms. The finite
diagnostic was `code=400`, `status=INVALID_ARGUMENT`, `category=unspecified`,
`fields=[]`. This means the sanitized classifier did not identify a public
parameter; it is not evidence that Google named none in its discarded raw
message. Seven calls shown are the unit's count. No canonical/documentary
validation or unit consolidation succeeded; that one-attempt consent is spent.

The workspace follow-up displays these already-stored finite fields prominently,
with separate analysis-wide and per-unit counters, real checkpoint progress,
source navigation and explicit paused states. The copy action is user-triggered,
local-only and includes only public allowlisted metadata; it does not call the
provider or copy file/prompt/body data. Legacy failures remain readable without
inventing absent details. The visual change does not repair or silently bypass
an unknown upstream400. The owner supplied an existing successful
`workout_generation` log for `gemini-3.8-flash` at `2026-10-16T01:56:03.868Z`
(38855.5 ms, no fallback, 6209 reported total tokens). This establishes historical
success for that task, not contemporary structured-output acceptance or that the
same credential/configuration was used. The workout route uses `call_llm`
without an output schema (8192 output tokens, 90-second timeout), then parses
and validates its JSON locally. Inventory uses its Pydantic contract in the
transport (3072 output tokens, 45-second timeout) and documentary checks after
local validation. Both use the shared Gemini provider; the successful log also
predates PR66's transport change. No fresh provider call was made to compare them.
Do not claim a cause, request a new
upload, change privacy/validation or repeat real attempts without fresh consent.

### One-attempt differential diagnostics

The saved inventory can offer three separately confirmed diagnostic cases:
plain text, a minimal JSON schema, and the real canonical InventoryUnit schema
with fixed synthetic input. These isolate basic request acceptance, structured
format acceptance and contract acceptance; none establishes documentary quality.
The existing router/provider, system instruction, output budget and timeout are
retained. The diagnostic pins Gemini 3.8 Flash and forbids fallback or a second
attempt. A route override to another model fails before provider I/O.

Each case requires its own explicit `resume` confirmation (`mode=pilot`,
`diagnostic_case=text|json|inventory`). It consumes the existing saved attempt
budget without accepting a limit extension. Existing ownership, revision,
idempotency, account locks, live leases and cooldown checks apply. The diagnostic
field is omitted from receipt fingerprints when absent, preserving resume
receipts created before this addition; changing a replay into a diagnostic is
still rejected as a different action. The diagnostic
snapshot does not even load source blocks: neither PDF text nor its manifest is
included in the prompt. A fixed synthetic prompt is sent; secrets remain only
in the provider header. Tests use MockTransport, never real AI.

A successful technical response creates only an allowlisted diagnostic receipt.
It does not persist response text/data, complete/split a real unit, consolidate
roles, mark the provider/document pilot validated, import content, award XP, or
release the queue. Both success and failure pause automatically; cancellation
fences late responses. Malformed synthetic output cannot split the real PDF's
checkpoint. Full execution still requires a separately successful documentary
pilot and separate owner authorization. An accepted technical case must not be
reported as a resolved Issue65. Inspect its evidence before choosing whether a
different case is necessary; never run all three automatically.

PR66 deployed merge `2eaff991f55311f93a38f506d12812179b8f0b7e`; its
[publication receipt](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/66#issuecomment-6306947091)
and [four successful merge workflows](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/66#issuecomment-6306980333)
do not establish real provider acceptance. The owner subsequently authorized
one manual attempt. At `2026-10-21T11:00:02.527Z`, its router log recorded
`gemini/gemini-3.8-flash`, inventory unit `12a466e5-2608-4286-8e06-782604e487ac`,
reference `4c195c90-025a-42cf-8748-0652276f9039`, HTTP400,
`request_rejected`, `structured-transport/3`, `gemini_response_format`,
schema SHA256 `12e4a11144bf234144434ac9a971a38be56765e8c636af9d829ea64a8201d556`,
2315 schema bytes, 6279.8 ms and no fallback. No unit was validated. The six
calls shown in that unit's diagnostics are not the analysis-wide counter.

This proves the new transport was used and rejected; it does not identify the
rejected parameter or establish schema size, API key, timeout or `store:false`
as the cause. Both response envelopes and `store` remain declared in the public
Discovery/API reference. Do not change them speculatively or repeat inference.
The one-attempt authorization is spent; any future attempt requires new consent.

The diagnostic follow-up preserves the exact payload, routing, transport
version, canonical/evidence validation, checkpoints and budget. HTTP400 errors
may additionally carry `provider_rejection`: a bounded numeric code, allowlisted
status/category and at most eight known public request paths. The parser reads
only bounded error text/field violations and returns constants, never message
fragments. Unknown fields stay absent; arbitrary schema property paths collapse
to the public schema prefix. Unknown/raw metadata is filtered again on cache,
error construction and owned API reads. No private provider body, key, prompt,
document content or arbitrary field name is retained. A generic provider400
without recognized details honestly remains `unspecified` with no field names.
An instrumentation release alone does not resolve Issue65 or authorize inference.

### Transport investigation preceding that pilot

The owner reports another real HTTP400 on `gemini-3.8-flash`, reference
`45b9ce8a-2e3c-4b8f-b633-bf0e8c9983e1`, after PR63: zero of 67 inventory
units validated, seven of 120 attempts reserved, minimum known total 141.
PR64's deletion controls are integrated separately and must be preserved.

Audited request: `GeminiProvider.generate()` posts directly to
`v1beta/models/{model}:generateContent` with the API key in a header, `store:false`,
text contents/system instruction and `maxOutputTokens`. The previous structured
envelope was `generationConfig.responseMimeType="application/json"` plus
`responseJsonSchema`. The current REST example instead specifies:

```json
{"generationConfig":{"responseFormat":{"text":{"mimeType":"APPLICATION_JSON","schema":{"type":"object"}}}}}}
```

The [official REST structured-output example](https://ai.google.dev/gemini-api/docs/generate-content/structured-output#rest)
and [TextResponseFormat reference](https://ai.google.dev/api/generate-content#TextResponseFormat)
use the enum `APPLICATION_JSON`. The SDK's `application/json` string cannot simply
be copied to that enum field: independent Discovery validation rejects it.
The [public v1beta Discovery](https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta),
revision `20261019` retrieved on 20 October 2026, still declares the legacy fields too.
**Therefore deprecation does not establish that the old envelope caused the
production HTTP400.** The historical sanitized error does not identify a rejected
parameter. No mock is presented as proof that Google rejected it.

The provider now uses the recommended envelope and enum, omitting all legacy
format fields. Schema projection, original Pydantic/JSON Schema, documentary
coverage and consolidation gates are unchanged. Plain chat/tools, PDF extraction,
the saved IR, unit keys, histories and budgets are unchanged. There is no JSON-only
fallback, implicit retry, new upload, limit extension or new migration.
Transport version 3 invalidates earlier transport approvals without resetting
their records or attempt counters; execution still needs the owner's new pilot
authorization and stops after one actual provider attempt.

On provider failure, safe diagnostics additionally identify the request format,
SHA-256 and byte count of the public transport schema, alongside the existing
model/task/unit/reference/status. Field/enum incompatibilities are allowlisted
categories, not raw provider messages. Request text, PDF, prompts, response bodies
and credentials remain excluded; cached failures retain metadata without private
tracebacks. This allows the next authorized pilot to distinguish an envelope
failure from schema complexity and actual validated/consolidated success.

`tests/fixtures/gemini_generate_content_discovery.json` preserves selected vendor
schema facts with revision/source/digest; it contains no keys or document data.
Mock HTTP captures the exact provider payload for a minimal schema and all four
real contracts on both Gemini models. The matrix explicitly proves that both
legacy and current envelopes remain declared, that the wrong new MIME enum is
invalid, and that local canonical validation remains mandatory. A real disposable
PostgreSQL worker test extracts a cited synthetic role through HTTP/Pydantic/
evidence/consolidation and then pauses. **These are contract tests, not real
Gemini homologation. Issue65 must remain open until one authorized real unit
validates and completes its checkpoint.** Publication alone does not meet that
acceptance criterion. The manual procedure below still applies, with the new
transport version; obtain separate authorization before its first real call and
again before any of the remaining 67 units.

## Incident and evidence boundary

The owner confirmed that the real textual 70-page PDF passed extraction after
PR62. Semantic discovery then stopped with zero of 67 inventory units completed,
five of 120 attempts reserved, `invalid_request`, and the observed model
`gemini/gemini-3.5-flash-lite`. Some later executions reported `unavailable`
without a provider call. Existing generic logs cannot identify the exact rejected
field or retrospectively prove the cause of that HTTP400. A key failure must not
be inferred from a request-format failure.

This hotfix provides provider-specific transport projection, correlated safe
diagnostics and explicit recovery. Mocked HTTP acceptance is **not** evidence of
real model acceptance or semantic completeness. No live provider test is part of
CI, no production test writes are authorized, and the extracted document is not
reuploaded or replaced.

## Contracts and routing

`ai/schemas.py` projects canonical schemas into explicitly catalogued Gemini
and Groq transport profiles. It removes annotations and scalar constraints that
are unsupported/ignored in transport, converts scalar `const` to `enum`, emits
pure `$ref` nodes and rejects unsupported structural features, recursion and
oversized schemas before reserving a provider attempt. Literal property names
remain intact. References and required structural constraints remain bounded.
The original JSON Schema and Pydantic output type still validate the response;
document citations, complete primary coverage and association checks still run
before checkpoint consolidation. Projection never authorizes storing invented
roles, unsupported facts or incomplete results.

Official references: [Gemini generateContent REST](https://ai.google.dev/api/generate-content)
documents the `responseJsonSchema` subset and `$ref` sibling restriction;
[structured output](https://ai.google.dev/gemini-api/docs/structured-output)
describes supported constraints and local validation;
[Gemini 3.5 Flash Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
lists structured output/document capabilities;
[Groq structured outputs](https://console.groq.com/docs/structured-outputs)
distinguishes supported models and best-effort output. Gemini `store:false`
remains in the request. Groq best-effort `strict:false` does not weaken local
validation. Model routing remains the existing configurable catalogue; projection
does not prove that a deployed model accepts every possible schema.

HTTP400 is permanent for that payload. A bounded, five-minute rejection cache
prevents replay for the same account, credential fingerprint, model, task,
transport version, wire schema and request fingerprint. Only hashes/metadata
are retained; cached exceptions do not retain private tracebacks. Payload/schema failures stop without silently
switching providers. Only an explicitly classified model-capability rejection
can skip that model and try another catalogued compatible profile. Transient,
quota and cooldown behavior stays distinct. A cooldown-only execution records
that no provider request occurred and does not consume a provider attempt or a
retry failure. A one-call pilot forbids a second provider attempt, including
fallback; its original HTTP failure remains available for diagnosis.

Each attempted call logs only provider/model, task, allowed stage, UUID unit,
diagnostic reference, HTTP status, allowlisted incompatibility, elapsed time,
fallback and reported token counts. The unit stores that correlation and safe
category. Provider bodies, prompts, PDF text and credentials are not logged.
An absent HTTP status remains absent, never an invented 400 or successful call.

## Budget and existing analyses

The owned read-only execution plan counts unfinished active units and known
future inventory/content comparisons. It includes attempts already reserved.
It labels unknown role-association/content work and excludes unobserved retries
and monetary cost. At 67 pending inventory units and five reserved attempts, the
known lower bound is **139 total attempts**, before deeper work or retries.
The default 120 is not automatically increased; the maximum remains 200.
Full execution pauses whenever its known remaining work exceeds the authorized
budget, including work created by splits or later stage advancement.

New intake packs at most 60 primary blocks, 10,000 text characters and 16,000
compact JSON characters per inventory unit. Existing bounded context rules and
the 24,000-character prompt-data fence remain. An offline Linux measurement of
the owner's extracted 70-page document preserved all 2,772 primary IDs in exact
order: 67 old inventory batches became 47 new batches, maximum prompt 19,464
characters including instructions. Text, table metadata and documentary IDs
are preserved; the complete IR is unchanged. This measurement is neither an AI
test nor permission to regroup the already saved 67 units.

Legacy/new analyses require explicit pilot authorization for this transport
version. Resume uses existing account locks, revision and idempotency receipts.
Completed results, unit keys, IR, historical attempts/provider calls and audit
remain intact. The SQL attempts counter retains its historical three-attempt
bound; explicitly authorized recoveries add a monotonic `claims_total` audit
counter and reset only the current retry-failure window. Twelve provider calls
per unit and the analysis budget remain hard limits. Approval uses optional
manifest JSON fields, so **no migration** is required.

## Manual pilot — owner authorization required after publication

1. Confirm exact reviewed deployment and read-only health checks. Do not click
   resume, upload again or call production POSTs as a deployment smoke test.
2. Obtain the owner's explicit authorization for **one real provider attempt**
   on one small pending unit in the existing owned analysis. Check the current
   route/model, provider availability, saved budget and diagnostic reference.
   Never share keys in chat or logs.
3. In the saved analysis, inspect the forecast and choose **Executar lote piloto
   (1 chamada)**. The confirmation discloses any explicit budget extension.
   A running lease or cooldown blocks competing/repeated authorization.
4. Require an actual successful model response, canonical JSON/Pydantic
   validation, documentary validation and atomic consolidation of that unit.
   Record only safe provider/model/ref/status/usage and checkpoint identifiers.
   Verify the unit is completed, progress is partial, attempts increased only
   once and execution automatically paused. HTTP200 alone is insufficient.
5. On rejection, quota, timeout, malformed/evidence-invalid output or lease loss,
   preserve saved checkpoints and stop. Inspect correlated safe diagnostics;
   do not repeatedly retry an incompatible request. A failed pilot cannot grant
   full-run permission.
6. Present the pilot evidence and updated lower bound. **Await separate owner
   authorization before resuming the remaining batches or extending their
   budget.** The full-run UI confirms the total limit, past attempts and unknown
   future work. A validated pilot is not a completed inventory/program and does
   not bypass human review/import gates or award XP.

The workspace shows completed/pending counts, sanitized causes and references,
explicit waiting/cooldown/pilot states and recovery controls. Paused jobs do not
keep the UI polling as if semantic processing were active. Existing analyses,
source-page browsing and histories remain accessible.
