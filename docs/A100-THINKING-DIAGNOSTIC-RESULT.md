# A100 thinking-mode diagnostic result

**Both workers completed the public task. OFF passed 12/12 independent cases.
ON passed 7/12, with four mismatches and one inconclusive invocation.** The
A100 emitted reasoning in all four ON responses and none of the five OFF
responses. Both arms compiled, passed 5/5 public observations, and froze their
own model-authored candidate after clean engineering closure. This one pair
shows a difference on the byte-stride fixture under the approved limits.

| Measurement | OFF | ON |
| --- | ---: | ---: |
| First applied edit, seconds after arm start | 37.918, operation 5, request 3 | 36.995, operation 4, request 2 |
| First public check, start → passing completion | 41.743 → 43.235 s, operation 6, request 4 | 41.015 → 42.550 s, operation 5, request 3 |
| MCP allocation | 6 = 4 focus + 1 edit + 1 check | 5 = 3 focus + 1 edit + 1 check |
| Accepted / rejected edits / tool errors | 1 / 0 / 0 | 1 / 0 / 0 |
| Compiled public results | 5/5 | 5/5 |
| Independent results | 12 pass, 0 mismatch, 0 inconclusive | 7 pass, 4 mismatch, 1 inconclusive |
| Provider requests / usage receipts | 5 / 5 | 4 / 4 |
| API prompt / completion / total tokens | 36,534 / 1,186 / 37,720 | 29,013 / 2,420 / 31,433 |
| Observed reasoning emission | 0/5 responses | 4/4 responses, 5,280 UTF-8 bytes in `reasoning_content` |
| API reasoning-token counter | Unreported in 5/5 receipts | Unreported in 4/4 receipts |
| API cached prompt tokens | 0 reported, 5 receipts | 0 reported, 4 receipts |
| Model output length stops / compactions | 0 / 0 | 0 / 0 |
| Peak API prompt tokens | 9,601 | 9,673 |
| Worker wall time | 28.125 s | 33.062 s |
| Arm start through freeze and engineering closure | 55.508 s | 54.227 s |
| Independent grading phase wall time | 7.875 s | 17.703 s |
| Captured provider payloads | 583,597 bytes, 15 verified files | 946,541 bytes, 12 verified files |

First-edit and first-check times use the OpenCode event clock relative to the
recorded arm start. Tool-call IDs bind those events to the originating captured
provider requests. All nine streams returned HTTP 200 and completed with their
usage receipts. The ON response bytes evidence a reasoning emission, with no
separate API token count. OpenCode's aggregate reported zero reasoning tokens
even for ON, so that counter does not quantify the observed emission.

ON used one fewer request and roughly twice the completion tokens. It reached
the edit and check in fewer operations, with less than one second difference in
the observed milestone times. Its worker took about five seconds longer. The
arm wall times include warm-up and independent public verification overhead.
The fixed OFF → ON order and a single observation per arm limit conclusions
about latency and general model quality. The API reported no cache hits, and
the benchmark did not reset the shared server's cache.

## Source and independent grading

Both candidates replaced the same compilable 0/5 C placeholder. OFF checked
exact argument count and the 40-byte text cap, consumed the full decimal token,
and validated the step range. ON implemented the stride loop but accepted
surplus arguments and omitted the text cap. It parsed the step without an end
pointer and compared it to the text length instead of checking the specified
range. Public fixtures allowed both approaches to pass.

The four ON mismatches concerned excess text length, trailing whitespace in
the decimal argument, negative steps, and surplus arguments. The malformed-sign
case parsed to a zero step and made no progress in the output loop. The
read-only sandbox invocation reached its 12-second timeout and retained
1,048,576 output bytes at the cap. The independent verifier marked that case
**inconclusive**. This was a candidate execution limit. The grading phase
finished and owned cleanup passed. Both grading phases compared exact exit
status, stdout and stderr in separate network-disabled Docker containers.

| Arm | Frozen `candidate.c` SHA-256 |
| --- | --- |
| OFF | `2fb2d073abd0c60a2aee339731c3bb246f9792bb56ff5b4887abeb20cd38206a` |
| ON | `17e24e3b646b2bfc352244e92375d9ca4db41ca65c73459095f7275b7b74d939` |

The shared private suite was authored from the reference contract after both
closures, without consulting either candidate. It has 12 distinct stimuli and
no overlap with the 53 known public or historical cases. Its SHA-256 is
`2af9014e0d23ae5480f557904a06edb4ee5e875225ad8e792d240e59d811440e`.
Both grader copies matched that digest. Private inputs and raw oracle outputs
remain local. Only redacted observations and the suite hash are committed.
Neither worker received any sealed feedback.

## Scope and integrity

Both separate grants from `6132031` are consumed. Preflight matched all 83
prepared evidence hashes, the pinned binary and inputs, the implementation and
OpenCode binary, the exact four tools, and the request and resource controls.
The existing endpoint matched the model, template and idle slot. The four
frozen template renders reproduced without inference. Each surviving provider
body preserved its approved Boolean, generation settings, scoped tool catalog
and single initial system message. The controller ran once per arm under the
approved 210-second, 18-request, 24-operation, 65,536-context and 4,096-output
limits.

Both workers exited 0, and all owned warm/work/grade cleanup receipts passed.
Neither arm was quarantined. Read-only postflight found the same A100 endpoint
healthy and idle, and its owned SSH forward closed. The runtime, remote
services, historical evidence and `main` were preserved. The preparation's
235-test result remains attached to its original commit. This outcome commit
contains the model-authored copies, two complete execution traces, public and
sealed verdicts, and audit records. Execution ended after this pair.

[Evidence archive](evidence/a100-thinking-diagnostic-result/README.md) ·
[Frozen preparation](A100-THINKING-DIAGNOSTIC.md)
