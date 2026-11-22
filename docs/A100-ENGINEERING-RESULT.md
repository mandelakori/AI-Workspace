# Milestone E A100 trial: failed at the provider boundary

**FAIL — infrastructure incompatibility; QUARANTINED.** The approved trial from
`de38d35` ran once under digest
`150b82b49ebf8235fb0482d70bbcb75d3e3e1556334dd44406f5af3d69fab4af`.
No model completion, source edit, authored test or worker public-test call occurred.
There is no candidate to grade and no model coding-capability verdict.

The trial was not restarted or resumed. No fresh sealed cases were authored,
because engineering did not close successfully. No repair, protocol change,
harness replacement, remote service change or additional campaign was performed.

## What happened

Preflight validated the approved manifest, all source/asset/controller hashes,
the pinned OpenCode executable and the existing offline Docker image. Installed
test dependencies matched: pytest 9.0.3, freezegun 1.5.5, python-dateutil 2.9.0.post0,
six 1.17.0. Read-only A100 checks matched the pinned Qwen3.6 35B-A3B Q6_K derivative,
llama.cpp build/template and one idle 131072-token slot. The 20-second readiness
phase finished successfully and closed its owned forwarding process.

The controller ran its frozen public baseline check (3/12), opened one worker
session, and verified that all four scoped MCP tools were connected and advertised.
The first forwarded request then received HTTP 500 from llama.cpp in 0.312 seconds:

> System message must be at the beginning.

The saved bodies and the exact active template identify the cause:

| Boundary | Message roles |
| --- | --- |
| OpenCode request | `[system, user]` |
| Controller-forwarded request | `[system, system, user]` |
| Active Qwen template | Rejects any system message when `not loop.first` (line 85) |

`ExecutionContext.provider_request` prepended the persistent task contract as a
new system message, ahead of OpenCode's existing system message. The second system
message deterministically violates the model template's guard. The original
messages are otherwise preserved verbatim; the failure is evidenced by their
hashes, the raw HTTP response and the pinned template, without another inference.

The required tool catalog **passed**. The later `required_tools_unavailable` 400
in the harness trace is a generic response from the already-failed provider gate,
not the original cause. OpenCode attempted an automatic resend after the 500; the
gate blocked it. Thus there were **two local provider POSTs, one A100 request**,
one controller worker/session/attempt and no forwarded retry. The attempted local
resend is retained as a compliance finding; no zero-retry claim is made about the
SDK itself.

## Measured outcome

| Item | Actual result |
| --- | --- |
| Source changes | **0**; all 45 worker-workspace hashes equal the approved input |
| Authored tests / worker public tests | **0 / 0** |
| Public behavior | Controller baseline **3/12** during the trial; no model candidate score |
| Upstream regression | **Not run by the worker**; the frozen preparation baseline was 297/297, no skips. Unchanged source is verified, not presented as a new upstream execution |
| Independent acceptance | **Not created / not graded**, not 0/24; no frozen candidate |
| Tools | **0/96** MCP operations: inspection 0, editing 0, verification 0; reserved eight edit/eight test slots untouched |
| Provider calls | One forwarded request failed HTTP 500; one local automatic resend blocked; no usage-bearing completion |
| Inference usage | Prompt/output/reasoning/cache token counts **unreported/unknown**; no generated text returned. No invented zero-token total or throughput |
| Request settings | Correct model; `max_completion_tokens=4096`, `reasoning_effort=none`, `chat_template_kwargs.enable_thinking=false`, temperature 0, seed 1729 |
| Context | Harness configured 65536; server slot 131072; epoch 0, compactions 0, no inspected/evicted source; prompt-token count unavailable |
| Harness exit | **1**, `provider_failure`; no timeout or scope violation |
| Readiness phase | **4.797 s**, successful |
| Engineering phase | **14.625 s** including process termination; container cleanup **0.218 s** |
| Harness / upstream error time | **4.985 s / 0.312 s** |
| Trial wall time | **19.675 s**, execution-start marker to failed engineering phase closure; excludes preflight and evidence preservation |
| Grading phase | **PENDING / unused**, 120-second reservation not consumed |

The nominal 720-second attempt had 713.407 seconds remaining at harness admission;
the controller retained 20 seconds for verification and offered the harness
693.407 seconds. This failure was unrelated to time, context or tool exhaustion.

Cleanup passed for the private OpenCode server and owned execution/container jobs.
Independent local checks found the recorded readiness-forward PID and private
server PID absent, port 18881 closed, all original/input/worker source hashes
unchanged, and no frozen/sealed artifacts. A100 telemetry recorded 10144 MiB free
before and after the harness. No unrelated process or remote service was stopped.

The root `quarantine.json` is authoritative and `execution-started.json` consumes
the one-shot authorization. The phase ledger records work `FAILED`; its separate
`quarantined` field is false because it tracks timeout/cleanup failures, which did
not occur. These original records are preserved without rewriting them. The
consumed/root-quarantined trial cannot resume or grade through the entrypoint.

## Evidence and remaining blocker

[Outcome and raw evidence](evidence/milestone-e-a100-result/) include the exact
approval, manifest, readiness/phase receipts, both provider requests, forwarded
body, HTTP 500 response, complete agent traces, resource ledger, unchanged-source
and process checks. Runtime homes/private logs and retained stages remain at their
owned local paths, with a local evidence inventory; credentials/runtime homes are
not published. Historical evidence indexes, frozen Click, `main`, the original
models and the unauthorized Pi/OpenCode comparison remain unchanged.

No controller/harness/target implementation changed. The prior preparation's
182 passing regressions remain the latest full suite; this execution performed
dependency/readiness, controller public-baseline and post-run hash/process checks,
not an additional engineering or regression campaign.

**Remaining blocker:** preserve the authoritative persistent contract while
producing a message layout accepted by the strict active Qwen template. A minimal
single-system-message compatibility change, plus inert template and retry-policy
conformance, needs separate review before a fresh approval-bound trial. It was
not implemented or prepared here. This result does not justify replacing OpenCode
or declaring the A100 model incapable of the ItsDangerous feature.
