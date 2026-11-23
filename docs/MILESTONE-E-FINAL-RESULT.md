# Milestone E final acceptance: partial progress, deadline quarantine

**FAIL — autonomous coding progressed, but Milestone E acceptance remains unmet.**
The one approved trial from `389d192` executed once on 2026-11-23 using OpenCode
and the existing A100 Qwen3.6 35B-A3B Q6_K. Its original public score improved from
3/12 to 12/12, the expanded score from 22/48 to 48/48, and upstream regressions
passed 297/297. The worker did not finish correct authored tests or the mandatory
acceptance workflow before its deadline. The trial is quarantined and unpromoted.

Consumed approval:
`b6d7338aad1fa82343277ab37ac7c4afb946ec4da7353a6040e3abda977a71f6`.
Bundle: `.aiwork/milestone-e-final/acceptance-trial`.
Job: `fe27597006e842629a39c8680c45dc3d`, exactly one attempt.
No retry, fallback, implementation guidance, manual source correction, service
change or subsequent campaign occurred. No frozen candidate exists, so **the 24
sealed cases were not created or graded**. Independent correctness is untested,
not 0/24. No new ItsDangerous trial is prepared.

## Acceptance evidence

| Requirement | Observed result |
| --- | --- |
| Original public behavior | **12/12**, baseline 3/12; worker operations 25 and 42 |
| Expanded public behavior | Initially **44/48** at operation 26; autonomously repaired four integer precision/overflow failures, then **48/48** at operation 29; baseline 22/48 |
| Relevant upstream regressions | **297/297**, no skips, at operation 30; pytest reports 2.61 s |
| Regressions | Zero lost public passes; upstream suite remains green for the tested production source |
| Authored tests | Gate **failed** at operation 50 under two controlled UTC clocks; the retained second-run receipt shows **5 passed /10 failed**. Two subsequent test edits were accepted but never reverified. No final authored score is claimed |
| API/interfaces | Duration annotations/docstrings changed, but the interface gate was **not executed** |
| Documentation | `docs/timed.rst` updated with durations, fractions, equality, zero and negative limits; the documentation gate was **not executed** |
| Syntax | Python edits passed the scoped editor's syntax validation and the production module ran in public/upstream checks; separate syntax gate **not executed** |
| Acceptance / harness | No command-7 acceptance call; harness **interrupted**, exit 1, timed out. Successful engineering closure **failed** |
| Independent acceptance | **Not permitted / not graded**; quarantine guard rejects freeze/grading |

Production source did not change after operation 28. Exact hashes of its copies
at operations 29, 30, 42 and 50 equal the retained final production source hash.
The public and upstream results therefore remain evidence for those production
bytes. Later edits changed documentation and authored tests; they do not establish
a verified final integrated delivery. The controller stopped before final
candidate selection/verification because the worker failed clean closure.

All three permitted files changed, and no other input changed:

| File | Accepted edits | Final SHA-256 |
| --- | ---: | --- |
| `src/itsdangerous/timed.py` | 10 | `71df145085b3417aa167928273799477ac1a376f7dd8809f75e741cfe3ca9e4c` |
| `docs/timed.rst` | 1 | `e565bec618dd7e43caa5167d215c37d2063702818e1f8497edb364ec2d7d734e` |
| `tests/test_itsdangerous/test_timedelta_max_age.py` | 5 | `b7efda103598839832a45fa5b60a669cd14a9bfd9af3f3d082e2d460a7d239de` |

These are model-authored, **unaccepted** artifacts preserved with the patch in
[the evidence archive](evidence/milestone-e-final-result/README.md), not operator
fixes or starting solutions for another worker.

## Execution and resources

| Measurement | Recorded result |
| --- | --- |
| First inference | HTTP 200, usable tool call; 7,603 prompt +115 completion =7,718 tokens |
| First accepted edit | MCP operation **10**, **71.871 s** after trial start |
| First public execution | MCP operation **25**, **282.438 s** after trial start |
| MCP allocation | **53/96**: 23 focus, 23 edit, 6 check, 1 diff; 43 operations remain unused |
| Edits | **16 accepted /7 rejected**; 10 accepted newline adaptations, zero inspected-location edits |
| Rejections | Two `unsupported_newlines` (anchor splits a CRLF pair), five `edit_too_large` (1,200-byte anchor /3,000-byte new-text bounds); no scope bypass |
| Other tool failures | Two invalid/nonexistent-file inspections and two failed test checks; 11 error events total including the seven rejected edits |
| Provider requests | **47/64 forwarded**, all HTTP 200 headers; 46 ordinary inference calls and one compaction; 46 complete response/usage receipts, final response partial |
| API-reported usage | **1,240,366 prompt +20,618 completion =1,260,984 tokens** across 46 complete receipts; final request usage unknown |
| Cache / reasoning | API reports zero cached prompt tokens; no reasoning-token counter. SDK reasoning reports zero; no inference about internal token accounting |
| Context | One compaction, epoch 1; peak API-reported prompt **51,131/65,536** tokens. Resumed inference retains the contract |
| Capture | **15,588,689 bytes /141 files**; all byte counts and SHA-256 verified. Limit 67,108,864 bytes, required disk headroom 33,554,432 bytes; no exhaustion or unadmitted request |
| Timing | Warm **4.828 s**, work **705.343 s**, harness **693.016 s**, trial start to work closure **710.458 s** |
| Recorded execution categories | Inference 621.971 s, compaction 27.156 s, inspection 6.720 s, editing 6.438 s, verification 20.578 s; these are category receipts, not additive wall-time estimates |
| Cleanup | Owned cleanup passed. Read-only postflight: unchanged model/template/build identity, healthy endpoint, one idle context slot, owned forward closed; zero postflight generation requests |

The configured attempt remained 720 s. Baseline/admission left 713.313 s; the
approved internal 20 s verification reserve yielded a 693.313 s harness allowance.
The harness deadline interrupted request 47; the outer 900 s work ceiling was
not reached. Its remaining time cannot extend the separately approved attempt.
The 120 s grading reservation remains unused.

`provider-gate.json` records fail-closed cancellation and `TimeoutError` on the
last stream. `execution-receipt.json` accurately classifies the attempt as
`interrupted`, not evidence exhaustion. The controller's generic detail mentions
"cancellation/cleanup failure"; cleanup itself passed. Backend cancellation
latency was not measured; the later idle-slot check is not such a measurement.
No automatic resend or retry was observed. There is no evidence here of a new
provider, capture, model-loading or editor implementation defect.

All 47 forwarded bodies retain the approved model/settings, exactly one initial
system message, the complete controller contract and the original system
instructions, including compaction and subsequent requests. All four scoped
tools remain advertised. No tools, permissions or generation settings changed.

## Remaining limitation and milestone assessment

The worker repaired its own initial integer-to-float precision regression using
public diagnostics, preserved all public passes, added documentation, authored
15 tests and began repairing their clock setup. Those are genuine autonomous
implementation/debugging results without mid-run operator source guidance.

The remaining test code shows incomplete reasoning and workflow execution.
Most signer tests sign under the ambient clock but verify under an unrelated
timestamp near 1000, producing future-signature failures under the two frozen
clocks. The last two accepted edits correct only the first two test methods.
Static review of the retained source also finds a fractional test expecting both
acceptance and expiry at the same age/limit, an integer equality test expecting
expiry, and serializer tests patching `get_timestamp` on the serializer rather
than its signer. These are **unexecuted residual source observations**, not a
new diagnostic campaign or sealed grade. The final candidate was not repaired
or retested after quarantine.

Five oversized test edits were safely rejected despite explicit tool bounds.
The worker recovered by splitting edits, but spent its remaining time on test
construction and did not run interfaces, documentation, syntax or aggregate
acceptance. Useful source editing is established; reliable, independently
accepted feature completion within this protocol is **not established**.
The capture correction is not reopened. No harness replacement or architectural
change follows from this single outcome.

**Milestone E remains BLOCKED pending operator review. Stop here.** Do not
automatically prepare another ItsDangerous trial, modify the harness, begin REA
work, dispatch the Pi comparison or start another development phase.

## Integrity and verification

Before dispatch, all **152 frozen files**, manifest/controller/dependency hashes,
scope, catalog, image and A100 identity/idle slot passed revalidation. The offline
image is `sha256:00d3d7e3d1e32064b5bf313cc788fb91945c0c5fa000856513f490f2c8087645`;
Python 3.12.16, pytest 9.0.3, freezegun 1.5.5, python-dateutil 2.9.0.post0, six
1.17.0. Pinned harness/dependency identities are in the consumed manifest.
Preflight disk space was 262,247,563,264 bytes, above capture plus headroom.

After execution, **4,082 historical indexed entries**, all 152 approved bundle
files and every controller/asset hash passed verification. Main remains
`cf50e89c2ca2ad21d86fda5473f5ad6edc0c2623`. Historical trials, consumed grants,
frozen Click, remote services and the unauthorized Pi comparison are preserved.
All 935 local bundle files are inventoried; runtime homes/databases/private logs
remain local. The complete captured requests/responses, model edits, inspected
source, tool results and timing/cleanup receipts are committed without secrets
or sealed material. The final stream is explicitly partial, never reconstructed.

No controller implementation changed. The full **231/231** regression and
installed inert-conformance results belong to preparation at `389d192`; they
were not rerun or represented as new trial tests. This execution's checks and
integrity audits are linked in [the evidence index](evidence/milestone-e-final-result/README.md).
