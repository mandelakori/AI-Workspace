# Architecture

1. `schema.py` loads the TOML operator contract. `workspace.py` snapshots selected files, refuses linked paths, excludes common credential and harness settings paths, and hashes the stage. Intake records build and test hints, Python function names and syntactic call references, and PE/ELF architecture metadata.
2. `state.py` claims queued jobs atomically in SQLite. `router.py` ranks eligible profiles by a smoothed verified rate for the same category, preferred compute plane at the stated complexity, historical success time and stable ID. Overrides filter candidates. Jobs record ranked routes and attempt-level failures.
3. Local and A100 schedulers gate execution with cross-process locks in the controller state directory. A100 dispatch serializes the shared model lane and opens a strict localhost-to-localhost SSH tunnel. The harness runs on Windows. Managed profiles can ask `cloud.py` to acquire and wait for one named Lambda instance. Cloud-init can restore a pre-staged persistent launcher/model and start a private listener.
4. `harness.py` builds ephemeral OpenCode or Qwen Code configuration for the exact inference profile. Native shell tools are disabled in the supplied harness policies. The stdio MCP bridge only accepts an index into the operator’s approved public checks. `specialists.py` supports PE/ELF evidence, headless Ghidra and an operator-configured external static analysis command. Agent prompts receive a bounded summary and selected evidence.
5. `verify.py` runs tests independently of the agent, using the candidate copy after checking the changed file set. A task can use exact output assertions or an external differential oracle. Failure leads to another ranked profile within the attempt budget. A new attempt starts from the same frozen baseline.
6. Attempt directories hold routing, harness events, public tool results, generated files, verification outputs and hashes. The SQLite state can recover a queued or explicitly resumed job after a process interruption. `workflow.py` handles declared dependency graphs and carries forward verified deliverables through `.handoff/`.
7. `benchmark.py` compares selected profiles with independent baseline snapshots and a common fixture hash. Results include wall time, tool calls, emitted token usage and independent verdicts. Every completed sample is checkpointed.

The A100 scheduler runs in the controller. An A100-local harness daemon, a general MCP broker and a hard multi-tenant GPU allocator are extension points.

## Hierarchical engineering

`hierarchy.py` registers a project with explicit component interfaces, selected public files, dependency artifacts and approved runner commands. The local planning coordinator and planning specialist reorganize these component IDs in a nested tree. An approval digest binds the tree to the registered policy, runner and profile. The existing workflow scheduler expands the tree into dependency jobs and validates the digests of their scoped handoffs. Separate deterministic analysis, testing and integration jobs produce evidence and verified artifacts. Implementers use the installed harness or a bounded local single-file proposal. A targeted retry switches the worker to the debugging role and preserves other verified jobs. [Phase 5 operator workflow](PHASE5.md)

Components can opt into ranked multi-turn engineering with a named read-only public corpus, approved compile/run recipes and an absolute attempt budget. `adaptive.py` produces review-only interface and dependency changes from recorded public failures. A new approved graph can reuse byte-identical verified nodes with compatible dependency ancestry, profile and pinned verifier. [Phase 5.1 operator workflow](PHASE51.md)

## Engineering execution

- Existing manifests use restricted execution. An engineering manifest authorizes explicit file or directory roots and a list of public command recipes. The harness can edit or create files under those roots. The MCP service offers command indices and a Git diff. Runner copies receive no host shell, network, Docker socket or private verifier mount.
- Setup and commands execute in disposable copies. A setup recipe can install from staged, reviewed offline packages. Independent verification runs an ordered pipeline in a separate copy. Each command may select a workspace-relative subdirectory.
- Engineering attempts retain Git patches, checksums, failure classifications and validated checkpoints. Retries can start from a previous in-policy candidate. Use `task resume --reset` to start from the original snapshot while retaining previous evidence.
- The planner sends a bounded index and objective to an existing inference profile. The controller validates the JSON graph against operator commands and write scopes. It assigns preferred lanes, runs workers through the same queue and merges only independently verified deltas. It checks file hashes and collisions before running combined verification. An integration failure can trigger one repair job.
- The self workflow archives a committed Git snapshot. The operator can supply an engineering manifest with explicit writable paths. The runner independently verifies the resulting patch and preserves the original regression suite.

## Phase 3

The project index stores path hashes, cached metadata and attempt evidence in SQLite. Each refresh rehashes the bounded tree and reparses previously unseen content for that language and parser version. Python imports and common relative JavaScript and TypeScript imports produce module edges. The operator can use a ranked selection and direct dependencies as manifest `inputs`. Hash comparisons indicate whether linked attempt observations match the indexed files.

The planner accepts a validated operator-reviewed graph. A revision can inherit verified jobs when the manifest, baseline, private assets, runner, trust and predecessor chain agree. A pause leaves the queue between steps. The worker holds a per-job lock for its lifetime, and a short dispatch lock serializes claims with interrupted-job recovery.

The sealed oracle runs each candidate invocation with read-only source and network disabled in a fresh Docker container. The controller sends the current case input and compares exit status, stdout and stderr on the host. Audit reports contain case counts, verdicts and timing. The legacy verification-directory mount continues to support reviewed tests that need that interface.

Phase 3 shares one A100 inference lane with the original controller. GPU samples capture device total and free memory around harness calls. The laptop can apply a configured free-memory requirement before loading a model and consults Ollama for residency. Effective output rate uses harness wall time, which includes tool calls, and reports record lane wait separately. Category reliability and verified latency continue to inform routing.
