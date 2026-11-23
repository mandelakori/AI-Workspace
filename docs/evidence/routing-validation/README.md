# Routing validation evidence

- `targeted-before.log` shows the failure assertions against `bac5fad`. `local-cleanup-before.log` reproduces promotion after failed isolated Ollama cleanup and a clean relay exit. `before-ollama-forwarded.json` shows the original serialization without Ollama's ceiling field. `targeted-final.log` shows the repaired cases and installed inert-controller checks. `regressions-validated.log` is the final installed and offline regression suite.
- `inert/local` and `inert/a100` contain the synthetic provider requests, forwarded bytes, streams, admission and tool receipts, and independent-verifier results. The A100 transport seam is inert in these directories.
- `prepared` contains the two immutable manifests and read-only readiness records. The bundle comparison includes the pristine baseline and invalid-approval checks. The private tests are represented by hashes and redacted scoring receipts.
- `evidence-hashes.json` records byte counts and SHA-256 hashes for this archive. No operator approval was created for either prepared arm.
