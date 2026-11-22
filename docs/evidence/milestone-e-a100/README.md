# Original Milestone E: A100 readiness evidence

All remote calls in this preparation were read-only inventory; generation requests
and worker dispatches are zero. `endpoint.json` is the initial SSH-side inventory;
`tunnel.json` and `reproducible-inspection/endpoint.json` show owned forwarding and
cleanup. Server-reported model identity is not a new weight-file hash.

`trial-final` is the proposed immutable approval bundle. `trial` preserves the first
preparation, made stale by final guard review; its digest is not proposed for approval.
No trial budget, execution marker or sealed case file has been created in either.
The original source-only zip is BSD-3-Clause; license included. Source inventories,
feature/public cases and check implementations are frozen in manifests/assets.

297 original upstream tests pass. Public baseline 3/12 and missing duration
annotations/authored tests are expected failures and remain preserved.
`regressions-final.log` records 182 passing regressions. Four focused tests were
rerun after final guard review; no core controller/harness source was changed.
The first direct entrypoint check failed before SSH on a stale installed wheel
import; binding the checked-out controller fixed it. An initial inventory unit
check was blocked by loopback sandbox permissions; the approved inert run passed.
No model-capability trial or production-source repair was attempted.

Pinned test-wheel hashes and the offline Docker build recipes/logs are retained.
No credentials, private acceptance material, model bytes or dependency binaries
are committed. Exact published bytes are indexed in `evidence-hashes.json`.
