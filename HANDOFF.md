# Sirius — current handoff

## Active correction — 2026-11-11 (not published)

Owner authorized resolving pending issues. The real requested workout on Nov9
(hypertrophy/gym/4 weeks/3 sessions/45 minutes) failed before persistence:
Gemini3.8 Flash HTTP400 INVALID_ARGUMENT, reference
`c91228c2-19aa-4e81-b296-1203fe713c65`, public reference `a462a9923f08`.
No Groq fallback occurred; specific rejection cause remains unknown. Current
official generateContent docs still support responseFormat.text.schema and store;
do not claim the field name caused this failure or that mocks prove acceptance.

Branch `codex/workout-provider-recovery`: prefer existing free Groq120B/20B route,
opt into strict structured workout output, keep original validation and bounded
caller recovery for Groq json_validate_failed. Preserve Gemini-only/multimodal
routes. Honor explicit weekly_frequency alias for strength too; UI errors show
only a validated public reference. No migration or paid service.
Gates and real generation remain pending. PR84 publication documentation is
incorporated here with its exact historical snapshot; close it as superseded
only after this correction merges. Do not declare workout or Issue65 solved.

## Published correction — 2026-11-06

PR83 merged at `ff1e29e1127dd4f2248e2dc7f16e536a881bfba2` after four green
workflows and clean independent Codex review of head
`34d2b8da625a68bc581d440ad1dee7d664dda7cd`; merge/head trees match.
[Review and validation receipts](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/83#issuecomment-6683745299).

Workout generation now sends the original BasePlan schema through the existing
AI router, preserving Pydantic/semantic/equipment/calendar checks before save or
XP. Gym/home/running quick presets preserve personal constraints and routine;
customization, exclusions, summary and closing/recovery remain available.
No migration or paid infrastructure. No real AI calls or production test writes.
All local browser suites passed at320/390/768/1024/1440. Local PostgreSQL first
run had488/489 passes: startup safety rejected a database name without `test`.
The unchanged startup test then passed against a correctly named disposable DB;
the entire PostgreSQL workflow passed on GitHub. No validation was weakened.

## Deployment evidence

Owner resolved expired payment method. Northflank accepted the automatic build
`expert-jewel-6660`, succeeded and deployed exact merge `ff1e29e` (Running1/1,
Free0.2vCPU/512MB). GitHub deployment7605447146 reports success. This also brings
PR82's previously blocked backend correction into production.
[Northflank build](https://app.northflank.com/t/jpedrosampaios-team/project/sirius/services/siriusfrontandback/builds/expert-jewel-6660).
[Vercel successful deployment](https://vercel.com/jpedrosampaios-projects/sirius-frontend/8hYCKXWHKc1D4vba11srsuNa47ka).
Read-only production verification:live/ready200, frontend200, current quick-setup
asset present, PWA/contracts intact and20 protected anonymous reads401.
A live check returned503 during rollout; the full recheck passed after startup.
No plan/payment/credential changes were made by the agent.

## Next authorized work and limitations

Retry the already authorized real workout after the correction deploys, and
confirm it with the configured free provider before
claiming end-to-end generation reliability. Mock schema acceptance is not proof
of real provider acceptance or the exact cause of the past production failure.
Do not create synthetic production records. Preserve workout history/tutorials.

Issue65 remains open. Last verified saved edital:25/200 attempts reserved,
1/70 discovery and1/1 verification complete,69 discovery pending; only a role
family established. Approved200 supersedes historical120. Preserve PDF text,
checkpoints/history; no upload or automatic budget extension. PR82's bounded
Groq output recovery is now deployed, but actual validated discovery remains
unconfirmed. Consult saved state before any controlled continuation.
Lovable reference: saved TRT22 result showed11 roles and verticalized subjects;
its model and full extraction implementation were not established.

No new master-plan phase authorized. OCR/rectifications and other maintenance
remain backlog. Preserve all modules; never bypass the prior cache-deletion
rejection. Northflank's public incident warning was reported to the owner;
credential rotation is separate and must preserve decryption of stored AI keys.

## History

[Pre-publication snapshot](docs/history/HANDOFF_BEFORE_WORKOUT83_PUBLICATION.md).
[Pre-workout snapshot](docs/history/HANDOFF_BEFORE_WORKOUT_QUICK_SETUP.md).
[Earlier output-recovery history](docs/history/HANDOFF_BEFORE_EDITAL_OUTPUT_RECOVERY.md).
