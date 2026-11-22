# Offline historical evaluation and unauthorized preparation evidence

`historical-evaluation/` retains both distinct model-authored replay sources,
their inventories and every frozen public/upstream/interface/authored/syntax
receipt. They are unpromoted historical proposals, not solutions supplied to a
worker. Source is covered by the preserved
[ItsDangerous BSD license](../milestone-e-a100/ITS-DANGEROUS-LICENSE.txt).

`prepared/` is a byte-exact copy of the fresh manifest, digest and false approval
example from `.aiwork/a100-editor-recovery/itsdangerous-trial`. Frozen source and
baseline workspaces remain there. `endpoint.json` records a read-only inventory,
zero generation requests and closed owned forward. `catalog/` captures the actual
scoped tool schema without a model session; its state is separate from the bundle.
`inert-conformance/` contains installed OpenCode's synthetic-provider edit/recovery
and exhaustion traces, cleanup and resource receipts. It is not model inference.

`regressions.log` records 207 passing tests, zero skips. `verification.json` and
`preparation-verification.json` bind the results and original clean starting
inventories. `preservation.json` audits historical indexes and main. The evidence
hash index covers every file here except itself.

Reproduce validation with `examples/milestone-e-a100/trial.py validate` and the
bundle above. Historical evaluation used that unchanged script's `evaluate`
function: snapshot the original frozen `input`, overwrite only
`src/itsdangerous/timed.py` with the corresponding preserved replay source, then
run `evaluate` into a fresh output directory. It executes the same five frozen
offline Docker checks and never calls inference. Do not copy evaluation outputs
or historical sources into the live trial input or future worker context.
