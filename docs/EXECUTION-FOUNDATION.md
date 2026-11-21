# Context and resource execution foundation

Implementation follows `a5c106a` on `phase61/autonomous-completion`. Phase 6.1
benchmarking remains closed. No live comparison, remote inference, download,
service reconfiguration or historical trial resume is authorized by this work.

## Diagnosis and correction

**VERIFIED:** The closed B trace lost source in two compactions while its duplicate
cache retained the source keys. `execution_context.py` now separates the immutable
active contract, context epochs, visible excerpts and durable resource counters.

The old adapter wrote `operator-task.md` and configured `instructions`, assuming
persistent system delivery. Neither the active-objective header nor its full work
order reached the recorded system message. The ordinary user objective was later
replaced by checkpoints. Installed OpenCode 2.0.27 inert requests reproduce the
missing header before the controller's new injection.

Upstream configuration acceptance is separate from delivery: the pinned
[normalizer](https://github.com/anomalyco/opencode/blob/v2.0.27/packages/core/src/config/normalize.ts)
accepts `instructions`, while the inspected
[discovery plugin](https://github.com/anomalyco/opencode/blob/v2.0.27/packages/core/src/config/plugin/instruction.ts)
loads global/project AGENTS.md sources and can disable discovery. **UNTESTED:**
the exact upstream omission across all loading paths. This is a controller boundary
fix, not an upstream fix. This change enables no project/global discovery.

Every engineering provider request, including summaries, now receives a canonical
system contract: full objective, writable paths, approved public command/setup
menu, original absolute deadline and resource policy. Independent checks and
private evaluation files are excluded. Incoming and forwarded bodies have separate
artifacts and hashes. Tool schemas and generation settings are unchanged. Contract
byte overhead is recorded and must be included in subsequent context planning.

Focus results retain content-addressed source artifacts, file hashes, line locations
and evidence keys. Only valid verbatim source in provider-facing **tool** messages
counts as visible; summary assertions do not. Observed evictions and recognized
pinned summary requests advance epochs. Evicted source can be inspected again.
Exact hashes and unique anchors remain mandatory; the editor implementation is
unchanged. A changed task contract cannot reopen the ledger.

## Resource and permission contract

Optional task TOML fields, with new production defaults:

```toml
tool_operations = 48
edit_reserve = 4
public_test_reserve = 4
model_requests = 64
compaction_limit = 4
```

These are configurable limits, not experiment authorization. Captured legacy tool
specs without a policy retain their historical 16-call allowance and zero
reservations. Historical manifests are neither regenerated nor executed.

All new engineering navigation/edit/test operations pass through scoped MCP.
Unmetered native navigation and mutation tools are denied; the provider gate rejects
unexpected tools. Controller source inventories and focus symbols/query/pagination
remain available. Inspection cannot spend unconsumed edit/test reservations.
Rejected edits also consume edit operations. Three consecutive reservation-blocked
calls stop unproductive generation. All forwarded requests consume the model quota;
summaries additionally consume the compaction quota. Context changes and reconnects
never replenish resources. Existing attempt/phase deadlines and independent
verification time reservations remain enforced. A separately configured new attempt
is not a resume; quarantined measured trials remain nonresumable.

`execution-context.json` records category counts, inspection/edit/verification/
inference/compaction/cleanup elapsed time and context events. Provider durations
include transport/evidence capture. The verification counter covers worker public
checks; controller independent checks have separate verdicts/artifacts. Categories can overlap and are not an additive
wall clock; the execution receipt separately records total harness time.

Exhaustion refuses further upstream forwarding with a controller-specific error.
The receipt retains the harness's raw exit and reports `resource_exhausted` only
after successful cleanup and without provider failure, timeout or truncation.
This allows independent verification of any preserved candidate, not a claim of
completion. Provider failure, interruption, scope failure, capability rejection and
cleanup failure have distinct statuses. Existing quarantine rules remain authoritative.

## Portable harness contracts

`harness_contracts.py` declares required capabilities and rejects unsupported
adapters. Schema-1 execution receipts record adapter, status, raw exit, elapsed
time, timeout, cleanup, provider admission and independent verification status.
Successful OpenCode sessions also include resource counters and provider usage
by request/category; unavailable usage is explicit. The controller records its
independent verdict outside the worker's context.

| Adapter | Current outcome | Integration requirement |
| --- | --- | --- |
| OpenCode 2.0.27 | VERIFIED installed inert-provider conformance; live engineering UNTESTED | Preserve pinned readiness, provider gate, exact MCP editor, owned jobs and independent verification. Recertify future versions. |
| Qwen Code 0.27.4 | BLOCKED engineering; restricted legacy adapter retained | Native edit/write_file and check/diff permissions do not provide hash editing or provider/context gates. Disable native mutations, bridge all scoped tools, align retries and prove cancellation/cleanup. Rejected before endpoint or remote readiness. |
| Pi | UNTESTED, unimplemented | Pin SDK/RPC, disable builtins, supply reviewed MCP extension, scoped permissions, provider gate, compaction events and owned cancellation. |
| mini-SWE-agent | UNTESTED, unimplemented | Replace the bash-oriented default environment with reviewed scoped commands/editor. No unrestricted host shell. |
| DeepSeek Harness | UNTESTED, unimplemented | Pin/audit plugin lifecycle, permissions, provider interception, context events and cancellation before connecting scoped tools. |

Declarations are not blanket certification. Positive OpenCode and negative Qwen
receipts are preserved. Unknown adapters fail closed. The controller retains
scheduling, permissions, verification and ranked checkpoint authority.
Primary integration references: [Pi SDK/RPC](https://github.com/earendil-works/pi/tree/main/packages/coding-agent),
[mini-SWE-agent](https://mini-swe-agent.com/latest/),
[DeepSeek Harness and safety documentation](https://github.com/deepseek-ai/deepseek-harness).
No additional harness was installed.

## Adaptive context planning

`context_planning.py` and `context-plan` choose the **smallest feasible** window
from approved candidates. Inputs include model maximum, VRAM/RAM budgets, resident
GPU/CPU footprint, KV bytes/token and GPU fraction, prefill/generation rates,
task demand, headroom and deadline. GPU/CPU resident footprints represent weight
offload and non-KV residency; KV placement is independent. Memory budgets mean
total capacity available to this allocation including residency, excluding other
users. Do not supply OS free memory and subtract already resident weights twice.
Include activations/workspaces in headroom.

```powershell
.\.venv\Scripts\python.exe -m aiwork context-plan examples/context-plan.synthetic.json
```

The example selects 16K, rather than 8K or 32K, using **synthetic** data. Missing
or invalid measurements fail closed. Rejections identify memory, demand, maximum
and deadline limits. Prefill estimates conservatively charge the full input,
without assuming a warm cache. Demand must include the repeated contract and tool
responses. The command produces a reviewable receipt; it does not load a model,
enlarge a profile or reconfigure a service. Qwen3.5-9B/8K remains the controlled
baseline. **UNTESTED:** hardware calibration and real adaptive execution.
Latency is a per-request estimate, not a prediction of multi-turn completion.
Supply the inference allowance after reserving tool/check/cleanup time; cumulative
controller deadlines still apply. Provider-visible source tracking cannot certify
against an inference backend silently truncating its own input.

## Verification

Installed OpenCode with an inert provider actually compacted twice, recovered
source three times, applied one exact edit and passed one public check, without
replenishing quotas. A separate installed test spent its only operation and proved
zero further upstream requests, raw exit 1, clean exhaustion and owned cleanup.
These are scripted protocol tests, not autonomous model implementation evidence.

The pre-change baseline passed 146 tests, with eight optional integrations skipped.
Final verification passed **162/162 tests**, including installed inert-provider and
offline Docker checks, with no skips (122.891 seconds). Intermediate failures and
the final evidence index are retained under `docs/evidence/execution-foundation/`.
Initial inert failures exposed a nonblocking ledger-lock race and mismatched test
summary formats. An intermediate full run found a mocked test missing the now
mandatory spec file. All were corrected and preserved.
Final failure injection also verified accounting errors fail closed while owned
sockets are released. It exposed stale closed-socket bookkeeping, now corrected.
One intermediate Docker test observed auto-removal racing explicit removal; its
assertion now accepts that exact daemon error while still requiring quarantine,
no remaining owned containers and survival of the unrelated test container.
Production Docker cleanup and quarantine behavior were not relaxed.

```powershell
$env:AIWORK_TEST_OPENCODE_BOUNDARY = '1'
$env:AIWORK_TEST_DOCKER_IMAGE = 'aiwork-engineering:phase3'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Loopback/Docker access and the existing image/binary are required. No real model
is contacted. Without these flags, optional installed-harness/Docker tests skip.
The preserved first sandbox failure was loopback access denial, not a model result.

## First live comparison — proposal requiring separate review

1. Complete Qwen's scoped editor/provider/context integration. Pass identical inert
   tests for two compactions, exhaustion, external-file denial, stale hashes,
   interruption and cleanup before comparing harnesses.
2. Freeze a fresh small real-repository objective and baseline. Propose one
   OpenCode/Qwen pair with identical 9B/8K model, snapshot, public corpus, source
   inventory, 150-second attempt ceiling, 180-second engineering reservation,
   48 operations with four edit/four public-test reservations, 64 provider requests
   and four compactions. Explicitly review warm-up/grading and total token limits.
   Randomize order; no retries, fallbacks or mid-run implementation guidance.
3. Record first edit/test, public/upstream and fresh sealed correctness after
   candidate freeze, regressions, evictions/reinspection, primary/summary/cache
   tokens, category timing and total wall time. Missing usage remains unknown.
   One pair does not establish reliable success rates.
4. Separately authorize model/cache/offload context measurements before proposing
   fixed-8K versus resource-planned trials. Hold harness and task constant. Do not
   confound harness/context changes or implicitly change an inference service.

No runnable live manifest or dispatch is created here. Frozen Click, earlier
approvals/quarantines and `main` remain outside this implementation.
