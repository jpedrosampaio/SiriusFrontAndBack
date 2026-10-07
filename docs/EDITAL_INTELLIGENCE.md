# Edital Intelligence & Radar

## Audit and implementation boundary

Main cfaa4bf: ContestSource already owns opt-in URLs, trust classification, snapshots, ETag/Last-Modified, six-hour source leases and host cooldown. ContestUpdate records discovered document links and limited textual differences, not a durable complete version history. The watcher already rejects private networks, redirects, robots restrictions and access challenges. Reuse these contracts rather than creating another source registry/worker.

Phase 3 adds declared source kinds and immutable bounded text versions, linked to the existing updates. Original PDF/HTML bytes are not retained. Versions preserve exact extracted text (up to the existing 200,000-character provider bound), provider hashes, HTTP metadata, predecessor, timestamps and owner. Reverted content is a new observation; hash equality suppresses repeated identical observations, not distinct A→B→A transitions. Leases keep ingestion atomic and revoke removed sources.

Impact is deterministic textual evidence plus clearly labeled heuristic categories for roles, disciplines, topics, dates, weights, questions, rules and calendar. No legal conclusion or invented duration. Syllabus and plan impacts are proposals; nothing is silently rewritten. No LLM call is necessary for the radar, and unchanged content does not call one.

Official deadlines require a trusted registered source, a full valid date with an explicit year, a recognized nearby event label, and a literal source excerpt bound to version/hash/URL. Ambiguous dates remain unclassified. Publication time is never guessed from detection time or HTTP headers. Timeline is informational; automation/reminder rules belong to phase 12 and must retain this provenance.

## Migration gate

The new version history cannot be reconstructed from the existing partial diffs. Use an additive source-kind column and version table; backfill only the latest existing source snapshot/hash, marked legacy, without inventing older versions. Keep all existing source/update rows and existing IDs. Current parent is 84d2a71ef309. Implement/test/review the PR, then stop before merge for the owner to apply the revision on Neon through DATABASE_URL_DIRECT.

Readiness currently requires the exact Alembic head. The old main can report ready=503 after the owner advances the database until the new code is merged/deployed; coordinate the application/merge transition. No startup DDL or automatic production migration is introduced.

Tec/QConcursos and similar protected services are not radar providers. Only authorized APIs or permitted user imports may supply future questions. Existing source URL/body limits and host policies remain bounded; no new infrastructure, storage service or billing is added.

## Available contracts and limits

- GET `/study/v2/programs/{id}/radar`: latest observation for each active source, textual impact proposals and official date candidates with version/hash/URL/quote. Conflicting candidates are disclosed rather than resolved. This is not a final legal calendar.
- GET `/study/v2/programs/{id}/sources/{source_id}/versions?limit=20&offset=0`: owner-scoped history, maximum 50 observations per page; no full snapshot in list responses.
- GET `/study/v2/programs/{id}/sources/{source_id}/versions/{version_id}`: owner-scoped extracted text detail, maximum 200,000 characters. Never exposes original binary storage that does not exist.
- Source creation accepts `source_kind` (default unknown for existing clients); classification never upgrades domain trust. Strict opt-in, maximum five active sources, existing leases/cooldowns/backoff/robots/SSRF guards remain.
- Numeric dd/mm/yyyy or dd.mm.yyyy and complete Portuguese written dates are extracted only on a line with one recognized event category. Yearless, invalid or ambiguous dates are omitted. Legacy snapshots are preserved without pretending their dates were analyzed. PDF images require readable extracted text; no OCR service is introduced.
- Comparisons retain 1,500 lines and 60 added/removed lines per side, with explicit partial flags. Categories/confidence are heuristic proposals; no confirmed topic delta, invented coverage time, silent recalculation or automatic notification is produced.
- HTML version hashes include extracted text and normalized document links, so replacing a PDF link with the same displayed title is observable. Link changes are separately displayed, without pretending the linked PDF content was fetched. Link metadata is not repeated in history list responses.
- Impacts compare the preceding immutable text observation and retain its partial flag, including after stopping/reactivating a source. They do not compare against a cleared mutable snapshot.
- Legacy backfill timestamps use the existing latest-attempt/record timestamp for ordering, with an explicit UI label that the observation date is unconfirmed. They are never presented as publication dates. PDF text separators count toward truncation and both document and version partial flags agree.
- Date scanning covers the entire retained 200,000-character snapshot, with at most 100 candidates per source and explicit date-analysis partial/limit metadata and UI notice. Link deltas use stable URLs; a PDF byte revision at the same URL is not falsely described as link removal/addition.
- Preparation source freshness uses the distinct last successful check of active official sources, retained across later failed attempts, and is displayed in the preparation view. It is not a presumed publication time. The additive migration backfills this timestamp only where the legacy latest attempt was successful; unknown prior successes are not invented.

MIGRATION REQUIRED: revision `6f12b8e4a903`, down_revision `84d2a71ef309`; command `python -m alembic upgrade head`, working directory `backend`, database Neon via `DATABASE_URL_DIRECT`. No production migration has been run by the agent.

Local verification includes the existing PostgreSQL suite, owner/foreign-owner pagination, unchanged hash and A→B→A, direct PDF changes preserving exam type, sourced dates, pure parser regressions, a separate loopback migration upgrade/downgrade/re-upgrade with legacy backfill, and browser history/date views at 1440/1024/768/390/320px. CI/review status is tracked in HANDOFF.
