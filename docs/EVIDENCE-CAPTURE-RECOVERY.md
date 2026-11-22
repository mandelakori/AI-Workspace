# Milestone E: bounded capture correction and open candidate diagnosis

**Capture verification PASS; preserved candidate remains unaccepted and unrepaired.**
No live model inference, remote access, downloads, new trial preparation or target
source correction occurred. The consumed `de9bdcda...` authorization, quarantine,
historical receipts and original A–E roadmap are unchanged.

## Changed implementation and measured policy

- `aiwork/evidence_capture.py`: reserved, disk-backed payload writes; streaming
  SHA-256; partial-write accounting; bounded incremental usage parsing; explicit
  byte limits and disk headroom. Existing evidence files cannot be overwritten.
- `aiwork/provider_gate.py`: use that storage, number/attribute requests before
  capture admission, archive before forwarding, retain prefix hashes and explicit
  completeness flags on interruption, persist exhaustion in the task ledger and
  classify local capture exhaustion as `resource_exhausted`. Local storage errors
  are `evidence_failure`; genuine upstream failures remain provider failures.
- `tests/test_evidence_capture.py`, `tests/test_capture_harness.py`: 12 deterministic
  capture/replay/resource tests and one installed inert OpenCode conformance test.
- This report, STATUS/NEXT_STEPS and `docs/evidence/evidence-capture-recovery/`:
  receipts, open diagnostic drivers and results. No ItsDangerous source/tests/docs
  were repaired. Diagnostic drivers are operator-authored verification, not
  autonomous implementation corrections.

The failed trial archived **4013320 incoming +4192802 rewritten +8570944 response
bytes =16777066**. Its old counter reached 16777435: a **369-byte chunk** was counted
but rejected before writing at the 16777216-byte cap. Those historical bytes and
limits remain unchanged; the missing chunk is not reconstructed.

The new default is **64 MiB (67108864 bytes)** of provider payload per session,
configurable through `ProviderGate(capture_limit=..., disk_headroom=...)`, with a
hard maximum of 512 MiB. At the observed mean, 64 requests project to **23861241
bytes (22.76 MiB)**; 64 MiB supplies roughly **2.81 times** that projection. This
supports the demonstrated workload, not every combination of maximum context,
request count and output. Heavier traces still stop at an explicit ceiling.

Payload admission leaves **32 MiB default disk headroom** for receipts/cleanup.
The ledger is capped at **16 MiB**, with at most 1024 numbered request records;
payload plus ledger/atomic-ledger temporary files has a **96 MiB** default bound,
excluding separately bounded harness artifacts. After closure, later requests are
counted as unadmitted, not read or forwarded. Catalog summaries are bounded and
flagged when abbreviated; their full original bodies remain in payload evidence.
Metadata exhaustion preserves the last complete ledger plus a closure notice.

Space is reserved **before network reads** and charged only for bytes actually
written. Concurrent reservations cannot oversubscribe the cap. Every response
chunk is archived before relay. On exhaustion, no synthetic finish marker is
inserted: the archived prefix is hashed, `response_complete=false` is explicit,
the resource reason is durable and further inference is blocked. Unexpected disk
write failures record any unarchived suffix's byte count/hash rather than claiming
complete evidence. Physical storage failure cannot guarantee retention of that
suffix. Partial HTTP bodies and cancellation remain failures with retained hashes.

Response reads are at most **64 KiB**, with a **256 KiB** usage-line parser bound;
the entire response is no longer loaded into memory for hashing/parsing. Oversized
usage lines are flagged; their raw bytes remain archived. This is a software
buffer bound, not a measured process-RAM or inference-capacity benchmark.

## Verification

**220/220 tests pass, zero skips, 173.987 seconds.** Baseline: 207/207 in 152.888 s,
direct fixture VERIFIED. Final coverage includes existing permission, rollback,
compaction, cancellation, provider resend and installed OpenCode/Pi boundaries.

The deterministic replay serves the **44 complete historical response streams
twice**, through 88 inert HTTP requests with the real gate/contract rewrite. It
archives **30418686 bytes across 264 files**, verifies every payload size/hash and
finishes without exhaustion or failure. This exceeds the previously observed
16777435-byte counter. It does not complete or alter historical request 45, run
agents, generate tokens or represent 88 engineering trials. Replayed usage events
are historical data, not new model consumption.

An intentional **4096-byte** cap stops exactly at 4096 archived bytes, releases
all reservations, retains the exact response prefix/hash and blocks another
forward. The normalized result is `resource_exhausted`, not provider failure.
Installed OpenCode independently passes the same classification/cleanup test with
a **262144-byte** cap and an inert oversized stream; the workspace is unchanged.
Tests also cover request/rewrite admission, metadata/request ceilings, disk
headroom, partial disk writes, genuine truncated upstream HTTP responses and owned
stream cancellation. Intermediate logs retain a retry-attribution regression
found and corrected during development; the final 220-pass log is authoritative.

[Verification and accounting](evidence/evidence-capture-recovery/verification.json),
[replay receipts](evidence/evidence-capture-recovery/proofs/),
[full regression log](evidence/evidence-capture-recovery/regressions.log).

## The nine historical authored-test failures

The unchanged candidate was copied into isolated offline Docker workspaces.
Production and original authored-test bytes were verified unchanged after all
diagnostics. No frozen trial was resumed and nothing was promoted.

| Historical failed test | Classification and evidence |
| --- | --- |
| `TestTimestampSignerTimedelta.test_timedelta_zero_duration` | Incorrect assertion: zero age equals zero limit; frozen specification requires acceptance |
| `TestTimestampSignerTimedelta.test_timedelta_future_timestamp_invalid` | Test implementation error: `.encode()` on an already-bytes separator raises before expiry validation |
| `TestTimestampSignerTimedelta.test_timedelta_validate_expired` | Timing-sensitive: sleeping 1.1 s can produce integer age 1; equality with limit 1 remains valid |
| `TestTimedSerializerTimedelta.test_timedelta_expired` | Same integer timestamp boundary assumption |
| `TestTimedSerializerTimedelta.test_timedelta_loads_unsafe_expired` | Same boundary; unsafe valid flag remains true at equality |
| `TestTimedSerializerTimedelta.test_timedelta_zero` | Incorrect zero-age assertion |
| `TestURLSafeTimedSerializerTimedelta.test_timedelta_expired` | Timing-sensitive integer boundary |
| `TestURLSafeTimedSerializerTimedelta.test_timedelta_loads_unsafe_expired` | Timing-sensitive integer boundary |
| `TestURLSafeTimedSerializerTimedelta.test_timedelta_key_rotation_second_key` | Test implementation error: bytes `.encode()` fails before rotation is tested |

That is **two incorrect assertions, five timing-sensitive failures and two test
implementation errors**, not nine proven production defects. A sixth timing test,
`TestTimestampSignerTimedelta.test_timedelta_expired`, happened to pass in the
historical controller run. With a diagnostic per-test clock starting at fractional
second `.125`, unchanged tests give **18 passed/10 failed**; at `.95`, they give
**24 passed/4 failed**. No real sleep is needed and no assertion is edited. The
four invariant failures are the two incorrect assertions and two bytes mistakes.

The apparent exact-boundary test also never advances the clock to its 3600-second
limit, so its name overstates its coverage. These are model test-quality/workflow
limitations, independently of successful edit application.

## Genuine production defects found separately

Open differential diagnostics against the pristine source find regressions in
the candidate's unconditional `float(max_age)` conversion:

| Diagnostic input | Pristine source | Candidate |
| --- | --- | --- |
| Numeric string `"100"`, numeric bytes `b"100"`, string `"nan"`, string `"inf"`, object implementing only `__float__` | `TypeError` | Accepted for an age-50 valid signature |
| Nonnumeric string `"invalid"` | `TypeError` | `ValueError` |
| Integer limit `9007199254740995`, age `9007199254740996` | Expired | Incorrectly accepted after rounding the limit upward |
| Integer limit and age both `9007199254740993` | Accepted at equality | Incorrectly expired after rounding the limit downward |

These violate preserved integer behavior and the prohibition on broadening
unrelated invalid-input acceptance. This does not claim that numeric float NaN
was newly accepted; the diagnosed broadening is conversion of previously rejected
types. The diagnostic signer uses a controlled valid signed token, not a bad
signature workaround. No production repair was supplied.

The separate unchanged-candidate recheck still passes **12/12 frozen public**,
**297/297 upstream**, syntax and **6/6 duration annotation sites**, including
overloads. Public checks therefore miss the production regressions above.
`docs/timed.rst` remains byte-identical to the original and the explicit
documentation requirement is unmet. No missing required duration annotation was
found; passing that permissive check does not establish runtime API compatibility.

The drivers produce **38 open observations per source copy**, not an acceptance
score. They and the controlled-clock runs are **diagnostics, never the reserved
24 sealed cases**, and must not later be relabeled as fresh sealed evidence.

## Stop point and reproduction

Use the existing virtual environment and offline images; set the same regression
flags recorded in the evidence and run `python -m unittest discover -s tests -v`.
`AIWORK_TEST_EVIDENCE_CAPTURE` optionally retains replay/conformance receipts.
Diagnostic driver sources and complete container receipts are preserved alongside
the report; run them only on disposable source copies using the pinned image.

No new live trial or approval digest is prepared. The old quarantine/consumed
authorization cannot be reused. Review this capture policy and the unresolved
production/test/documentation defects before separately authorizing further work.
All **4002 historical indexed entries** (overlapping inventories), including the
911-file quarantined bundle, match their saved hashes. Main, remote services/models
and the original roadmap remain unchanged. Stop here.
