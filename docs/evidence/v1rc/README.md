# RC package and CLI verification

- `audit.json`, `build.log`, `install.log` and `pip-check.log` record the offline wheel and isolated installation. `version-outside-checkout.log` confirms the installed executable reports the RC version outside the checkout.
- `cli/` records package CLI help, inventory, task review, direct queue and Docker verification, profile-specific scratch submissions and expected errors. The two engineering jobs stayed queued in the scratch state and were never dispatched.
- `doc-validation.json` records checked release links and preservation of the previous status and handoff content. The A–E labels come from `baf9e9f:docs/STATUS.md`.
- `evidence-hashes.json` indexes the archived bytes. The wheel stays in the local ignored release directory for review.
