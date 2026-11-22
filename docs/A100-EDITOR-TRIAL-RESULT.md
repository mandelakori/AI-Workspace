# Milestone E: editing recovered; trial quarantined before acceptance

**FAIL — partial autonomous feature progress, no accepted delivery.** The single
trial approved from `05271bd`, digest
`de9bdcda4c591eaf1b2a93927477b3159e4da9f1b480c844ed93abacf46a07e3`,
ran once. The model applied valid edits and improved public correctness from 3/12
to **12/12**, with **297/297 upstream** passing. Its authored tests failed, docs
were unchanged, and the controller's provider-evidence cap interrupted request 45.
The root bundle is quarantined; the authorization is consumed. Do not resume it.

No implementation guidance, historical candidate reuse, retry, fallback, service
change or subsequent campaign occurred. No controller/harness/task implementation
was changed. The source and test corrections are model-authored. No candidate was
frozen and no sealed inputs were created: **not permitted, not 0/24**.

## Measured engineering outcome

| Measurement | Observed result |
| --- | --- |
| Preflight | Manifest/implementation/assets, all 140 original bundle files, original source, permissions, catalog, dependency versions and verifier image match. Current model/template/build identity and idle 131072-token slot match; owned inspection forward closed |
| First inference | HTTP 200; 5537 prompt +114 completion =5651 tokens; valid source-inspection call |
| First successful source edit | **MCP operation 6**, 40.732 s after trial start; uniquely matched LF anchor adapted to CRLF |
| First public test | **MCP operation 16**, 147.091 s after start; **12/12** |
| Accepted edits | **12**: eight production edits, four authored-test-file edits, including creation. Seven use newline adaptation. Zero documentation edits |
| MCP rejections | **5**: `edit_too_large` 2, `invalid_anchor` 1, `syntax_error` 1, `ambiguous_anchor` 1; rejected requests leave source unchanged |
| Other attempted edits | **2** tool argument streams hit the 4096-token output ceiling and remain incomplete; **1** later edit stream is aborted by the capture cap. None reach MCP or mutate files. Total initiated edit calls 20, admitted MCP edits 17 |
| Location recovery | **3/3 accepted**, operations 28, 30, 32. Exact issued inspection keys/current hashes and selected line 54, 106, 159 respectively; the model recovered from ambiguity without first-match or fuzzy replacement |
| Exported public behavior | Controller post-harness verification **12/12**, up nine passes from baseline, zero lost public passes. Production hash equals the earlier passing public-check snapshot |
| Upstream | Worker and controller post-harness check both **297/297**; authored file excluded by the frozen upstream recipe |
| Authored tests | Controller **19 passed, 9 failed**. Last two worker checks each **18 passed, 10 failed**; initial authored check failed because the file was absent |
| API interfaces / syntax | Worker checks both pass. Production source unchanged afterwards. Controller stops its final verification at authored-test failure, so later interface/syntax checks are not rerun there |
| Independent acceptance | No clean closure/freeze; **NOT GRADED**. The quarantine grading guard explicitly rejects access |
| Tools | **47/96 admitted MCP operations**: 23 focus, 17 edit, 7 check; no diff. Checks: one feature-public, one upstream, three authored, one interfaces, one syntax. OpenCode additionally records the three unexecuted edit attempts above |
| Requests / compaction | **45 forwarded**: 44 inference, one compaction (request 31). 44 complete usage receipts; request 45 has none. Epoch 1; peak API-reported prompt 51233 tokens |
| Settings | All 45 forwarded bodies retain one initial system message/authoritative contract, original model, temperature 0, seed 1729, max output 4096 and disabled thinking. Harness context remains 65536; no tool/model budget reset |
| API usage | **1104506 prompt +22958 completion =1127464 total**, including compaction and reported cache tokens. Last request's usage unknown; these are incomplete totals |
| Cache / reasoning | API reports **25311 cached prompt tokens**. No server reasoning-token counter; SDK reports zero. SDK input/output totals exclude compaction and cached input, explaining their lower figures; no cold-cache claim |
| Time | Warm 4.985 s; harness 663.468 s; work process 686.750 s; start-to-quarantine closure **691.987 s** |
| Termination / cleanup | Harness exit 1, `provider_failure`, **timed_out=false**; work phase FAILED/root quarantine. Owned cleanup passes. Read-only postflight sees original A100 healthy/idle and closes its forward. Remote cancellation latency was not measured |

## Exact stop cause and remaining limitations

The attempt ceiling remained 720 s. Baseline/admission left 714.625 s and the
existing 20-second verification reserve yielded 694.625 s for the harness. It
stopped after 663.468 s, **before this deadline**, with 49 MCP operations and 19
model-request slots still available. It did not exhaust the attempt, context,
operation or request budgets.

`ProviderGate` separately caps cumulative captured incoming requests, rewritten
requests and streamed responses at **16777216 bytes (16 MiB)**. During request 45,
the counter reached **16777435**, triggering the existing `provider evidence budget
exhausted` guard. The upstream had returned HTTP 200. The proxy cut the stream,
and OpenCode reported `OpenAI Chat stream ended without finish_reason`, normalized
as `provider_failure`. This is a **local controller evidence-budget failure**,
not an A100-reported model/server error. The available archived provider bytes total
16777066; the final 369-byte counted chunk is not archived because the check raises
before writing it. The rest of that response/usage is unknown, not reconstructed.
Forty-four responses are complete and one is partial.

There are also reproducible worker test-quality limitations in the saved checks:
zero-age tests expect expiry despite the frozen requirement accepting equality;
several expiry tests rely on `sleep(1.1)` despite integer timestamps and strict
greater-than expiry; two tests call `.encode()` on an already-bytes separator.
Different worker/controller pass counts reflect timing-sensitive tests. The model
did not resolve these failures, left docs unchanged and later emitted two
incomplete edit calls at the output ceiling. After compaction it performed repeated inspections without
an accepted correction. No operator repaired these tests or the implementation.

The editor successfully applied exact and location-grounded changes. The next
review concerns trace-budget compatibility/classification and autonomous test
diagnosis/workflow. **No further editor-repair cycle, cap change, new preparation
or live trial was started.** Passing the finite public suite does not establish
independent acceptance or complete the feature contract.

## Preserved evidence and stop point

[Evidence and outcome receipts](evidence/a100-editor-trial-result/) retain the
approval, preflight, all available incoming/forwarded requests and response streams,
agent/MCP traces, failed proposals, source inspections, hash receipts, model-authored
exported files, unaccepted patch, controller checks, timing and cleanup. The
quarantined local bundle retains **911 indexed files**, runtime homes/database and
its test-owned staged workspace. Private server logs/runtime credentials are not
published. No grading material exists.

All **2872 historical indexed entries** and the 140 original approved bundle files
remain unchanged. Main remains `cf50e89`. The unchanged implementation's **207/207
preparation regression receipt** remains historical; no additional platform
regression or engineering campaign was run after quarantine. The existing offline
verifier and remote service/model/storage configuration were preserved.

Do not execute `run` or `grade` again for this bundle. No replacement digest or
trial is prepared. Stop here for operator review.
