# Decisions

- Use Python 3.12+ and SQLite with no runtime Python dependencies. Store structured execution metadata in SQLite and keep workspaces and logs on disk.
- Use OpenCode 2 with a private standalone server, scoped edit permissions and a task-local MCP test tool. Independently check the resulting workspace from a fresh copy. [OpenCode CLI](https://opencode.ai/docs/cli/commands/) · [Permissions](https://opencode.ai/docs/permissions/) · [MCP servers](https://opencode.ai/docs/mcp-servers/)
- Use Ollama and llama.cpp through their loopback OpenAI-compatible interfaces. Reuse the existing A100 SSH alias and forward only the model HTTP port. Cloud operations use a separate provider identity. [Ollama API](https://docs.ollama.com/api/openai-compatibility) · [Lambda Cloud API](https://docs.lambda.ai/public-cloud/cloud-api/)
