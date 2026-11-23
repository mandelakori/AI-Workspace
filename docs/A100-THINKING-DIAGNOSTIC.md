# A100 thinking-mode diagnostic

**PREPARED_NOT_AUTHORIZED.** The installed Qwen3.6 template and llama.cpp server
accept both explicit thinking modes. The paired diagnostic uses the existing
byte-stride fixture. Each arm must inspect evidence, edit a small C starter and
run the same public check. The consumed ledger trial remains closed.

| Arm | Provider request switch | Separate approval digest |
| --- | --- | --- |
| OFF | `chat_template_kwargs.enable_thinking: false` | `d463872c20fd451f06f088b7f69f287c1799b532f692318beac2b0d59687aa54` |
| ON | `chat_template_kwargs.enable_thinking: true` | `919170e98baabcf70c597c3c1f052dcae64cb55ed82e02ed53d5a88956498c92` |

Omit `reasoning_effort` from both arms. The active template advertises no effort
levels. The pinned parser explicitly recognizes the Boolean and also treats
`reasoning_effort="none"` as a disable directive. Set the optional
`enable_thinking` field on a llama.cpp profile to emit the Boolean as a template
kwarg. An unset field preserves existing serialization, including the legacy
OFF setting. The schema rejects unsupported engines, non-Booleans and ON with
`reasoning_effort="none"`. [Pinned llama.cpp request parser](https://github.com/ggml-org/llama.cpp/blob/2cbca389f/tools/server/server-common.cpp#L1372-L1414)

## Deterministic verification

Over an owned SSH forward, the existing server `b12063-2cbca389f` returned the
original model path and Q6_K format, the exact template SHA-256
`e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259`, and one idle
131,072-token slot. Four `/apply-template` calls rendered initial and continued
tool histories. OFF rendered an empty closed `<think>` block and ON left an
open `<think>` block for generation. The tool schemas and tool continuation
survived both modes. This route shares chat parsing and returns the prompt
without inference. The owned forward closed. [Pinned render handler](https://github.com/ggml-org/llama.cpp/blob/2cbca389f/tools/server/server-context.cpp#L5795-L5808)
Offline Jinja2 3.1.6 repeated all four mode/history checks against the same
template bytes.

The running service command line showed no reasoning-budget or parser override.
The remote process environment and Docker metadata could not be inspected with
the existing account. Prompt-level activation is verified. Actual reasoning
emission, token accounting and model-generated tool calls will be assessed only
from the approved live stream. The deployed model identity is pinned by server
metadata and template hash. The weight file was not rehashed.

Installed inert OpenCode tests exercise both settings through the provider gate.
Each performs a source read, hash-validated edit and approved public check. ON
receives a synthetic reasoning delta followed by a tool call. The request
archive records both exact mode switches, and the usage receipt preserves a
synthetic reasoning-token counter for ON while leaving the absent OFF counter
unreported. These are transport checks with zero generated model tokens.
The full suite passed **235/235** in **228.633 s**, with zero skips, and the
direct baseline fixture passed. Two pre-change test invocations hit malformed
inherited Git environment configuration and passed on a child-only recheck.
The final suite used that isolated environment.

## Matched controls

- **Fixture.** Phase 4 self-authored byte-stride ELF
  `787a07f328a2a393e9b271bacb266b0ac6a76e474d34af3e3f66e67e9ff0ec12`.
  The reference replay passed **5/5**, and the common C starter compiled and
  scored **0/5**. No earlier model candidate seeds the trial. Each arm gets
  distinct copies of the same five files: the starter `candidate.c`, binary and
  Ghidra JSON, public examples, and native public check driver. Reference source,
  target executable and historical private data remain outside worker input.
- **Model and tools.** Same existing A100 Qwen3.6 35B-A3B Q6_K, OpenCode binary,
  authoritative task contract, pinned offline Docker, and scoped focus, diff,
  edit and check. Only `candidate.c` is writable. Commands 0 and 1 respectively
  compile and check the five observations, or compile only. The identity and
  idle context slot must match before each arm. The provider catalog gate must
  pass before forwarding. No service, model or harness switch.
- **Resources per arm.** 65,536 context, 4,096 output tokens, temperature 0,
  seed 1729. One attempt of at most **210 s**, **18 requests**, **24 MCP
  operations** with four edit and four check reservations, and one compaction.
  Warm/work/grade reservations **20/270/90 s**. Existing 64 MiB capture and
  32 MiB disk headroom. No planner, retries or implementation guidance.
- **Order and isolation.** Fixed OFF then ON. Both require their own grant and
  separate pristine workspaces, processes, logs and result records. Default
  cache behavior is identical. Record reported prompt cache usage and flag
  possible carryover or slot-load effects. A single pair is diagnostic evidence
  about this fixture and configuration.
- **Verification.** Require an applied edit, passing worker public check 0,
  independently compiled 5/5 public result, and clean worker and phase closure
  before freezing an arm. An ordinary unsuccessful arm can close without a
  freeze. Stop the pair on a safety failure. Once both engineering arms close
  safely, author **12** new private cases applicable to every frozen candidate.
  Reject overlap with 53 known development and prior final stimuli. One sealed
  suite grades eligible arms through the existing differential verifier with
  exact stdout, stderr and exit comparison. Cases cannot be shared with the
  worker. An arm with no eligible candidate is ungraded.

## Measurements for the live comparison

| Measure | Evidence and interpretation |
| --- | --- |
| Activation | Check each forwarded body for the frozen Boolean and absence of conflicting effort. Record nonempty `reasoning_content` or generated inline thinking delimiters separately from the rendered prefill. |
| First edit and test | Use OpenCode tool event timestamps relative to arm and worker start. Join tool-call IDs to provider request indices and MCP ordinals. Report the first applied edit and first attempted and successful public check separately. Leave missing milestones unobserved. |
| Tool use and correctness | Count inspection, accepted/rejected edits with rejection reasons, compile and public check calls. Report controller public score and sealed score only for actual executions. Retain unchanged and failed proposals. |
| Usage | Sum provider-reported prompt, completion and cache tokens. Record the number of usage receipts covering each counter. Sum reasoning tokens only where the provider reports `completion_tokens_details.reasoning_tokens`; distinguish explicit zero, partial reporting and unreported values. |
| Limits and failure | Record model requests, compactions, peak prompt, wall time, captured bytes, stream finish reasons including `length`, harness/controller status and owned cleanup. Distinguish model output limits, scope or provider failures, and a clean unchanged proposal. |

## Approval and reproducibility

Bundle `.aiwork/a100-thinking-diagnostic/pair`. Only the Boolean differs in the
normalized mode configurations. Separate proofs reject cross-arm approvals,
changed starting bytes and early grading. Neither arm has a grant, run marker,
worker state or private cases.

```powershell
$thinkingPy = '.venv/Scripts/python.exe'
$thinkingPair = '.aiwork/a100-thinking-diagnostic/pair'
& $thinkingPy examples/native/thinking_trial.py validate $thinkingPair
# After exact separate approval for the OFF arm.
& $thinkingPy examples/native/thinking_trial.py run $thinkingPair off --approval '<off-grant.json>'
# After OFF closes safely and exact separate approval for the ON arm.
& $thinkingPy examples/native/thinking_trial.py run $thinkingPair on --approval '<on-grant.json>'
# Only after both engineering arms close safely and the common private suite exists.
& $thinkingPy examples/native/thinking_trial.py grade $thinkingPair '<eligible-arm>' --approval '<arm-grant.json>'
```

Each JSON grant binds its own `approval_digest`, `authorize` array (`["off"]`
or `["on"]`) and `operator_approved: true`. The bundle and script preserve the
per-arm consumed marker and existing fail-closed watchdog. If re-preparing in
a fresh directory, use `prepare <new-pair> --archive
.aiwork/phase4/native/316b157df27c459e93b5b171bc1df38d --template
.aiwork/a100-thinking-diagnostic/template-probe --config config/self.local.toml`.
Any changed material requires new review. No live trial has been launched.

[Preparation and exact evidence](evidence/a100-thinking-diagnostic/README.md)
