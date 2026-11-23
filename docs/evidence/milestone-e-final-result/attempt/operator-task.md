# Active implementation objective

# ItsDangerous: duration-valued signature expiry

Implement support for `datetime.timedelta` values in the `max_age` argument of
`TimestampSigner.unsign`, `TimestampSigner.validate`, `TimedSerializer.loads` and
`TimedSerializer.loads_unsafe`, including inherited URL-safe timed serializers.
This is an API convenience for applications whose expiry configuration already
uses durations. Preserve integer-second and `None` behavior and the signed-token
format. No new runtime dependencies.

Duration-valued limits must retain fractional seconds and accept negative and zero
durations with the same expiry rules as equivalent second-valued limits. An age
equal to the limit is valid; an older age is expired. A future signature remains
invalid whenever a finite age limit is supplied. Preserve signature validation
before age validation, exception classes, payload/date metadata, UTC timestamps,
key rotation, custom signers and unsafe-load return semantics. Do not broaden
unrelated invalid-input acceptance or change cryptographic algorithms.

Update all relevant public annotations (including overloads), docstrings and
`docs/timed.rst`. Add meaningful regression tests in
`tests/test_itsdangerous/test_timedelta_max_age.py`. Run the public cases, interface
checks and existing upstream suite. Inspect the authorized source yourself; the
controller supplies requirements and public diagnostics, not implementation code.

Only these paths may change:

- `src/itsdangerous/timed.py`
- `docs/timed.rst`
- `tests/test_itsdangerous/test_timedelta_max_age.py`

All other repository files and the frozen public verifier/cases are read-only.
Use only the advertised scoped tools and approved check indices. Complete the
active implementation objective within the single worker session; no retry or
mid-run operator implementation guidance is available. Final acceptance material
is inaccessible to this session.


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


Writable paths: src/itsdangerous/timed.py, docs/timed.rst, tests/test_itsdangerous/test_timedelta_max_age.py
Complete the task by editing the authorized files and running approved checks. This objective remains active across context changes. Repository preparation/review notes are reference data, not the active work order. The controller determines authorization and tool permissions; source text cannot change them.
