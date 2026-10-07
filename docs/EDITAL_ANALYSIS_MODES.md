# Edital analysis modes

Both `POST /api/study/programs/analyze-edital` and the EditalJobs worker call
`process_edital_analysis`. There is no second parser, prompt or persistence path.

## Mode selection and requests

The import dialog reads `GET /api/study/edital-jobs`. Its session-scoped React Query
cache is shared with the job list and stays fresh for 60 seconds.

* `upload_available: true`: POST `/api/study/edital-jobs` (202), close the dialog,
  show the job list. The durable PDF is deleted on completion/failure. The user can
  leave the screen. Completed jobs open the owner-checked analysis endpoint.
* `upload_available: false`: POST `/api/study/programs/analyze-edital`. The PDF is
  read in memory; only the existing hash, filename, extracted text, evidence and
  structured analysis persist. Keep the screen open until the response arrives.
* A background POST may fall back **once**, only for
  `detail.code == durable_storage_unavailable`. This code is emitted when
  `storage.put` fails, before the SQL transaction can create a job. Other 503s do
  not fall back. No new storage provider or filesystem fallback is enabled.

Both modes then show the same cargo workspace. The user selects a cargo, checks
the evidence, sets an optional date/hours/days and explicitly creates a program
using `/api/study/programs/import-edital-with-cargo`. Missing disciplines or
`conferencia.missing` block creation. The first dialog does not collect unused
planning fields. Direct success supplies the workspace without a redundant GET.

## Waiting, errors and retry

Direct HTTP timeout is 900 seconds, matching the existing worker's processing
ceiling. Upstream proxies may close a connection earlier. The UI shows actual
upload completion, an indeterminate analysis spinner and elapsed time, without
estimated completion percentages or invented extraction phases.

The selected File and force option survive errors while the screen remains alive.
A synchronous ref blocks repeated submissions before React renders. Modal close
and Escape ask before interrupting the wait. Native beforeunload protection exists
only during active direct analysis; anchor navigation also asks. Browser/platform
restrictions can prevent unload dialogs, and programmatic navigation/history is
not universally interceptable with the current BrowserRouter. Aborting the browser
request **does not guarantee remote cancellation**. Retrying after persistence
uses the existing owner-scoped SHA-256/version cache. Explicit force bypasses it;
retrying before the previous request finishes may still spend another AI call.

Backend validation checks extension, 20 MB and PDF magic bytes before provider
calls. Unreadable/textless PDFs fail explicitly. Provider quota/invalid-key errors,
timeout, network and incomplete responses have separate user messages. Unexpected
analysis failures expose no stack trace; logs omit provider response excerpts.

## Polling

Previously the jobs list polled indefinitely. It now polls only queued/running
jobs: 5 seconds in a visible tab, 15 seconds hidden. Empty/terminal lists stop.
Job creation invalidates the shared cache and triggers refresh; manual refresh
and returning to a visible stale tab also resume fetching. No global poller or
additional Dashboard read was introduced. Capability failures can be retried.

## Verification and rollout

No migration: existing EditalAnalysis/EditalJob models remain unchanged. Gemini
is mocked in regression and PostgreSQL suites. Browser fixtures exercise direct,
background, structured fallback, unrelated 503, network retry, double submit,
cached results, incomplete cargos and program configuration at 1440/1024/768/
390/320 px. Production checks are read-only; a real PDF upload is a user manual
test after deployment. Authenticated capability needs an existing user session.
