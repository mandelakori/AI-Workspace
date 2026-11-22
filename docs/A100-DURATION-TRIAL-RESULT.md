# Milestone E ItsDangerous trial: inference succeeded, editing failed

**FAIL — no accepted source edits; deadline interruption and quarantine.** The
single approved trial from `84933e1`, digest
`0534cc79d14abfe300f187b5ebf7a4728d89106558a925f16cce3d75fa214644`,
ran once using the frozen bundle, OpenCode and existing A100 Qwen3.6 35B-A3B Q6_K.
The previous system-message incompatibility is resolved in live requests, including
compaction and resumed inference. Autonomous feature completion was not achieved.

No retry, fallback, operator implementation guidance, source correction, service
change or subsequent development was performed. This authorization is consumed.
No candidate was frozen, so the 24 sealed cases were **not created or graded**.

## Actual results

| Requested measurement | Observed result |
| --- | --- |
| First A100 request | **Succeeded**, HTTP 200; 5421 prompt +114 completion =5535 tokens; initiated a valid source-inspection tool call |
| Requests | **51 forwarded**, all received HTTP 200 headers; **50 complete usage receipts**, final request interrupted at the deadline. No SDK resend observed |
| Contract | All 51 requests have exactly one initial system message containing the authoritative contract and original system instructions; other messages, tools and generation settings are preserved |
| Settings | 65536 harness context, 4096 output ceiling, temperature 0, seed 1729, reasoning disabled; all forwarded bodies contain the frozen settings |
| Edits | **37 model-authored proposals; 0 accepted edits**; no authored test or documentation change |
| MCP operations | **51/96**: 12 focus, 1 diff, 37 edit, 1 check; no operation/model budget reset |
| Worker tests | **One syntax check**, index 4, passed on unchanged source. **Zero feature-public, upstream, authored-test or interface-check executions by the worker** |
| Public correctness | Controller baseline check executed **3/12**. All source hashes remain identical, so no improved candidate exists; no new candidate grade is claimed |
| Upstream | Frozen preparation baseline **297/297**, no skips; not rerun by the worker or after quarantine |
| Independent acceptance | **Not permitted / not graded**, not 0/24; no candidate freeze or sealed inputs |
| Reported tokens | Across 50 complete calls: **1474386 prompt +13273 completion =1487659 total**. The final request has no usage receipt, so these are incomplete totals |
| Cache / reasoning usage | API reports zero cached prompt tokens across completed calls; no reasoning-token counter. Do not infer uncached engine behavior or an internal reasoning-token total |
| Context events | **One successful compaction**, request 47; requests 48–50 then completed resumed inference. Epoch 1; peak reported prompt 50643/65536 tokens, including compaction |
| Source recovery | Eleven source-bearing focus results, including post-compaction reinspection; persistent objective retained. Source was available, not silently lost |
| Termination | Harness `interrupted`, exit 1, `timed_out=true`; outer work process exited 1 before its 900-second phase ceiling. Root and ledger quarantine recorded |
| Timing | Warm **4.844 s**; work **703.047 s**; work cleanup **6.093 s**; total start-to-quarantine closure **714.012 s** |
| Cleanup | Local owned process/container cleanup passed, controlled PIDs absent, forward listener closed. Read-only postflight found the existing A100 healthy and idle |

The configured attempt remained 720 seconds. Admission/baseline work left
714.094 seconds; the controller retained its approved 20-second verification
reservation, yielding **694.094 seconds** for the harness. Recorded harness time
was 693.781 seconds. The final in-flight call was interrupted at this deadline;
the attempt was not extended. Forty-five MCP operations and thirteen model-request
slots remained unused. This was not a tool-count, context-capacity or evidence-size
exhaustion. Exact remote cancellation latency was not measured; the later idle
postflight check does not establish it.

## Saved-trace diagnosis

All 37 proposed argument objects extracted from the raw provider streams equal
the actual MCP edit arguments. Every supplied source hash was current. This rules
out transport double-escaping or stale-hash corruption for these attempts.

The unchanged source file contains **228 CRLF line endings**. Focus returned those
line endings intact. The editor deliberately requires byte-exact anchors.

| Rejection | Count | Evidence |
| --- | ---: | --- |
| `anchor_mismatch` | 12 | Eleven multiline anchors contain LF rather than CRLF. Each matches exactly once only after CRLF re-encoding in a **read-only comparison**. The remaining single-line anchor does not occur |
| `ambiguous_anchor` | 24 | Twenty-three anchors match five locations; one matches seven. Selecting one would violate the frozen unambiguous-anchor rule |
| `invalid_anchor` | 1 | Empty anchor for an existing-file insertion |

The model attempted 15 replacements and 22 `before` insertions. It repeatedly
shortened anchors into ambiguous type fragments rather than recovering a valid
unique byte match. Diagnostics supplied exact-match counts, source hashes and
suggested focus regions; the worker nevertheless repeated rejected edits. No
operator converted an anchor, inserted code, weakened matching or repaired the
candidate. The CRLF comparison is diagnostic only, not an applied correction or
a claim that the proposed implementations would pass.

The measured blocker is **reliable source-grounded edit application across line
endings and recovery from ambiguous anchors**. It is distinct from the previous
provider-template failure, which did not recur. This trial does not establish
whether the feature algorithm would be correct after successful edit application,
nor isolate model capability from the strict editing contract. It provides no
basis for a harness-superiority claim.

## Preserved outcome

[Raw evidence and receipts](evidence/a100-duration-trial-result/) retain the exact
approval, preflight catalog/dependencies, all 51 incoming/forwarded request bodies,
raw responses including the interrupted stream, complete agent/MCP traces, proposed
edits, context ledger, timing/cleanup receipts, and read-only anchor analysis.
Runtime homes/private logs and retained stages remain at their owned local paths;
credentials and model bytes are not committed.

Independent hash checks confirm the worker workspace equals the 45-file approved
input, the original/pristine source is unchanged, no freeze/private directory
exists, and the grading guard rejects the quarantined state. Historical results,
the old quarantined trial, main, model/storage/service configuration and the
unauthorized Pi/OpenCode comparison are preserved.

No platform, harness, task or target implementation changed. The correction's
190-pass regression receipt remains historical; no full regression or additional
engineering campaign was run during this evidence-only execution. No new trial
or authorization manifest was prepared. **Do not resume this consumed trial.**
