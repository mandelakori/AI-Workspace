# A100 ledger reconstruction trial result

**FAIL — no candidate produced.** The single approved clean-start OpenCode
worker inspected the ledger evidence, applied zero edits and ran zero public
checks. The pinned reference again matched **18/18** public observations before
dispatch. Candidate compilation and behavioral correctness are **ungraded**.
The absent-source baseline records zero passes and zero executions. The
engineering phase failed, so there was no freeze, private case authoring or
independent grade.

The approval from `43eb3c8` was consumed for exactly `["a100-existing"]`.
Digest `8698eb97b2f06104dca2c14003848a30e664b03723e4c87777f638d94315510a`.
Bundle `.aiwork/native-workbench-validation/a100-ledger`, job
`dcb91076c1f844c99ba724a316e3f273`. All four worker input files, the reference
ELF, public corpus, controller and launcher hashes, OpenCode binary, 298 private
stimulus exclusions, permissions and limits matched the preparation. The
installed offline Docker image and GCC were available. Read-only preflight and
warm-up matched the approved Qwen3.6 35B-A3B Q6_K identity and idle 131,072-token
slot. The provider gate saw the exact four scoped tools before forwarding every
request. The controller retained `candidate.c` as the only writable path.

| Measurement | Observed |
| --- | --- |
| Worker and phase | OpenCode `completed`, exit 0. The controller rejected the unchanged workspace. Work `FAILED`, exit 1, no trial timeout. |
| MCP operations | **10/96**: nine focus, one diff, zero edit and zero check. Three focus errors, all on the absent `candidate.c`. |
| Inference requests | **7/64**; all HTTP 200, complete streams, 7 usage receipts. First six stopped for tools. Request seven stopped at `length`, exactly **4,096** completion tokens, with no tool call. |
| Provider token usage | **70,242 prompt + 4,571 completion = 74,813 total**. Zero cache hits reported. The SDK totals cover the six tool-calling steps and omit the final length-limited step. |
| Context | **0/4** compactions, epoch 0, peak prompt **12,828/65,536** tokens. All seven requests retained one initial system message and the full approved contract and generation settings. |
| Evidence capture | **1,839,763 bytes**, 21 complete provider files, all hashes verified, within 64 MiB and 32 MiB headroom policy. |
| GPU snapshots | A100-SXM4-40GB, 10,144 MiB free before and after. Peak GPU memory was not sampled. |
| Elapsed | Warm **5.500 s**, worker **66.281 s**, work **72.344 s**, total **78.086 s**. Provider requests accounted for **61.406 s**, of which the final request used **34.781 s**. |
| Cleanup and final status | Owned cleanup passed. No quarantine flag was set. The work phase is failed and consumed, grading remains pending behind the freeze guard. Postflight found the same endpoint idle and closed its owned SSH forward. |

The clean-start file was deliberately absent. On operations 1, 8 and 10,
`checks_focus` returned a size-related generic error for that absent path.
`checks_diff` confirmed an unchanged tree. The worker explicitly considered
the editor's `create` mode, then continued interpreting `sscanf` and operand
handling in prose until it hit the per-response output ceiling. The final
provider stream ended normally with `finish_reason=length` and `[DONE]`. No
provider, tool-count, request-count, context-window, evidence-capture or elapsed
deadline failure occurred. No create request reached the editor, so the trial
does not test live native edit application or candidate compilation.

The launcher emitted a secondary `FileNotFoundError` while loading a checkpoint
receipt the controller had never generated. The controller's earlier receipt
identifies the actual failure as an unchanged proposal. The wrapper still
failed closed and left no qualified or frozen artifact. The missing-file
diagnostic and wrapper error reduce clarity. Neither explains away the worker's
failure to issue an edit. This run demonstrates static exploration, with the
transition to a bounded source edit and verification still unresolved for this
clean-start ledger task. Earlier stride, classifier and ledger replays retain
their respective finite-test evidence.

The report and archive preserve every captured provider body, stream, tool
receipt and failure. Runtime homes and private server logs remain local and
are covered by the local inventory. Historical evidence, `main` and the exact
trial implementation are unchanged. No retry, model or harness change, guidance,
or further campaign followed. The preceding 58 targeted tests retain their
preparation status. No new implementation tests were needed for this evidence
commit.

[Trial evidence](evidence/native-ledger-a100-result/README.md) ·
[Native workbench validation](NATIVE-WORKBENCH-VALIDATION.md)
