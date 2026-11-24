# Current status — 1.0.0rc1

Operator review on `phase61/autonomous-completion`. The original Milestones A–E
remain authoritative. The [acceptance matrix](ACCEPTANCE.md) gives the current
verdict for each gate. The [historical status ledger](STATUS-HISTORY.md)
preserves earlier observations, preparation states and test counts verbatim.

| Capability or outcome | Status | Evidence |
| --- | --- | --- |
| RC package and essential CLI | VERIFIED | Offline wheel built and installed in an isolated venv. Version, help, doctor, task inspection, direct verification and queue/status paths were checked. [Release notes](RELEASE-NOTES-1.0.0rc1.md). |
| Laptop model startup through engineering verification | VERIFIED | One owned 16K model instance, one accepted edit, 4/4 public and 6/6 independent. [Local smoke](LOCAL-ENGINEERING-SMOKE-RESULT.md). |
| Existing A100 scoped execution | VERIFIED | Historical live execution and owned SSH recovery. The RC verification was offline. [Benchmarks](BENCHMARKS.md), [routing](ROUTING-VALIDATION.md). |
| Local ownership-aware admission and reclamation | VERIFIED | Deterministic lock, ownership, recheck and eligible fallback checks. Live external unload is UNTESTED. [Stabilization](RELEASE-STABILIZATION.md). |
| Matched live cross-plane comparison | UNTESTED | The first admission was blocked on local memory. The repeated preflight passed, but the local arm failed during cold load and the A100 arm was withheld. Later standalone load and smoke results do not complete that pair. [Admission](ROUTING-CROSS-PLANE-RESULT.md), [execution](ROUTING-CROSS-PLANE-EXECUTION.md). |
| Managed Lambda lifecycle | MOCKED / BLOCKED | Existing SSH operation is separate from provisioning. Live managed launch, bootstrap, termination and volume recovery lack completed acceptance. [Managed profile prerequisites](NEXT-STEPS-HISTORY.md#lambda-managed-profile). |
| Native workbench | VERIFIED | PE/ELF analysis, Ghidra, REA PE resources, finite differential grading and bounded reconstruction. [Workbench](NATIVE-WORKBENCH-VALIDATION.md). |
| Whole-program stateful native reconstruction | BLOCKED | Ledger partial components and failing finite candidates are retained. The clean-start A100 trial produced no candidate. [Ledger result](NATIVE-LEDGER-A100-RESULT.md). |
| General autonomous engineering acceptance | BLOCKED | Local fixture completion and model-authored real-project progress coexist with failed final gates. Click and PyPA feature delivery involved operator assistance. [Milestone E](MILESTONE-E-FINAL-RESULT.md), [acceptance matrix](ACCEPTANCE.md). |

## Trial disposition

| Recorded protocol | Current disposition |
| --- | --- |
| Local load-only check and RC engineering smoke | Both passed and consumed their own grants. [Load-only result](OLLAMA-LOAD-ONLY-RESULT.md), [smoke result](LOCAL-ENGINEERING-SMOKE-RESULT.md). |
| Original local-first cross-plane pair | Local grant consumed. A100 grant unused and held by the original completion gate. It does not authorize a standalone A100 arm. [Execution](ROUTING-CROSS-PLANE-EXECUTION.md). |
| ItsDangerous trials | Closed and consumed, with quarantine where recorded. The final trial did not freeze a candidate or reach sealed grading. [Final outcome](MILESTONE-E-FINAL-RESULT.md). |
| Ledger and A100 thinking-mode diagnostic | Consumed under separate protocols. Ledger froze no candidate. The thinking diagnostic completed both bounded arms and was independently graded. [Ledger](NATIVE-LEDGER-A100-RESULT.md), [thinking diagnostic](A100-THINKING-DIAGNOSTIC-RESULT.md). |
| HTTPX and source-discovery campaigns | Closed and quarantined as documented. No restart, delayed arm or sealed grading is authorized. [HTTPX pilot](HTTPX-SINGLE-ARM-PILOT-RESULT.md), [source discovery](DISCOVERY-EXPERIMENT-RESULT.md). |
| Pi/OpenCode comparison | Historical `PREPARED_NOT_AUTHORIZED` draft. Remains unauthorized. [Review](LOCAL-HARNESS-COMPARISON-REVIEW.md). |

Preparation records are historical evidence. They do not authorize dispatch,
reuse of a consumed grant, or changes to existing services. The RC uses
ordinary operator-submitted tasks as described in the [operator guide](OPERATOR-GUIDE.md).
