# Calibrated Ollama cold-start evidence

- `diagnosis.json` binds the saved failure, prior calibration and inspected versioned Ollama sources. The original trial archive is unchanged.
- `cold-start-before.log` and `cold-start-direct.log` record the pre-change deterministic suite and direct fixture.
- `cold-start-final.log` and `cold-start-focused.log` record deterministic and inert regression checks after the correction.
- `cold-start-focused-fixture-failure.log` preserves an intermediate test setup error. The simulated second attempt initially reused its predecessor's artifact directory. The corrected test uses a fresh attempt directory.
- `initialization-review.json` and `initialization-review.sha256` define the separate unsigned load-only review. `initialization-validate.log` records read-only manifest validation. Neither Ollama model initialization nor live engineering inference was run.
- `evidence-hashes.json` indexes the evidence by SHA-256 and byte count.
