# ADR-0001: Data handling around the LLM extraction pipeline

## Status

Accepted (documents existing behavior as of 2026-09; not a proposal)

## Context

Vault sends bank/card statement text to Anthropic's Claude API for extraction
(`worker/processing.py`). Because this is financial and potentially
personally-identifiable data, we need a clear, written record of exactly
what leaves our infrastructure, what gets masked first, and what happens to
the source files afterward — both for our own engineering clarity and in
case this is ever asked about for compliance purposes (Ley 25.326).

This ADR documents current behavior. It does not introduce new behavior.

## What gets redacted before text reaches Claude

`worker/processors/redaction.py::redact_sensitive_numbers` runs on extracted
statement text before it is sent to the LLM. It masks, keeping only the last
4 digits:

- Card numbers in `dddd-dddd-dddd-dddd` / `dddd dddd dddd dddd` form.
- Any other run of 10+ consecutive digits with no separators (this is the
  catch-all that covers CBU/CVU numbers, which are 22 digits).

Dates and monetary amounts are intentionally **not** masked — they don't
match either pattern, and they're required for the extraction and
verification logic to work.

**Not currently redacted:** account holder name, DNI/CUIT if present in the
statement header, and merchant/transaction description free text. These
remain in the text sent to Claude as of this writing.

## What happens to the source file in S3

- On a successful run, the original uploaded file is deleted from S3 after
  processing completes (`worker/processing.py:295`, `s3.delete_object`).
  This is best-effort: a failed delete is caught and only printed to stdout
  (`worker/processing.py:296-297`) — it is not retried, and does not fail
  the job.
- On a processing **error**, there is no explicit cleanup path in
  `processing.py` — the source file is left in S3 indefinitely.
- Users can explicitly delete their own uploads and exports
  (`app/routers/uploads.py`, `app/routers/users.py`), which also call
  `s3.delete_object` / `s3.delete_prefix`.
- There is no bucket-level lifecycle policy today acting as a backstop for
  either of the gaps above.

## Open questions / not yet decided

- Should account holder name / DNI / CUIT also be redacted before reaching
  the LLM, or is this an accepted risk given the data is needed for
  matching accounts to statements?
- Should failed-processing uploads have a TTL/cleanup path instead of
  living in S3 forever?
- Should S3 have a lifecycle policy as a defense-in-depth backstop
  regardless of what the application code does?

These are flagged here rather than resolved, so they're visible instead of
implicit in the code.
