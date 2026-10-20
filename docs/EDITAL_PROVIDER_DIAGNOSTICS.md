# Edital: structured transport, recovery and controlled homologation

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
