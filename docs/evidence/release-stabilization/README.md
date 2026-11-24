# Release stabilization evidence

- `baseline.log` and `final.log` contain the full installed inert and offline test passes before and after the change. `focused.log` records the focused checks, with the optional installed boundary test enabled in the full suite.
- `direct.log`, `queued.log`, `worker.log`, `run-detail.log`, `doctor.log`, `inspect.log`, `help.log` and `invalid-config.log` record the deterministic CLI audit.
- The offline wheel build and isolated install used the existing pinned setuptools wheel. The initial build without that backend is retained in `wheel.log`.
- `smoke/` contains the local-only manifest, digest and offline baseline receipts. The private cases and any future grant stay outside Git. There was no generation, worker dispatch or external unload.
- `evidence-hashes.json` binds the archived bytes.
