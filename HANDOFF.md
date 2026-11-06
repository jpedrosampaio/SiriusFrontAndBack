# Sirius — current handoff

## Current work — 2026-11-06, not published

Main verified at `0fc1a43c6530110e1912139a452ec86771dad6e2` (PR82).
Authorized priority: repair workout generation and simplify setup while staying
on free services. Branch: `codex/workout-generation-quick-setup`.
The workout route now passes its original BasePlan contract to the existing AI
router. Local Pydantic, equipment, modality, calendar, ownership, idempotency and
XP validations remain mandatory. Quick setup offers explicit gym/home/running
presets; customization, exclusions and pre-submit summary remain available.
No migration, new service, real AI call or production test write.

Next: finish all four CI workflows and independent final-SHA Codex review.
Do not claim workout generation is fixed in production until deployment and an
authorized real result have been confirmed. Mock transport tests prove the
contract wiring, not provider acceptance or the exact past production failure.

## Deployment blocker and edital continuity

PR82 passed its four workflows/review and merged; Vercel published the merge.
Northflank was still running PR81 `d1d3d74acb0876b10d5547dda0e27f2bf1a3613d`
on November 4. Its manual build rejected the expired default payment method.
On November 6 the dashboard still shows Free and an expired card. No card,
plan, payment, credential or integration was changed by this work.
Owner must resolve account eligibility directly; never request card data in chat.
[Verified blocker receipt](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/82#issuecomment-6633631569).

Issue65 remains open. Last verified saved analysis:25/200 attempts reserved,
1/70 discovery and1/1 verification completed,69 discovery pending; only a role
family was established. Approved200 supersedes historical120 budget. Preserve
PDF text, checkpoints and history; no new upload or automatic budget extension.
PR82 classifies Groq json_validate_failed for existing bounded recovery; its
backend deployment and real validated discovery remain unconfirmed.
The Lovable reference has a saved TRT22 result with11 roles and verticalized
subjects; its model/full extraction implementation was not established. Do not
copy unverified weights, claim complete coverage or infer provider compatibility.

No new master-plan phase authorized. Preserve existing modules. OCR,
rectifications and other maintenance remain backlog; do not bypass the prior
cache-deletion rejection. Northflank's public security incident warning was
reported to the owner; credential rotation is separate and must preserve the
ability to decrypt stored AI keys.

## History

[Previous handoff, unchanged](history/HANDOFF_BEFORE_WORKOUT_QUICK_SETUP.md).
[Earlier output-recovery history](history/HANDOFF_BEFORE_EDITAL_OUTPUT_RECOVERY.md).
