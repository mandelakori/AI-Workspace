# Additional harness compatibility review

Reviewed 2026-11-21 against primary source. Only OpenCode and the experimental
pinned Pi adapter have installed engineering conformance in this implementation.
Qwen Code remains **BLOCKED** for scoped engineering and is not a dependency.
mini-SWE-agent and DeepSeek Harness are **UNTESTED / unimplemented** here.

| Harness | Execution and local inference | Context / unattended use | Required AI-Workspace integration |
| --- | --- | --- | --- |
| OpenCode | Installed reference; private server and provider catalog gate | Headless sessions; existing contract/epoch bridge | Retain existing four-tool scope, exact editor, owned jobs and deterministic verification |
| Pi 1.6.0 | SDK session, custom tools and explicit OpenAI-compatible loopback provider | In-memory session, configurable automatic compaction, programmatic cancellation | Implemented experimental bridge; real Qwen engineering remains unmeasured |
| mini-SWE-agent | Small Python query/execute loop; default agent uses bash actions and an environment; LiteLLM supports local API bases | Simple message history and explicit step/resource limits; CLI/batch unattended execution | Replace unrestricted action execution with strict scoped-tool dispatch; add catalog gate, durable contract/epochs, compaction accounting and owned cancellation |
| DeepSeek Harness 0.2.2-rc.5 source snapshot | Node/Cordis plugin system; headless CLI and SDK; Ollama integration exists upstream | `headless --json` waits for quiescence and session flush; persistent agents and compaction policies | Pin reviewed plugin graph; remove native shell/filesystem/web mutations, route scoped tools through controller, prove context compatibility, gate provider/catalog and own all descendants |

mini-SWE-agent is the next integration priority **after** the separately approved
OpenCode/Pi comparison, because its transparent minimal Python loop offers a
distinct, testable reference for harness overhead and context policy. This is an
integration recommendation, not a measured quality or speed advantage. Its default
bash-only parser/environment cannot satisfy the exact-edit contract unchanged.
Step/cost limits alone do not replace the controller's cumulative wall deadline,
category reservations or quarantine policy. A future adapter must reject arbitrary
shell actions rather than interpreting them as permission to run commands.

DeepSeek Harness needs a separate security/compatibility review before admission.
Its source labels the project a developer preview and not security audited. The
minimal SDK example uses `danger-full-access` without an approval service; that
example is not an acceptable adapter configuration. The reviewed package requires
Node >=24.9. Existing headless/SDK paths inherit a broader native tool stack unless
the plugin set is explicitly restricted.

The official Ollama launcher configures DeepSeek Harness with native Ollama,
web search and cloud connection integration. Do **not** use that launcher as this
platform's scoped local adapter. Configure only the owned local provider and remove
web/cloud tools first. Ollama's launcher source also documents a 65536-token
compaction headroom reservation in dsh 0.2.x. Together with output reservation this
can disable compaction at our measured 8K/16K/32K sizes. That policy needs a reviewed
override and forced-compaction conformance before dsh can meet this platform's
context contract. Native Ollama support alone does not establish safe compatibility.

No mini-SWE-agent/DeepSeek dependencies were installed, no real inference was
performed through them and no capability declaration was promoted by this review.
Future conformance must cover missing/extra tools, denied native mutation, exact
source hashes, repeated compaction with source eviction, public verification,
resource exhaustion, provider cancellation, process ownership and cleanup failure.

Primary sources (unversioned links are discovery references, not runtime pins):

- [mini-SWE-agent agent loop](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/agents/default.py),
  [LiteLLM adapter](https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/models/litellm_model.py),
  [local model setup](https://github.com/SWE-agent/mini-swe-agent/blob/main/docs/models/local_models.md).
- [DeepSeek package](https://github.com/deepseek-ai/deepseek-harness/blob/master/package.json),
  [CLI reference](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/reference/README.md),
  [CLI help](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cli-help.md),
  [safety status](https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md).
- [Ollama DeepSeek integration](https://github.com/ollama/ollama/blob/main/docs/integrations/deepseek-harness.mdx),
  [launcher and context policy](https://github.com/ollama/ollama/blob/main/cmd/launch/deepseek_harness.go).
