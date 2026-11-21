# Next AI Workspace development plan

**PROPOSED — REVIEW REQUIRED. NOT AUTHORIZED FOR IMPLEMENTATION OR EXECUTION.**
Phase 6.1 benchmarking is closed. This document creates no runnable manifest,
new branch, model request, remote operation or implementation permission.

## Objective and evidence

Make one local engineering worker able to retain its objective, use precise
source evidence and finish a bounded edit/test cycle through interchangeable
harnesses. Demonstrate this before adding agents or increasing task complexity.
Unassisted unfamiliar-repository feature completion remains unverified.

The [closed comparison](DISCOVERY-EXPERIMENT-RESULT.md) provides concrete priorities:

- Required tool registration now works in the actual provider-facing catalog.
- A 5,086-token initial prompt left limited space in an 8K configuration. Two
  automatic compactions removed source while the controller's duplicate cache
  still suppressed its retrieval. Configured task instructions were not visible
  as the full task in the provider system message.
- All sixteen MCP slots went to inspection/diff. Twelve further attempts were
  refused, yet inference continued to timeout. No edit or worker test executed.
- Two summarizer calls consumed 14,099 logical tokens including cache/output,
  omitted from the harness's normal step-finish totals.

These observations justify context and resource-contract repairs. They do not
prove that a larger model, more context, another harness or hierarchy will succeed.

## 1. Establish a portable, enforceable harness contract

Extend the existing `Harness` protocol and adapters only where the evidence needs
it. Keep task intake, model endpoints, global routing, permission authority,
verification and candidate selection in the deterministic controller.

Start with installed OpenCode **2.0.27** as the instrumented baseline. Audit the
installed Qwen Code **0.27.4** adapter as the second candidate; do not assume parity.
Its current configuration permits native edits and exposes check/diff, whereas
OpenCode engineering uses scoped hash-checked edits. It also declares different
turn/retry settings. These are explicit compatibility gaps, not interchangeable
execution today.

Proposed minimum adapter contract:

- Declare supported inspection, hash editing, public checks, context events,
  usage reporting, cancellation and artifact export; reject unsupported tasks.
- Map logical tools to actual provider-facing names/schemas through a reviewed
  adapter policy. Capture the offered catalog before inference. Do not silently
  rename tools, add permissions or fall back to native mutation.
- Route mutations through the existing exact-anchor/current-hash editor, or fail
  conformance. Preserve isolated workspaces, approved command indices and offline
  verification. No fuzzy edit mode or operator-written implementation patches.
- Separate worker attempts, API transport retries, summary requests and ordinary
  model steps. Bound and record each under the approved overall budget.
- Normalize completion, clean budget exhaustion, provider failure, interruption,
  scope failure and quarantine. A zero launcher exit must not mask failed work.

First deliverable after review: one shared conformance suite and two explicitly
graded adapter capability receipts. Keep unsupported features BLOCKED rather
than weakening the task contract. No new agent framework, proprietary model API
or Codex CLI dependency is proposed.

## 2. Make context and retrieval share a state model

Implement a small context ledger, not a general memory architecture. Track the
trusted active objective, approved tools and remaining resources separately from
untrusted source, observations and model-authored summaries.

For each delivered source excerpt, record path, exact file hash, line span,
provider request and context epoch. After compaction or another observed eviction,
mark verbatim evidence unavailable unless it is demonstrably retained. Permit
bounded reinspection of that unchanged version; do not replenish tool quotas.
Keep cached source artifacts and hashes on the controller so source integrity
does not depend on a model remembering code exactly.

Diagnose why the configured instruction file did not appear as task-specific
provider system text. Verify the chosen replacement through captured requests,
including after two forced context resets. Preserve all required behavior and
write scopes; a summary is not authority to drop requirements or grant tools.

Reduce repeated response framing before raising context limits. Use compact
source receipts, requested function windows and optional outlines. Avoid repeating
large objective/metadata blocks in every tool response once a trusted objective
is actually maintained. A suppression response must distinguish evidence still
visible to the worker from evidence that was merely supplied historically.

Acceptance: deterministic/inert tests force two compactions, preserve the objective
and permissions, evict source, reacquire it once, reject stale hashes and complete
an exact edit/public-check sequence. Test source changes, reconnects, overlapping
windows and absent compaction events. Opaque adapters must use a conservative
policy and report their visibility limitation.

## 3. Make resource allocation terminate usefully

Keep hard deadlines and quotas authoritative. The controller should stop
forwarding implementation generations when no usable tool budget remains and
return a deterministic partial/blocked receipt. Any final model call needs its
own explicit reviewed allowance. Interruption or unknown cleanup still quarantines;
clean budget exhaustion is a distinct terminal state under a newly reviewed policy.
Do not retroactively reclassify the completed Phase 6.1 quarantine.

Proposed resource policy should:

- Reserve operations and wall time for at least one edit recovery and public
  verification; prevent unlimited read/diff allocation from consuming them.
- Account for preparation, routing, startup, primary inference, compaction,
  tools, verification and cleanup using one absolute budget. Different harness
  defaults must not create hidden retries or uncharged inference.
- Use raw cache-inclusive prompt counts and report uncached/cache/output fields
  separately. Count auxiliary model calls, unfinished calls and unknown usage.
- Estimate verification reserves from the frozen baseline: this target's whole
  upstream check took about twenty seconds before public/authored checks. Reuse
  evidence only when source, corpus and verifier identities match.
- Use empirical residency, effective context, VRAM headroom, prefill latency and
  tool costs in deterministic admission/routing. Explain blocked configurations
  rather than silently increasing context, changing models, starting services or
  routing to cloud.

Keep the existing local 9B/8K profile for initial contract validation. Any larger
context, different worker or remote measurement is a separate reviewed proposal,
supported by observed capacity and an explicit budget. No agent may authorize it.

## 4. Validate a vertical slice before another real-repository trial

Proposed review gates, in order:

| Gate | Required evidence |
| --- | --- |
| Adapter safety | Both adapters pass catalog, scope, exact-edit, deadline and owned-cleanup conformance with inert providers; unsupported capabilities fail closed. |
| Context correctness | Two forced context changes retain the active contract, allow reacquisition of evicted source and preserve hashes without resetting quotas. |
| Progress control | At zero usable operations, no further implementation request reaches the provider; clean partial and interrupted/quarantined receipts differ. |
| Measured local smoke | Only after execution approval: a small agent-authored inspect/edit/test task with rejection recovery. A fixture result is not unfamiliar-repository completion. |
| Real engineering | Only after a new task/protocol review and separate execution approval: a fresh real-repository feature, frozen baseline/public cases, no mid-run implementation guidance and fresh sealed inputs after candidate freeze. |

Keep all current regressions and add tests for the identified boundaries. Run
Windows and Linux infrastructure checks where supported; Windows measured-job
ownership remains explicit until other platforms have equivalent evidence.
Do not resume a historical trial, reuse sealed feedback or run another Phase 6.1
campaign to validate these changes.

Record source delivery, correctness, regressions, first edit/test operations,
failed edits, context resets, source availability, API calls by role, tokens/cache,
tool allocation, elapsed time, human intervention and cleanup. Predeclare matched
conditions for any later comparison. Use repeated independent trials only when
their budget is separately approved; one pair supports descriptive results only.

## Review scope and handoff

The recommended first implementation review covers **objective propagation,
context-epoch retrieval and terminal budget handling**, with a reusable contract
that can then be applied to Qwen Code. Do not begin by adding roles, autonomous
decomposition, more models or an orchestration service.

Before work starts, approve the exact adapter versions, tool mappings, source
paths, command recipes, cancellation policy and deterministic test scope. Live
model tests need separate explicit authorization naming model/context, request
and output ceilings, resource reservations and stopping conditions. Remote/cloud
operations, new models, service restarts, deployment and merges remain excluded
unless separately approved.

Expected reviewable deliverables are small implementation patches, conformance
receipts, context/resource event traces and an operator CLI/PowerShell workflow
for checking state and retrieving verified artifacts. Preserve the existing
layers and local operation after Codex access ends. **This plan is not an approval
manifest and authorizes no implementation or execution.**
