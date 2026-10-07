# File upload audit — Studies / Edital Reliability 2.1

Audit of main and the existing upload implementations. Classification describes
the original binary's lifetime, not whether structured results persist in SQL.

| Resource | Classification | Implementation / result |
|---|---|---|
| Edital analysis | D → A (direct); background requires durable storage | `server.process_edital_analysis`, `edital_jobs.py`: capability selects direct memory analysis; optional queue preserved. Same pipeline and hash cache. |
| Mind maps / essay correction | A | `services/study_material_routes.py`: bounded request bytes; a temporary file is deleted in finally after the existing Gemini upload. Generated nodes/correction persist, not the original PDF. Provider credentials are required. |
| Study PDF → notes/cards/quiz | A | `services/study_pdf_materials.py`: shared transient provider upload; generated materials saved together in an activity transaction. No dependency on application object storage. |
| Imported exam PDF | A | `services/exam_generation_routes.py`: temporary provider input, generated exam persisted. No local durable binary fallback. |
| Workout sheet import | A | `services/workout_generation_routes.py`: shared transient `upload_part`, structured plan/activity persisted. Workout UX 2.0 unchanged. |
| Nutrition / body measurement PDFs | A | `services/nutrition_generation_routes.py`, `health_ai_routes.py`: transient provider input, structured results. No new upload path added. |
| Agent attachments / Study library sources | A | `ai/routes.py`, `services/retrieval.py`: PDF extraction in memory; hash/filename/text pages indexed in owner-scoped SQL. Images are sent to the existing configured provider for transcription, then only text persists. This audit adds no third-party upload. |
| Original attachment on an existing study note | C | `studies_catalog_routes.note_upload`: owner verified, explicit 503 saying attachment storage is not configured and the note remains available. No visible frontend call to this endpoint; not a user-facing dead end. Keep limitation until original-file retention is designed. |
| Old combined study chat + file | C (retired compatibility endpoint) | `/study/ai-chat-with-file` returns 410 directing clients to `/ai/attachments` and `/ai/chat`; current UI uses the latter. |

No B fallback was needed, and no additional visible D resource was found. Other
routes may require Gemini/Groq keys or the existing RAG feature flag; those are
explicit service prerequisites, not an object-storage dependency. Provider uploads
already present in the application remain transient inputs and are not a promise
of downloadable original files. Temporary files are never used as persistence.

This is a source audit supported by existing mocked-provider upload/SQL tests;
it is not a live upload test against production providers. Original-file downloads
and durable note attachments remain future work. No paid service, volume, bucket,
binary SQL column, Base64 persistence or migration was introduced.
