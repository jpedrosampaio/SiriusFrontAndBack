# Sirius — current handoff

## Current correction — 2026-11-04, backend deployment unconfirmed

PR82 merged as `0fc1a43c6530110e1912139a452ec86771dad6e2`, reviewed head
`7e30dd3ccbb171016a2fe20ed75e382630015758`, identical trees. Four workflows
passed on head and merge; independent read-only Codex CLI review clean.
Vercel Production7515982242 succeeded. Northflank has no matching deployment
record; its dashboard session expired and browser account selection timed out.
Owner was asked to finish login in the open tab. Health live/ready and frontend
passed read-only checks, plus20 anonymous protected reads401; this does not prove
the running backend SHA. No post-merge real AI attempt has been initiated.
[Merge, review, CI and deployment checkpoint](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/82#issuecomment-6630371017).
Owner approved200 total attempts and started the queue; the budget decision below
is historical and superseded. Read-only production observation:25/200 reserved,
1/70 discovery complete,1/1 verification complete,69 discovery pending. Queue
paused after Groq GPT-OSS120B HTTP400 `json_validate_failed`, reference
`79a46233-61dd-4acf-a820-f6fb031ca77a`. Only the role-family heading is established.

Merged branch `codex/edital65-output-recovery` distinguishes this exact public Groq code
from an invalid request for structured edital extraction/audit. Existing bounded
lossless unit splitting handles rejected output; no hidden provider fallback,
payload rejection cache, schema weakening, output repair or budget extension.
Single-block failures retain existing recovery stops. Other tasks are unchanged.
This proves error classification, not why Groq generated invalid output or full
real-document success. No new real call, migration or production mutation during
this correction. Preserve transport/9 and the saved pilot/checkpoints/history.

Local validation passed:71 PostgreSQL tests in a fresh disposable database,
304 regressions (4 Windows skips),5 security tests. The earlier reused-database
run stalled and was interrupted; it is not approval evidence.
Next: verify/deploy this exact merge in Northflank, then controlled recovery of
the existing analysis within the approved200 ceiling. Do not repeat a pilot
while the backend release is unknown. Current documentation checkpoint branch:
`codex/edital82-deployment-checkpoint`.
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
