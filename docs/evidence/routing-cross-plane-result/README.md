# Cross-plane execution preflight evidence

- `dependency-recovery.json` records the initial local Docker availability check and the bounded startup of the installed engine, before any worker launch.
- `local-resource-diagnosis.json` and `preflight-local.json` preserve the two observed local memory checks and the calibrated admission outcome.
- `preflight-a100.json` preserves the matched model identity and idle slot observed through the owned read-only forward.
- `process-observation.json` records the read-only OS and NVIDIA process observation. Per-process GPU usage was unavailable.
- `execution-state.json` records the absence of controller state, consumed grants, candidates and model requests in either arm. No private cases or approval files were copied into the archive.
- `evidence-hashes.json` binds the archived files by SHA-256 and byte count.
