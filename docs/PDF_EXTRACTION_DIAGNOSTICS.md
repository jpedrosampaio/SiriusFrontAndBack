# PDF runtime loader correction and bounded diagnostics

## Incident and decision

Production reported HTTP 422 `extraction_resource_limit`, reference `11b758e72ff0`,
on 2026-10-20 at 14:12:53 UTC, after approximately 2.76 seconds. The supplied
70-page textual PDF has SHA-256
`1564d6ccacdb20b5b16ad77fa2ccfc667efb925f83ab4d9b75150ade8745039e` and 763437 bytes.
The owner confirmed Northflank nf-compute-20, one instance, 0.2 shared vCPU and
512 MB total container memory.

The previous supervisor mapped both a nonzero child returncode and stdout over
12 MiB to the same error. That record cannot establish an address-space limit,
container OOM, CPU limit, signal, parser fault or excessive output as the cause.
A later test with the actual buildpack Python family reproduced a concrete
startup fault: the sanitized subprocess environment removed the library search
path required by the relocated interpreter, so the dynamic loader exited with
returncode 127 before Python, `child_limits()` or PDF extraction could run.
The fix supplies only the active interpreter's own library directory, derived
from `sys.base_prefix` and `sys.platlibdir`. It does not inherit arbitrary
`LD_LIBRARY_PATH`, `LD_PRELOAD`, Python paths, CMap paths or credentials.

All operational limits remain unchanged: 384 MiB child **virtual address space**,
55 CPU seconds, 60 seconds wall time, no file output, 20 MiB input, 12 MiB result,
400 pages, two million characters and 20000 blocks. RLIMIT_AS does not reserve
RAM and is not the container's shared resident-memory budget. The extraction
algorithm is unchanged. No batching, automatic retries, dependency changes,
migration or paid upgrade was introduced.

## Buildpack reproduction and correction

The official [Heroku Python buildpack v6.7.0 runtime test](https://github.com/heroku/buildpacks-python/blob/v6.7.0/tests/pip_test.rs)
includes its Python layer's library directory in `LD_LIBRARY_PATH`.
Its [version selection](https://github.com/heroku/buildpacks-python/blob/v6.7.0/src/python_version.rs)
resolves Python 3.11 to 3.11.17. The official Ubuntu 22.04 amd64 runtime archive
used locally has SHA-256
`834f88f4035a699247e230bd18dcd26e305ef28544ba0c320e254991ef4b7a45`.
All application requirements were installed in a separate venv using this
interpreter; the initial standalone Python build described below did not
reproduce its loader requirement.

With the original sanitized environment, even `python --version` failed with
127 and a libpython loader error; the PDF subprocess likewise returned 127,
zero stdout bytes and no Python traceback. Restoring only the interpreter's
own library directory allowed that same interpreter to start.

The original main extraction code and complete service import were then run
together in a cgroup with `memory.max=512000000`, no swap and
`cpu.max="20000 100000"`, using the real PDF. It reproduced
`extraction_resource_limit` in 0.075 seconds of extraction, peak 146509824 bytes
and no OOM events. This is parser timing, not the original HTTP request latency.

The corrected supervisor passed the same runtime, file and budgets:
40.086 seconds of extraction, peak 181018624 bytes (about 173 MiB), no OOM,
70 pages, 229422 characters, 2772 blocks and 62 table rows. The full IR matched
the earlier successful baseline, including every text/cell/geometry/source
reference. The independent per-page character comparison also remained exact.
The private PDF is not committed or sent to any provider.

This establishes the runtime-launch defect and its correction, not retrospective
proof that the historical request had no other contributing condition: its old
log did not record returncode. The actual production image/load/history and
database/background workers were not reproduced completely. New safe diagnostics
and the owner's normal retry remain necessary to confirm the live incident.

## Evidence and limits of reproduction

Initial local Linux: Ubuntu 22.04/WSL2, kernel 6.6.87.2, standalone CPython 3.11.17, all backend
requirements installed. Pinned parser stack: pypdf 6.20.1, pdfplumber 0.11.10,
pdfminer.six 20260107, pydantic 2.12.5, cryptography 49.0.0. Resolved supporting
packages included pypdfium2 5.14.0, Pillow 13.0.0 and NumPy 2.4.6.

The real PDF passed the original child limits before any extraction algorithm
change: 70 pages, 229422 characters, 2772 blocks, 62 table rows and 1171977 bytes
of JSON protocol output. A monitored run observed about 110 MiB peak virtual
address space and 83 MiB peak resident memory; returncode 0, empty stderr.

A separate cgroup v2 initially constrained the loaded backend and its parser together:
`memory.max=512000000`, `memory.swap.max=0`, `cpu.max="20000 100000"`.
This is slightly stricter than 512 MiB. The service imported the complete
`server` module with the same requirements, then used the real asynchronous
extraction path and original child limits. This initial run passed in 37.982 seconds of
extraction; cgroup peak 221196288 bytes, no `max`, `oom` or `oom_kill` events,
and CPU throttling was observed. A repeat with the instrumentation passed
in 40.779 seconds, peak 179097600 bytes and zero OOM events. Its correlated
supervisor log recorded returncode 0, 1171977 stdout bytes, the 512000000-byte
cgroup ceiling and zero OOM-kill delta. These are individual local measurements,
not a performance guarantee. No document splitting was needed.

The entire IR matched the unrestricted-budget baseline, including text, cells,
geometry, ordering and source references. Independent pypdf extraction had zero
missing/extra normalized alphanumeric characters on every page. Character
counts alone do not establish reading order or semantic correctness.

This reproduces the declared CPU/memory budget, **not the exact production
image, current load or memory history**. Network access in the test service was
blocked; database startup/background workers were not run. No production
database was accessed and no provider was called. The original failure did not
reproduce with standalone Python, motivating the subsequent buildpack-runtime
test above. Neither increasing limits nor changing extraction strategy is
justified by these measurements. The source PDF and extracted artifacts remain
private local inputs, outside Git.

## Operational interpretation

`edital_extraction` logs contain supervisor-owned outcome, correlation reference,
duration, returncode, POSIX signal number, captured stdout bytes/completeness,
output-limit flag and configured Linux address-space limit. They never contain
stdout, stderr, filenames, document text, environment values or exception text.
The HTTP error and `edital_ingestion` log reuse that reference.

- `process_failed` / HTTP 503 `extraction_process_failed`: child exited nonzero.
  Negative POSIX returncode identifies the signal; `-9` means SIGKILL, **not
  proof of OOM**. A nonzero exit and excess stdout are both visible if combined.
- `result_limit` / HTTP 422 `extraction_result_limit`: successful process exit
  with stdout above the ceiling. A child-reported result-limit rejection retains
  its existing HTTP 422 code.
- `timeout`: the existing subprocess runner killed/reaped the child. Its
  exception exposes partial stdout, not the final returncode; signal/returncode
  stay unknown and `stdout_complete=False`. Do not infer a natural SIGKILL.
- `launch_failed` and `invalid_result`: distinguish process startup from a
  malformed protocol result without logging OS/parser exception contents.
- `child_rejected`: existing PDF validation failed; the HTTP allowlist supplies
  the safe error code. Untrusted child diagnostics/codes are not log fields.

When available, read-only cgroup v2 counters prefer the process-specific group
over the hierarchy root and add memory before/after, container
maximum, **lifetime** peak and the change in `oom_kill` during the interval.
Missing, inaccessible or unlimited values remain `None`. These are shared
container counters, not per-request RSS or proof of causation. No cgroup setting
is changed by application code. Compare the correlated record with Northflank
resource/runtime events before concluding OOM or proposing a smaller working set.

## Validation and next action

An isolated Linux ELF fixture requires a shared library without an rpath: it
reproduces exit 127 before the fix and starts successfully with the derived
trusted library directory, even when the parent has hostile loader variables.
Regressions also cover nonzero exits versus output overflow, real Linux SIGKILL,
partial timeout output, unavailable counters, namespace paths, sanitization,
unchanged credential exclusion and actual RLIMIT_AS allocation rejection.
A synthetic 70-page Linux document checks every text line, every table cell,
contiguous page coverage and stable source references under existing limits.
PostgreSQL HTTP tests preserve the reference, fail the owned intake and prohibit
partial IR persistence/provider wake-up.

All four existing workflows and exact-head Codex review remain required.
Publication/deploy evidence belongs in the [PR62 conversation](https://github.com/jpedrosampaio/SiriusFrontAndBack/pull/62). After publication,
obtain a correlated diagnostic from the owner's normal retry of this real PDF;
do not perform authenticated test uploads or real Gemini calls from the agent.
Only if new facts establish a separate working-set problem should bounded page
batches with deterministic full-coverage consolidation be investigated before
changing limits.
