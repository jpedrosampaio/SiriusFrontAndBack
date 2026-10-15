# Post-launch maintenance contracts

Workouts, recoverable edital errors and Meu dia / Analises were authorized as maintenance of the completed fourteen-phase Sirius plan. This does not create Phase 15 or authorize another phase. Release evidence and acceptance limits are in [POSTLAUNCH_PUBLICATION](history/POSTLAUNCH_PUBLICATION.md). The [implementation snapshot](history/POSTLAUNCH_IMPLEMENTATION_LOG.md) preserves the full earlier audit/review log; its pending states are historical, not current instructions.

## Workout generation, revision and editing

- Form and backend share the requested duration/frequency: a single session or 1/4/8/12 weeks, with 2-7 sessions per week. Four weeks at three sessions produces 12 sessions; at five it produces 20. Labels and selected weeks remain one-based and stable.
- Declare modality, location, real apparatus, level, goal, focus, available time and exclusions. Unknown apparatus differs from declared none; a location does not grant equipment. A gym preset is explicit. Hidden options from another modality are omitted.
- Generate at most three complete typed base sessions per provider call, with bounded batches and one corrective retry. Validate required apparatus, recognizable equipment in names, exclusions, focus/split coverage, level, estimated duration/rest lower bound, conditioning activity and running terrain before writing anything. Invalid/incomplete responses save no plan or XP.
- Calisthenics requires actual bodyweight work. Mobility remains preparation. Conditioning has a circuit method; skills have an identifiable technical practice and conservative novice boundaries. Combined and alternating conditioning preserve the selected activity and correct strength rotation, including odd-frequency weeks.
- Compose the exact calendar deterministically. Repeated bases have an explained proposal purpose; phases and relative training/recovery offsets are proposals, not recorded performance or fixed Calendar commitments. Loads/intensities stay unassigned and never increase automatically. Today and Life State use the same schedule helper; legacy rotation remains supported.
- Evolving a new plan reuses the validated engine and its declared constraints. The revision context includes all current saved prescriptions and separate real history, deduplicating repeated templates; excessive context is explicitly rejected instead of silently clipping later edits. Preserve the original plan. Legacy plans retain the tested legacy revision path.
- Editing selects a session, changes only that session, preserves other weeks/duration and accepts repetition ranges. PATCH distinguishes omitted duration from explicit changes. Existing explicit-duration receipt fingerprints remain compatible; old omitted-duration keys can safely conflict rather than replay changed semantics. No historical receipt is rewritten.
- An uncertain generation retry retains its body/idempotency key without duplicating a plan or XP. A typed pre-write rejection permits editing. Private optional fields remain in memory during recovery and are cleared at account change; they do not silently alter account health preferences.
- Completion never invents calorie expenditure from duration. Missing values remain unknown and explicit zero remains zero. Preserve old calorie entries with unverified provenance, since they may contain former automatic estimates. Dashboard, weekly and workout totals/averages require complete coverage; registered values are not labeled measured or attributed to the user retroactively.

Existing Workout Session UX 2.0, tutorials, recorded history, transaction/ownership boundaries, the Training Engine and sole Global Planner remain authoritative. No schema change is required. This is a conservative structural proposal validator, not a medical assessment, exhaustive exercise ontology or guarantee of physiological outcomes; provider tags and execution-time estimates still need user review.

## Edital diagnosis and recovery

Canonical typed failures distinguish credentials/permission, quota/rate limit, model, request format, network/timeout, empty/blocked/truncated/malformed output and provider unavailability. Public errors use allowlisted messages and diagnostic references, never provider bodies or private document content. Cooldowns retain their owned provider/model cause. Direct and queued analysis share the same pipeline.

Strict JSON plus the existing output schema reject incomplete/truncated extraction rather than repairing a prefix into a completed analysis. Existing source verification, quality and import restrictions remain; schema validity alone does not prove extraction accuracy.

Active duplicate uploads coalesce under the existing owner/hash/mode contract. Explicit completed force-reanalysis retains its cache-bypass/new-analysis behavior. Content-addressed inputs can be shared between force modes: upload/reference attachment and terminal cleanup take the same owner lock, and deletion waits for the last active reference. History and cross-user isolation remain intact.

The original production Gemini account/model failure and a successful analysis of the real PDF remain unverified. Mocks and the [official model catalogue](https://ai.google.dev/gemini-api/docs/models) do not establish account access, quota or real-document accuracy. No real AI API is called in tests.

## Home and analytical dashboard

Top-level Meu dia / Analises tabs reuse Command Center, existing aggregate services and charts. Closed panes unmount and do not refetch; graphs load on demand with cancellation, safe error/retry and accurate labels when an older confirmed window remains visible. Controls and cards adapt across 320/390/768/1024/1440 px; title/actions do not overlap on tablets.

Money stays Decimal through the API and exact display/tooltips. Recorded net flow is not bank balance. Missing goals, exam attempts/accuracy, confirmed nutrition targets and calorie coverage stay unknown rather than zero; recorded zeros remain zero. Scores use the canonical grader. Session fences reject earlier-account responses. Assistant focus returns only to an effectively visible launcher, while an open dialog retains focus ownership.

## Validation and continuity

Keep all four workflows and all nineteen browser suites, including the original eighteen and every existing assertion, at the five required widths. Use disposable PostgreSQL, mocked providers, security/regressions, frontend lint/unit/build and final-head Codex review. Merge only the reviewed SHA; verify exact Vercel/Northflank deployments and production through reads. Production validation does not create private workouts, uploads or other test records.

Follow [AGENTS](../AGENTS.md), the [context map](DEVELOPMENT_CONTEXT.md), current [HANDOFF](../HANDOFF.md) and [protected migrations](PRODUCTION_MIGRATIONS.md). Historical logs are references, not automatic imports or renewed authorization.
