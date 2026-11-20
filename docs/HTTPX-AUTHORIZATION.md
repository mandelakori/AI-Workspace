# HTTPX final authorization review

Follow-up: the operator authorized this digest once. The attempted comparison
is now [QUARANTINED](HTTPX-COMPARISON.md) after direct warm-up cleanup failed.
The preparation review below is preserved; its example commands must not be
used to resume or repeat the closed comparison.

**PREPARED_NOT_AUTHORIZED.** Preparation made zero model inference requests.
No trial state, operator grant or private acceptance inputs have been created.
The frozen Click delivery is unchanged. This supersedes the earlier HTTPX
permission draft without modifying its inputs or historical receipts.

The exact [approval manifest](evidence/phase61/authorization/manifest.json) and
[digest](evidence/phase61/authorization/manifest.sha256) are ready for review:

```text
3bdd3fb56a0d2f8c15fdbdf3ff879619a2dc94cb09f64c43b6fce6af65114b53
```

The digest is SHA-256 of UTF-8 `json.dumps(manifest, sort_keys=True,
separators=(',', ':'))`, rather than the pretty-printed file bytes. It binds
all controller Python modules, harness executable, helper assets, complete
starting inventories, permissions, commands, model and resource protocol.
Code, input or harness drift invalidates dispatch. The original review and its
older JSON canonicalization remain recorded in the manifest.

## Frozen inputs and permissions

| Item | Verified identity |
| --- | --- |
| HTTPX 0.28.1 | `26d48e0634e6ee9cdc0533996db289ce4b430177`; clean pinned checkout |
| Feature specification SHA-256 | `06f1948ce3f59fe02503e0a3cd91fd6c8987adc41d3a9ddabf899aad0b7a355c` |
| Original 16-case public corpus SHA-256 | `532542411a986c14f0315947840c41bf9a520358a8931b2e69a1dc1e1d0dbab5` |
| Existing verification image | `sha256:d3521c3f00c0489a2c2ddccd1975469ee5658bac4e5a79fafd94a1f4f017ada3` |
| Existing local model | `aiwork-qwen35-phase4:8k`, digest `5852b52876b93f88a1d3b8f6a9888e3f6f904a38dff024a18f28831f6cbc1048` |
| Profile SHA-256, new canonicalization | `b7ebfeaeb3628a356c52a4d6b29131aa57a49305848f45d7b592919a53de6afa` |

Both arms start from identical 121-file inventories: the original 119 files plus
two read-only public scoring/policy helpers. No implementation is supplied.
Only `httpx/_utils.py`, `httpx/_client.py`, `tests/test_path_mounts.py` and
`docs/advanced/transports.md` may change. The original public cases and existing
repository tests remain read-only.

Both arms use the same local endpoint, model, 8,192-token context, 2,048-token
response limit, reasoning setting `none`, OpenCode executable, tool menu,
offline image, full public corpus and selected upstream tests. The profile is
unchanged; backend reasoning behavior has not been exercised in this preparation.
Public commands expose the complete 16 cases, 14 pattern cases, two client
integration cases, the existing 75-test upstream selection, and an authored-test/
documentation check. The two helpers add observable scoring and delivery gates;
they do not change the original feature assertions.

## Fixed execution and model protocol

Each arm reserves **240 seconds**, split into **20 seconds warm/preflight,
180 seconds engineering and public verification, and 40 seconds independent
grading**. The pair reserves at most 480 seconds. Unused allocations cannot be
transferred or refunded. Planning, inventory/admission during the phase,
inference, inspection, editing, tool execution, integration, candidate scoring
and freezing share their phase's absolute deadline. Offline preparation and
operator review precede these phases. Independent case authoring occurs after
all work closes, outside active execution; executing those cases consumes the
40-second grade reservation.

Budgets are persisted before launching children. UTC and monotonic deadlines,
owned Windows process jobs, per-container absolute-deadline watchdogs and
ownership-checked container cancellation enforce the limit. Finished, failed,
expired and interrupted reservations cannot restart. Controller resume/reset is
also forbidden for measured states. Workers receive no private budget lease.
Two worker sessions and one planner request are maximums; the direct arm does
not use its planner allowance. Each worker has 16 persistent MCP calls, including
inspection and diff calls; reconnecting cannot reset them. There is no enforced
matching total-token ceiling, and no claim that two worker sessions equal two
inference requests. Report actual usage, including the neutral request/planner.

Only cancellation may continue after the deadline, for at most ten seconds per
phase. No additional inference, tools or verification may start then. The shared
Ollama server is never terminated. Its backend cancellation latency remains
**UNTESTED**: an interrupted inference client, interrupted phase launch, warm/work
watchdog timeout or failed cleanup quarantines the pair and blocks further arms
and grading. Cancellation overhead is reported separately from useful execution.

Run direct first, then hierarchical, in an exclusive operator window. Record
initial model residency; a cold initial server is allowed. For each arm, make
exactly one neutral request, `Reply with exactly READY.`, temperature zero,
maximum four output tokens, with the profile's reasoning setting. Save request,
raw response and residency. Require the pinned digest, resident context 8,192
and at least 185 seconds of residency TTL. Cold loading must fit the same
20-second allowance; both successful arms then receive the full 180 seconds.
Do not unload models, restart services or change server settings. Each harness
gets a fresh isolated home. This does not prove every provider KV cache is
purged; one ordered pair supports an exploratory comparison, not a causal claim
of hierarchical superiority.

Direct execution gets up to two monolithic attempts. Hierarchical execution gets
one model-proposed two-step graph, one attempt per step, on one worker lane.
The planner may partition only the approved paths and command menu; no new tools
or permissions are allowed. Invalid plans receive no extra inference request.
Both use the same final public selector and protect previously passing cases;
ties retain the predecessor. A frozen baseline is the fallback. Worker stages,
including interrupted exports, are retained with ownership/location receipts;
live bounded traces survive controller termination. Retained external temporary
stages are evidence and are not automatically deleted.

## Independent grading and execution gate

Both engineering phases must close before any acceptance cases are authored.
Use exactly 24 genuinely new cases covering boundary paths, encodings,
precedence, sync/async integration and legacy behavior. Save them only at
`private/cases.json` inside the approved bundle. The same case hash is required
for both arms. The generic grader has no acceptance inputs; expected outputs
are never mounted in a worker/candidate container. Frozen candidate hashes are
checked again before grading. Partial/timeout receipts remain incomplete, and
neither arm can resume or receive sealed feedback for repairs.

The local execution bundle is
`.aiwork/phase61-authorization/benchmark-v2`. The earlier preparation at
`benchmark` is preserved, superseded and invalidated by the grader correction.
No authorization file has been written. After explicit operator approval, the
trusted operator can write a separate grant containing exactly:

```json
{
  "approval_digest": "3bdd3fb56a0d2f8c15fdbdf3ff879619a2dc94cb09f64c43b6fce6af65114b53",
  "authorize": ["direct", "hierarchical"],
  "operator_approved": true
}
```

These commands are for **after authorization**, from the repository root:

```powershell
$bundle = '.aiwork/phase61-authorization/benchmark-v2'
$grant = '.aiwork/phase61-authorization/operator-approval.json'
.venv/Scripts/python.exe -m aiwork.httpx_benchmark run $bundle --arm direct --authorization $grant
.venv/Scripts/python.exe -m aiwork.httpx_benchmark run $bundle --arm hierarchical --authorization $grant
# Stop on quarantine. After both work phases close, author private/cases.json.
.venv/Scripts/python.exe -m aiwork.httpx_benchmark grade $bundle --arm direct --authorization $grant --cases "$bundle/private/cases.json"
.venv/Scripts/python.exe -m aiwork.httpx_benchmark grade $bundle --arm hierarchical --authorization $grant --cases "$bundle/private/cases.json"
```

No mid-run implementation guidance is allowed. Any intervention must be recorded
and disqualifies the unassisted classification. No automatic retries, remote
inference, deployment, service modification or merge is included in this review.

## Preparation evidence

The [receipt](evidence/phase61/authorization/preparation-receipt.json) and
[targeted log](evidence/phase61/authorization/targeted-tests-final.log) record
43 passing infrastructure tests, including local Docker ownership/watchdog,
persistent expiry/quota/reconnect guards, retained source, planner integration,
expected-error grading, focused retrieval and process ownership. All inference
is mocked. The full suite and hardware/model fixtures were intentionally not
run under the targeted-only instruction. Historical HTTPX baseline receipts
remain 75/75 selected upstream and 7/16 feature cases; they were not rerun here.
No unfamiliar-feature completion or measured architecture result is claimed.

Reproduce the targeted checks without inference:

```powershell
$env:AIWORK_TEST_DOCKER_IMAGE='aiwork-engineering:phase3'
.venv/Scripts/python.exe -c "import sys,unittest; sys.path.insert(0,'tests'); names=['test_httpx_benchmark','test_trial_budget','test_engineering','test_process','test_focus','test_harness_context']; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names)); sys.exit(not r.wasSuccessful())"
```
