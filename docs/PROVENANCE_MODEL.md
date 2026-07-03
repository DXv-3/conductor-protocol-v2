# Provenance Model

## Generation lineage

A provenance trace records: request_id, session_id, source_videos, files_read, commands_run, scripts_invoked, reference_docs_used, artifact_paths_checked, generated_outputs, timestamps, operator_notes.

## Evidence classes

- `runtime_observed` / `runtime_proven`: witnessed execution output from real code paths.
- `artifact_compiler_observed`: seen in bundle compiler inputs or reference docs.
- `reference_only`: present only in markdown/reference source.
- `asserted_unverified`: stated in output but unsupported by compiler or runtime evidence.
- `contradicted`: claim conflicts with code audit or runtime test result.

## Required invariants

- Every emitted bundle has exactly one provenance trace.
- Every major claim has exactly one claim record with one current status.
- Promotion fails if any required claim is `asserted_unverified`, `contradicted`, `reference_only`, or `unverified`.
