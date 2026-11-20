# Authorized HTTPX comparison outcome

**QUARANTINED — infrastructure failure before engineering.** The single
comparison authorized for digest
`3bdd3fb56a0d2f8c15fdbdf3ff879619a2dc94cb09f64c43b6fce6af65114b53`
stopped at the direct arm's warm-phase cleanup check. No implementation worker
or planner ran. There is no feature candidate or architecture comparison result.

The existing local model cold-started successfully and returned `READY`.
The saved outgoing request contains `max_tokens: 4`, `temperature: 0` and
`reasoning_effort: "none"`. The pinned model digest and resident 8,192-token
context passed the warm checks. Phase process execution took 13.641 seconds;
execution including process termination bookkeeping took 13.656 seconds.
The provider reported 17 input tokens, two output tokens and 19 total tokens,
with zero cached input tokens.

The mandatory ownership query, `docker ps -aq --filter
label=aiwork.trial=aiwork-trial-4623c2f40ad04073b1e06353c1a68690`, exceeded its
frozen three-second command timeout. Cleanup returned failure after 3.047
seconds. The direct budget journal records `quarantined: true`; the runner
stopped before engineering. That journal also blocks subsequent hierarchical
dispatch and grading under the frozen pair-wide quarantine rule. No retry,
Docker recovery operation, service restart or protocol correction was attempted.
The underlying reason for the Docker CLI delay has not been established.

| Measurement | Direct | Hierarchical |
| --- | --- | --- |
| Outcome | Quarantined after warm-up | Not started; pair quarantined |
| Warm inference requests | 1 | 0 |
| Engineering sessions / planner requests | 0 / 0 | 0 / 0 |
| Engineering tool calls | 0 | 0 |
| Model-authored candidate | Absent | Absent |
| Public correctness / regressions | Not evaluated | Not evaluated |
| Independent correctness | Not evaluated | Not evaluated |
| Autonomous completion | Not demonstrated | Not demonstrated |

No source corrections, implementation guidance, private acceptance inputs or
sealed grading occurred. Neither engineering phase reached candidate freeze,
so the requirement to author 24 new acceptance cases was not activated.
Absent candidates are not assigned zero scores. This outcome measures an
infrastructure interruption and provides no evidence about repair capability
or hierarchical performance. Unspent phase reservations cannot be transferred,
resumed or used to start another campaign under this authorization.

The approved inputs, code, permissions, profile, image and budgets remain
unchanged. Frozen Click and `main` remain unchanged. No remote inference,
deployment or merge occurred. No additional regression run was needed because
the execution introduced no implementation changes; the preparation's 43
targeted passing checks remain historical evidence.

The [complete outcome](evidence/phase61/httpx-comparison/pair-outcome.json),
[timing/cleanup receipt](evidence/phase61/httpx-comparison/warm-process.json),
[raw request](evidence/phase61/httpx-comparison/warm-wire-request.json),
[raw response](evidence/phase61/httpx-comparison/warm-wire-response.json),
[residency receipt](evidence/phase61/httpx-comparison/warm-state.json) and
[evidence hashes](evidence/phase61/httpx-comparison/evidence-hashes.json) are
preserved. The original budget journal and all raw local files remain under
`.aiwork/phase61-authorization/benchmark-v2`; the exact operator grant is at
`.aiwork/phase61-authorization/operator-approval.json`. The approved manifest
has not been edited to disguise the interrupted run or authorize a replacement.

This comparison is closed to further dispatch. A future diagnosis or replacement
trial requires a separate decision; no continuation command is issued here.
