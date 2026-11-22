# Milestone E: single-system task-contract correction

## Changed files

- `aiwork/execution_context.py`: merge the complete authoritative contract before
  the original initial system instructions in one message. Preserve original
  text/metadata and all other messages/settings unchanged. Insert an initial system
  message when absent. Support strings and plain text-part arrays; reject multiple
  or late system messages, nontext/ambiguous system content and unsupported roles
  before changing context accounting. No instruction truncation or fuzzy merging.
- `aiwork/provider_gate.py`: retain the fail-closed latch, set it before exposing
  upstream errors to the SDK, and identify blocked follow-ups as
  `controller_failure_latched`. Record `retry_of` for identical resends instead of
  incorrectly presenting a latched failure as missing tools.
- `tests/test_system_contract.py`, `tests/test_provider_gate.py`, and
  `tests/test_context_compaction.py`: captured-request, pinned-template, instruction
  preservation, malformed-layout, compaction, cumulative-budget and resend tests.
- This report, current handoff/status/README, and
  `docs/evidence/a100-system-contract-fix/`: verification and fresh preparation.

No harness architecture, task assets, permissions, router, inference server or
model files changed. The consumed trial was not modified or reused.

## Exact verification

| Verification | Result |
| --- | --- |
| Before changes | **182/182** regressions pass, no skips, 156.579 s; deterministic direct fixture VERIFIED |
| Focused system/installed OpenCode tests | **7/7** pass, 6.358 s; fake providers only |
| Focused provider-gate tests | **8/8** pass, 5.368 s |
| Complete expanded suite | **190/190** pass, no skips, 150.223 s; installed inert OpenCode/Pi and existing offline Docker images |
| Exact-byte pinned-template follow-up | **1/1** pass, 0.939 s after making the Windows fixture write byte-exact UTF-8 |
| Pinned full-template vectors | The exact old forwarded request reproduces the expected exception; **7/7 corrected** initial, two compaction, two resumed, absent-system and text-part requests render successfully |
| Actual OpenCode forced compactions | Two compactions, source recovery, one exact fixture edit and a passing public check; every forwarded request has one initial system message and retains the objective |
| Retry reproduction | Installed OpenCode attempts one resend after the fake HTTP 500; **one** request reaches the fake provider, the second is blocked with `failure_latched`, `retry_of=1`; cleanup passes |
| Changed-body follow-up | Also blocked after failure, without incorrectly labeling it an identical resend; model/tool budgets are not reset or charged as forwarded retries |
| Fresh frozen baseline | **3/12 public**, syntax passes, **297/297 upstream**, no skips; missing new annotations/authored tests remain expected baseline failures |
| Preservation | All **326 consumed-trial files** retain their hashes and quarantine markers; historical evidence indexes and main checked separately |

The complete captured request (SHA-256
`423a6b512390534936a3c95a625a3bf2b5ba4ee11e53046a552621adb08decff`)
is used directly. Tests assert no input mutation, no instruction truncation,
unchanged user/tool messages, tool declarations and generation settings. Fourteen
malformed layouts fail before ledger mutation. Contract scope/checks persist
through repeated maintenance and resumed requests with cumulative budgets intact.

The existing offline image
`sha256:fc1854e6885153904be89d67c701cd012fd68e57523566405d184ce2a4fe05e1`
already contained Jinja2 3.1.6/MarkupSafe 3.0.4. No dependency/model download or
image modification was needed. The full pinned template was rendered in its
sandboxed Jinja environment with no model tokens. This is deterministic/inert
validation, **not a live llama.cpp inference result**. Synthetic provider usage
in the harness tests is not real model consumption.

Evidence: [receipts and preserved traces](evidence/a100-system-contract-fix/).
The original failure remains in [its immutable outcome evidence](evidence/milestone-e-a100-result/).

## Fresh authorization preparation

Status: **PREPARED_NOT_AUTHORIZED**. Bundle:
`.aiwork/a100-system-repair/itsdangerous-trial`.

New approval digest:
`0534cc79d14abfe300f187b5ebf7a4728d89106558a925f16cce3d75fa214644`

Authorize exactly `["a100-existing"]` only after separate approval. The
[manifest](evidence/a100-system-contract-fix/prepared/manifest.json) binds the
corrected controller and unchanged task assets, model, OpenCode binary, verification
image, source inventories and resource protocol. The consumed
`150b82b49ebf8235fb0482d70bbcb75d3e3e1556334dd44406f5af3d69fab4af`
grant was explicitly rejected against this new bundle.

Unchanged: A100 Qwen3.6 35B-A3B Q6_K, 65536 harness context, 4096 output ceiling,
reasoning disabled, one 720-second attempt, 96 operations with eight edit/eight
public-test reservations, 64 model requests/four compactions, 20/900/120 phase
reservations, all three permitted paths, 12 public cases and 24 fresh post-freeze
independent acceptance cases. Current read-only endpoint identity/template/131K
slot matched the original pinned identity and was idle; the inspection forward
was closed. Remote service/model/storage configuration was not changed.

```powershell
# Validation only; no worker or inference is dispatched.
.\.venv\Scripts\python.exe examples/milestone-e-a100/trial.py validate .aiwork/a100-system-repair/itsdangerous-trial
```

No worker state, execution marker, real approval file or sealed inputs exist in
the fresh bundle. No live model inference or new engineering trial ran in this
session. The old quarantined trial remains consumed. Other historical comparison
manifests were not changed, refreshed or executed.

## Remaining blockers

No deterministic blocker remains for the captured message layout. Actual A100
inference and autonomous feature completion remain **UNTESTED pending approval**
of the new digest. Unsupported system layouts intentionally fail closed. The SDK
can still attempt a local resend; the verified controller boundary prevents it
from reaching a failed upstream session and records it accurately.
