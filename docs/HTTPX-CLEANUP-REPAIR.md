# HTTPX cleanup correction and replacement review

**PREPARED_NOT_AUTHORIZED.** No real model inference or engineering campaign
ran during this correction. The original quarantined comparison, authorization
and evidence remain unchanged. Its reservations cannot resume.

## Diagnosis and correction

Three bounded, read-only Docker queries reproduced a successful ownership query
lasting **5.813 seconds**, followed by the same empty query in **0.140 seconds**.
The preceding server-version query succeeded in **0.125 seconds**. Thus the
old three-second per-command cap can fail despite a healthy response within
the existing ten-second cleanup allowance. The precise Docker Desktop/daemon
latency mechanism, including its role in the historical interruption, remains
unproven. No service was restarted and no unrelated container was changed.

Inspection also established that trusted HTTPX warm-up performs model metadata,
residency and read-only Docker version/image checks, but launches no containers.
The mandatory container scan during that phase was unnecessary.

The bounded fix:

- Container cleanup commands share one absolute **ten-second** deadline. Each
  receives only its remaining time; there is no new retry or larger allowance.
- Warm-up forbids verification commands/container launches in the central
  verifier. Its container cleanup is explicitly recorded as inapplicable.
- Work and grading retain label-filtered enumeration, exact ownership inspection,
  owned-container removal and a final empty check. Failed ownership inspection
  now fails closed immediately, including a possible disappearance race.
- Timeouts, unknown ownership and cleanup failure still fail closed. Interrupted
  inference and phase watchdog expiry still quarantine the pair. Resume/reset
  remains forbidden. The **20/180/40-second** reservations are unchanged.

Four focused tests cover the slow-successful-query reproducer, shrinking cleanup
time, failed/mismatched ownership and timeout without removal, container-free
warm-up, blocked verification, interrupted inference and persistent quarantine.
The complete suite passes **115/115**, zero skips, in **67.480 seconds**, including
offline Docker and installed OpenCode against an inert loopback provider.
No deeper process-ownership defect was demonstrated by this investigation.

See [diagnostic timings](evidence/phase61/cleanup-repair/docker-diagnostics.json),
[full regression log](evidence/phase61/cleanup-repair/regressions.log) and
[integrity receipt](evidence/phase61/cleanup-repair/receipt.json).

## Replacement authorization for the next session

The [new exact manifest](evidence/phase61/cleanup-repair/manifest.json) binds the
corrected implementation and cleanup policy. The specification, original public
corpus, identical clean starting inventories, model/settings, verification image,
four writable paths, tools and total budgets match the prior preparation.
No trial states, operator grant or independent acceptance inputs exist in the
fresh bundle at `.aiwork/phase61-cleanup-repair/benchmark`.

New approval digest, using the original minified/sorted JSON digest procedure:

```text
cac8f70e899ef694fde19c0100109a92636b316e5bc5020086d7c7809c9a4639
```

Only after explicit approval of **this** digest for exactly
`["direct", "hierarchical"]`, write a fresh grant at
`.aiwork/phase61-cleanup-repair/operator-approval.json` containing exactly:

```json
{
  "approval_digest": "cac8f70e899ef694fde19c0100109a92636b316e5bc5020086d7c7809c9a4639",
  "authorize": ["direct", "hierarchical"],
  "operator_approved": true
}
```

After that approval, run from the repository root:

```powershell
$bundle = '.aiwork/phase61-cleanup-repair/benchmark'
$grant = '.aiwork/phase61-cleanup-repair/operator-approval.json'
.venv/Scripts/python.exe -m aiwork.httpx_benchmark run $bundle --arm direct --authorization $grant
# Check the direct receipts; stop immediately if quarantined.
.venv/Scripts/python.exe -m aiwork.httpx_benchmark run $bundle --arm hierarchical --authorization $grant
```

The existing neutral warm-up protocol, no-guidance rule, two worker sessions,
one planner-request maximum, persistent MCP quotas, public candidate selection
and freeze-before-grading rules remain in the exact manifest. Once both work
phases close without quarantine, independently author exactly 24 new cases at
`$bundle/private/cases.json`; use the same cases for both frozen candidates.
Grade each arm once with the `grade` action, the new grant and
`--cases "$bundle/private/cases.json"`, within its 40-second reservation.
Never expose sealed feedback to workers. Any quarantine stops all dispatch.

The old approval is deliberately rejected by the replacement bundle. No launch,
service change, remote experiment, deployment or merge is authorized by this
handoff. Frozen Click and `main` are unchanged.
