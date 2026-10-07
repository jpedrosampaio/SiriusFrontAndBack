# Preparation Core 3.0

## Audit and boundaries

Preparation is the existing StudyProgram + optional StudyTarget. Generic programs remain valid. Notebook and StudyTopic represent disciplines/topics/subtopics, preserving UUID, parent_id and topic_key. StudyPlan supplies availability and dated blocks. Sessions, attempts, reviews, flashcard reviews and exam attempts remain authoritative facts. There is no Preparation table, duplicate evidence table, persisted health score or LLM scoring.

The primary preparation is a user preference (`users.preferences.primary_preparation_id`). PUT validates an active owned program, requires an idempotency key, and runs under the existing user lock/receipt transaction. Other preferences are preserved. Archived programs never appear as primary; another program must be explicitly selected. No migration is required; current head is 84d2a71ef309.

## Contract

GET `/api/study/v2/programs/{id}/state` is a read-only deterministic projection. An inaccessible or archived program returns 404. It returns coverage, mastery, performance, debt, reviews, pace, recent trend, candidate model, health components, candidates, syllabus graph, evidence ledger and freshness. IDs and source provenance remain explicit. No external provider or paid service is called.

Coverage is marked contact across active topics/subtopics, each counted once. It is distinct from mastery, which reuses `sirius-mastery-1`: only answered individual questions with a linked Question count; recency-weighted Beta(2,2) estimate, sample confidence and range. Aggregate practice, self-confidence, completed sessions and review activity never invent mastery. Topic evidence IDs trace the estimate to QuestionAttempt facts; the ledger shows recent activity, not a second source of truth.

Archived topics are excluded from current mastery while their recorded attempts remain in aggregate history. Candidate priorities reuse the existing deterministic rule and disclose unverified weights/incidence; they are proposals, not facts about the official exam.

Stages: no responses + unmarked = not_started; marked = exposed. Fewer than 10 responses or score below 60 = practicing. Score below 80 or confidence below high = consolidating. Otherwise mastered, or maintenance when last individual response exceeds 14 days. This describes the versioned operational estimate and never diagnoses memory, intelligence or health.

Health contains separate explanatory components: coverage, mastery, latest topic reviews in date, executed minutes/planned minutes over seven days (capped at 100), aggregate accuracy, and completed/past plan blocks over 28 days. Today's blocks do not count as past consistency obligations. Unknown components remain null. Fewer than three known components = insufficient; any below 50 = attention, otherwise any below 80 = moderate, else stable. This is not probability of passing. Flashcards due are shown separately.

Debt covers unfinished past blocks over 28 days and unstarted topics, without rewriting the plan. Current pace is completed minutes over seven days. Required pace is the recorded seven-day plan load, **not** an invented forecast of hours required to finish the syllabus. No topic duration baseline exists. Availability comes from the existing plan. Preferred study time remains unknown rather than being inferred from missing start timestamps.

## Bounds and limits

Batched owner-scoped SQL avoids per-topic queries. 2,000 books/topics/review schedules/recent sessions/plan entries and 5,000 individual answers are explicit sample limits. Truncation is disclosed. Ledger displays up to 100 recent records per selected source, merged to 100; sessions use the 28-day operational window. Aggregate accuracy uses SQL SUM over active disciplines, excluding explicitly unanswered exam rows. Archived disciplines are excluded from plan metrics. Original files are not retained. Official-source freshness is unknown until the radar phase.

The current overview adds expandable explanations and evidence, with suggestions requiring explicit study actions. Existing plan generation, study sessions, drafts and syllabus marking are preserved. Failed indicator reads can be retried independently. No change is silently applied to any plan.

Exam attempt/individual question IDs and review IDs link topics to practice history. Notes, drafts and flashcards are linked at discipline level; drafts retain topic_key when present. Topic source evidence is preserved. EssayCorrection currently has no preparation reference, so unrelated essays are explicitly excluded instead of assigned to an arbitrary preparation. Official source monitoring belongs to phase 3.

Measured local synthetic SQL test: 17 SELECTs for both 2 and 100 topics without a plan, with 100-topic JSON of about 68.7 KB. A plan adds one bounded upcoming-entry query. One state request replaces the overview request rather than adding a second metrics request. No claim of production timing improvement. Browser test intercepts all API calls; five viewport widths pass primary-selection lost-response retry with identical key, read retry, explanation/evidence expansion, study navigation and horizontal overflow checks.
