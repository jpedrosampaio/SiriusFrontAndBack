# Sirius — current handoff

## Current correction — 2026-11-03, not yet published

Main verified at `d1d3d74acb0876b10d5547dda0e27f2bf1a3613d` (PR81).
Owner approved200 total attempts and started the queue; the budget decision below
is historical and superseded. Read-only production observation:25/200 reserved,
1/70 discovery complete,1/1 verification complete,69 discovery pending. Queue
paused after Groq GPT-OSS120B HTTP400 `json_validate_failed`, reference
`79a46233-61dd-4acf-a820-f6fb031ca77a`. Only the role-family heading is established.

Branch `codex/edital65-output-recovery` distinguishes this exact public Groq code
from an invalid request for structured edital extraction/audit. Existing bounded
lossless unit splitting handles rejected output; no hidden provider fallback,
payload rejection cache, schema weakening, output repair or budget extension.
Single-block failures retain existing recovery stops. Other tasks are unchanged.
This proves error classification, not why Groq generated invalid output or full
real-document success. No new real call, migration or production mutation during
this correction. Preserve transport/9 and the saved pilot/checkpoints/history.

Next: complete PostgreSQL/regression/security tests, four full workflows and
independent final-SHA Codex review before merge; validate exact deploys and health.
Then controlled recovery of the existing analysis within the approved200 ceiling.
Do not claim Issue65 resolved until actual validated/consolidated discovery succeeds.
Pre-correction handoff is preserved in
[history](docs/history/HANDOFF_BEFORE_EDITAL_OUTPUT_RECOVERY.md).


## Published baseline and continuity

PR80 functional merge: 348e5b35b0bbfb8c5851de0c6b49c575d18bfc91. PR81
documentation merge: d1d3d74acb0876b10d5547dda0e27f2bf1a3613d. Their exact
deploy/CI/review receipts remain linked in the archived handoff. No new phase
is authorized. Preserve all modules and previously published PDF extraction,
notifications and deletion. OCR, rectifications, workout generation and cleanup
remain backlog. Never bypass the prior automatic cache-deletion rejection.
