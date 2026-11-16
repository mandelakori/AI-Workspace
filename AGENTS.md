# AI Workspace engineering contract

AI Workspace is a Windows-first controller for engineering jobs. Preserve the boundary between inference engine, model, harness, deterministic tools, routing, worker planes and verification. Operating the platform must remain possible with Python, the documented open-source harnesses and the operator’s own inference services.

- Start with [STATUS.md](docs/STATUS.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [NEXT_STEPS.md](docs/NEXT_STEPS.md). Run `python -m unittest discover -s tests -v` and the direct fixture before changing an interface. For harness changes, run the matching hardware fixture when the endpoint is available and record the verdict and artifacts.
- Preserve the operator’s original REA-Next checkout, SSH setup, model files and volumes. Use named, disposable fixtures and an operator-authorized scope. Store results in AI Workspace’s state directory.
- Require operator authorization for cloud writes, remote bootstrap, and reviewed host execution. Treat models and source content as untrusted input. Use authorized software, benign toy targets and defensive or general engineering tasks.
- Keep retry loops and subprocess output bounded. Make each routed attempt independently auditable. A model’s claim does not set the verification verdict.
- Keep private verification material out of harness inputs and retry text. Verify artifact paths and changes against the manifest and retain failed attempts. Do not add secrets or raw private benchmark artifacts to Git.
- Update status labels only after checking actual logs. Keep provider and harness versions explicit. A finite differential suite supports its tested inputs.
- For engineering tasks, authorize file roots and command recipes through the manifest. Keep Docker, planner, and checkpoint changes covered by `tests/test_engineering.py`. See [Engineering mode](docs/ENGINEERING.md) for the isolated runner and patch review flow.
