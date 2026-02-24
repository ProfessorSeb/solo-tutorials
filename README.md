# Agentgateway Tutorials

Kubernetes tutorials for [agentgateway](https://agentgateway.dev/) — an open source, AI-native data plane for connecting, securing, and observing agent-to-agent and agent-to-tool communication.

## Tutorials

### Getting Started
- [01 - LLM Gateway](01-llm-gateway/) — Route requests to multiple LLM providers (xAI, Anthropic, OpenAI)
- [07 - Azure AI Foundry](07-azure-ai-foundry/) — Route requests to Azure OpenAI through agentgateway
- [08 - Prompt Enrichment](08-prompt-enrichment/) — Inject context at the gateway layer

### MCP (Model Context Protocol)
- [02 - Basic MCP Server](02-basic-mcp-server/) — Deploy and route to an MCP server
- [03 - MCP Federation](03-mcp-federation/) — Federate multiple MCP servers behind a single endpoint

### Security
- [04 - JWT Authorization](04-jwt-authorization/) — Secure your gateway with JWT authentication
- [06 - AI Prompt Guard](06-ai-prompt-guard/) — Protect LLM requests from sensitive data
- [09 - Claude Code CLI Proxy](09-claude-code-proxy/) — Proxy and secure Claude Code CLI traffic

### Operations
- [05 - Telemetry & Observability](05-telemetry/) — Distributed tracing with OpenTelemetry and Jaeger

## Reference

- [Agentgateway Docs](https://agentgateway.dev/docs/kubernetes/latest/)
- [Agentgateway Tutorials](https://agentgateway.dev/docs/kubernetes/latest/tutorials/)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
