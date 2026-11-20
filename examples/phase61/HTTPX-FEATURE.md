# HTTPX path-scoped transport mounts

Preparation only. No model campaign is authorized by this file. Base: HTTPX
0.28.1, commit 26d48e0634e6ee9cdc0533996db289ce4b430177 (BSD-3-Clause).

Add path-prefix matching to URL patterns used for client transport mounts.
Applications should be able to route /api and /api/v2 to different in-process
transports without changing host/scheme/port routing. Support both Client and
AsyncClient, keeping normal request URL construction and transport ownership.

A non-root pattern path matches itself and descendants at slash boundaries.
/api must not match /apix. A trailing slash on a pattern is optional: /api and
/api/ select the same subtree. Empty and root paths remain unrestricted, as
before. Matching is case-sensitive. Query strings and fragments do not narrow
path scope. Compare normalized percent-encoded paths; an encoded slash is not
a subtree separator. Continue using HTTPX's existing URL parsing rules.

Preserve existing scheme, wildcard host and port matching, error behavior and
priority. When those priorities are equal, more specific (longer) path prefixes
sort before shorter/root paths. Preserve stable ordering for equal patterns.
This applies to the existing URLPattern abstraction; preserve pathless proxy
and environment-pattern behavior. Do not introduce networking or credentials
into tests. All transport tests must use MockTransport and trust_env=False.

Add focused tests in tests/test_path_mounts.py and document path-scoped mounts
in docs/advanced/transports.md. Existing tests and public verifiers are read-only.
Permitted production edits: httpx/_utils.py and httpx/_client.py only.

Workers may inspect approved public source, edit only the four approved paths,
and run the approved offline public commands. Models may propose a plan but
cannot extend permissions. No operator-written solution or mid-run
implementation guidance is allowed in a measured trial. If the fixed budget
expires, freeze the strongest candidate and preserve failure evidence.

Initial permissions/model/image/budget review is required before trial dispatch.
No direct-versus-hierarchical comparison is executed during this preparation.
Future trials must use the same starting hashes, public corpus, model, context,
tools, verifier and cumulative worker-time ceiling. Include planning overhead
in the hierarchical budget. Do not claim matched token budgets unless enforced.

Independent acceptance inputs must be authored outside all worker contexts
only after each final candidate is frozen. Cover new boundary paths, normalized
encodings, precedence combinations, sync/async integration and unchanged legacy
behavior. Do not use final feedback to revise candidates or retry prompts.
