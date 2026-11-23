# Native workbench validation

The existing workbench reproduced four frozen ELF candidate results, including both
ledger failures. Ghidra and the REA static adapter ran on the installed toolchain.
One clean-start A100 ledger trial is **PREPARED_NOT_AUTHORIZED**. It targets the
remaining whole-program reconstruction gap. ItsDangerous remains closed.

| Capability | Status | Demonstrated scope |
| --- | --- | --- |
| PE/ELF intake | Verified | x86-64 PE and ELF64 metadata and bounded strings on authorized fixtures. This is lightweight header inspection. |
| Ghidra analysis | Verified | Installed 12.1.4 emitted a function signature, call relationships and decompilation for PE `shipping_points` and ELF ledger `main`. |
| External static analysis | Verified | Installed REA 6.7.0 returned structured PE resource evidence for an empty tree and a known four-byte RCDATA resource. Reviewed specialist authorization enforced. |
| Function reconstruction | Verified | Historical A100 `shipping_points` delivery matched 182 finite comparisons. Meter state repair later matched 32/32 after integration. This session exercised PE analysis and Linux verification. |
| Multi-function reconstruction | Verified | Ranked autonomous classifier repair preserved earlier passes, reached 22/22 public and 48/48 independent cases, and reproduced both scores. |
| Stateful reconstruction | Partially verified | Historical meter, debt and water integrations from reviewed component contracts passed finite suites. Monolithic ledger reconstruction and the window-counter trials showed unresolved framing, parsing and transition failures. |
| Candidate repair and rollback | Verified | The original classifier repair gained nine public passes. The archived ledger GCC failure was reproduced and the selector retained the 13/18 incumbent. |
| Independent differential verification | Verified | Pinned Linux Docker; isolated reference/candidate runs, exact final streams and exit status, and separate post-freeze grading. Replayed historical suites retain their original evidence status. |
| A100 OpenCode native execution | Implemented | Existing controller, catalog and bounded host-local tools. This trial's model, template and idle context slot were checked read-only. The proposed native worker run awaits approval. |
| General executable equivalence | Unsupported | Evidence covers finite invocations on the pinned fixture and runner. Arbitrary programs, PE differential execution in the Linux runner, persistent side effects and other environments are outside this proof. |

## Local validation

Installed Docker Desktop started its Linux 29.9.3 engine. The native runner
resolved to `sha256:1b5e1619d2da515d953428d37729da1e25d2fa18946c1289780f3b7d65e3bd9b`.
Docker pulls were disabled. The archived reference source rebuilt byte for byte
to the original ledger ELF. Fresh Ghidra projects were cleaned up, and the
replays left zero additional `aiwork-check-*` containers. Target, source and
public corpus inventories matched their original receipts after replay.

The static PE probe used the existing self-authored C fixture and the installed
x64 MSVC Developer PowerShell. A disposable build linked `101 RCDATA { 0x1234,
0x5678 }`. REA reported type 10, ID 101, language 1033 and a four-byte payload. A
direct slice of the PE at the reported offset matched both the known bytes and
the adapter's SHA-256. Neither static PE fixture was executed. The earlier
`NativeDemo.ps1` host verification remains historical. The new local run used
the Docker-based verifier for generated candidates. The static adapter used the
installed cached REA 6.7.0 entry point already recorded by `ReaDemo.ps1`.

| Frozen candidate | Public replay | Archived final | Final replay | Replay time |
| --- | ---: | ---: | ---: | ---: |
| Byte-stride, A100/Qwen Code | 5/5 | 48/48 | 48/48 | 24.547 s |
| Classifier repair, laptop/OpenCode | 22/22 | 48/48 | 48/48 | 25.187 s |
| Initial ledger, A100/Qwen Code | 3/3 | 47/48 | 47/48 | 24.469 s |
| Ranked ledger incumbent, laptop/OpenCode | 13/18 | 10/48 | 10/48 | 24.344 s |

All four candidates recompiled. Across the 192 final cases, all individual
verdicts and differing channels matched the archived reports. The ledger had
one and 38 stdout mismatches respectively, with zero inconclusive cases. These
were the original suites for each checkpoint. Their results support replay
stability. Comparing the two ledger scores cannot establish a regression
because the final suites differ. The original classifier generation scored
44/48 historically. The archived classifier starting source scored 36/48 on
the later matched suite where the repaired checkpoint achieved 48/48.

The relevant suite passed **54/54 in 41.431 s, zero skips**, including the installed
inert OpenCode boundary test, the actual Docker oracle isolation test and the
owned-container watchdog test. The oracle probe checks the read-only `/work`
mount, loopback-only networking, and absence of private mounts and the Docker
socket. The ranked repair tests reject a private verification directory, and
the native grader rejects overlaps with public or supplied audit stimuli. The
trial staging inventory contains only the four approved public files. Historical
private inputs remain outside it. No new private acceptance cases were authored.
Four additional installed OpenCode conformance tests passed in 17.484 s. They
exercised catalog failure before forwarding, scoped edits, inspected-location
recovery and clean exhaustion. A disposable submission of the exact prepared
task staged the four approved files with no private directory or attempt.

The archived duplicate `case` proposal failed GCC again. The low-level generic
label is `command`, while the receipt independently records `compiled=false`
and the checkpoint decision correctly classifies `build_regression`. This is
a diagnostic-label precision issue. The existing selector preserves the stronger
candidate. Historical REA-Next selection rejected the round that required a
second classifier operand and scored 7/22 versus 17/22. Its transport, archive
hash checking and static-only import are implemented. The current session ran
the archive-input boundary tests and no REA-Next campaign.

The native controller exposes public expected-versus-observed diagnostics and
retains failed sources, patches and checkpoints. Its historical ledger proposals
failed compilation or broke previously passing cases. The earlier REA-Next
classifier regression was a protocol misunderstanding. In the Phase 5 ledger
closeout, framing 4/7, validation 14/18 and A100 balance 9/10 all passed UBSan.
Those were partial components. Integration did not qualify. Historical model
and harness limits include unchanged proposals, truncated responses and no
candidate delivery. They are separate from the reproduced behavioral mismatches.

## Prepared A100 validation

Bundle `.aiwork/native-workbench-validation/a100-ledger`.
Approval digest `8698eb97b2f06104dca2c14003848a30e664b03723e4c87777f638d94315510a`.
Authorize exactly `["a100-existing"]` in a separate approval. The workbench is
ready to proceed directly with this protocol once approved. No core correction
is needed. The review script binds the existing controller and verifier to the
digest, enforces one-shot phases and requires clean public closure before export.
The plain historical `native run` path can freeze a compiled partial candidate.

- Start with the existing ledger ELF, SHA-256
  `27b217da0301b0c7d28479b8163d73e6c5a2191c854d1acaff86cb0d124ddd1d`.
  The original C stays on the verifier side. The worker can read `binary.json`,
  `ghidra.json`, `examples.json` and `native_feedback.py`. `candidate.c` is the
  sole writable output and starts absent. Baseline is zero public passes with
  `missing_deliverables`. The pinned reference reproduced 18/18 observations.
- Use the existing A100 Qwen3.6 35B-A3B Q6_K with OpenCode, 65,536 context,
  4,096 output tokens, temperature 0, seed 1729 and reasoning disabled. One
  attempt of at most 720 s, inside 20/900/120 s warm/work/grade reservations.
  Allow 96 MCP operations, eight reserved edits and eight reserved public
  checks, 64 model requests, four compactions, 64 MiB capture and 32 MiB disk
  headroom. One worker, no planner, retries, fallback or implementation guidance.
  The warm phase checks the exact endpoint and idle slot before work. The
  existing provider gate requires the scoped tool catalog before forwarding.
- Require an applied edit, a successful worker public command 0, controller
  compilation and 18/18 public results on the same corpus, plus clean harness
  and phase cleanup. Only then freeze the selected source. Stop on a failed
  closure. Preserve usage, scope, source hashes and checkpoint receipts.
- Only after clean freeze, author exactly 32 fresh private stdin scenarios under
  `private/cases.json` outside worker input. Cover line boundaries, malformed
  and extra tokens, EOF fragments, range checks and state retention. The
  verifier rejects overlap with the 298 recorded public or previously graded
  stimuli and compares exact exit status, stdout and stderr against the
  reference in separate containers. Full acceptance is 32/32. Final results
  never feed back to the worker. Enforce one grading phase and stop afterwards.

```powershell
$nativePy = '.venv/Scripts/python.exe'
$nativeTrial = '.aiwork/native-workbench-validation/a100-ledger'
& $nativePy examples/native/ledger_trial.py validate $nativeTrial
# After approval, put the exact grant in a separate file and run once.
& $nativePy examples/native/ledger_trial.py run $nativeTrial --approval '<grant.json>'
# Only after a clean freeze and independent case authoring.
& $nativePy examples/native/ledger_trial.py grade $nativeTrial --approval '<grant.json>'
```

The grant requires `approval_digest`, `authorize` and Boolean `operator_approved`.
Validation rejected a false grant, premature grading, and drift in the target,
public observations and exclusions on disposable copies. The live execution
path and grading of this new trial remain untested. The exact manifest, native
fixture recipes, static reports, hash records and test log are in the evidence
directory. The local replay state retains the full per-invocation records and
private inputs. The preservation audit matched 4,307 historical indexed entries.
Main and the original roadmap are unchanged.

[Evidence](evidence/native-workbench-validation/README.md) · [Phase 4](PHASE4.md) ·
[Phase 5.1](PHASE51.md) · [Phase 5 handoff](PHASE5-HANDOFF.md)
