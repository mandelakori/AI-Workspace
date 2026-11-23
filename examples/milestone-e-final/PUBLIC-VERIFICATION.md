# Public acceptance contract

FEATURE.md is unchanged. These checks make its existing requirements executable;
they are public development material, not independent evaluation or solutions.

Command indices: 0 original 12 cases; 1 expanded public behavior (original 12 plus
36 additional cases); 2 upstream; 3 authored tests; 4 interfaces; 5 documentation;
6 syntax; 7 acceptance (all seven checks in one offline container invocation).
Original and expanded scores are always reported separately.

Preserve arbitrary Python integer limits, including exact equality and strict
expiry above floating-point exactness. Preserve None and previously accepted
numeric seconds. Unsupported types that the pristine API rejects must still be
rejected, including conversion-capable nonnumeric types. Signature validation
precedes age/type handling. Duration checks cover negative, zero, equality,
fractional seconds, finite future timestamps, UTC metadata, unsafe payloads,
custom separators and key rotation. Read the public corpus for precise inputs.

Update docs/timed.rst meaningfully: explain max_age/timedelta, seconds and
fractional durations, inclusive expiry equality, zero and negative limits. Public
doc checks require changed content, at least 30 words and these concepts; they
are a bounded structural check, not a claim of complete semantic prose review.
Relevant public docstrings and all max_age annotations/overloads must mention
or support timedelta.

Author tests in the permitted test file. They must collect at least six passing
tests with assertions/pytest.raises, no skips or xfails, and no wall-clock sleeps
(including imported aliases). Do not call encode on a bytes separator. The public
authored-test verifier runs the unchanged suite twice under different frozen UTC
clocks, forbids sleep at runtime and checks that both runs exercise timedelta,
integer and None limits, at least one unsupported type, and an integer above
2**53. Tests may use their own deterministic clocks, monkeypatches or freezegun
ticks. An assertion passing at age zero does not establish another boundary.

Before declaring completion, run command 7 and resolve its public diagnostics.
Successful engineering closure requires completed/clean harness execution,
model-authored edits, a successful worker acceptance call, all controller gates
passing, no lost public passes and no scope changes. Missing/failed gates cannot
be bypassed by a higher behavior score. Partial work is retained without a freeze
or independent grade. No retry or mid-run implementation guidance is available.

Use the exact hash editor. A new-text field is at most 3000 UTF-8 bytes; anchors
are at most 1200 bytes. Use small verified replacements/insertions or inspected
locations. The 4096-token output ceiling does not permit oversized file rewrites.
No historical attempted solution, diagnostic driver or correction is supplied.
After this one authorized trial, stop for milestone assessment; do not repeat it.
