# Agentgateway LLM Providers — Kubernetes Configuration Guide

Complete `kubectl apply` configurations for **50+ LLM providers** on Kubernetes using agentgateway + kgateway. Every example follows the official docs pattern from [agentgateway.dev/docs/kubernetes/latest/llm/providers](https://agentgateway.dev/docs/kubernetes/latest/llm/providers).

---

## Prerequisites

```bash
# 1. Install kgateway + agentgateway
helm repo add kgateway https://kgateway-dev.github.io/kgateway
helm repo update
helm install kgateway kgateway/kgateway \
  --namespace agentgateway-system \
  --create-namespace

# 2. Verify pods are running
kubectl get pods -n agentgateway-system

# 3. Get the gateway address
# Cloud LoadBalancer
export INGRESS_GW_ADDRESS=$(kubectl get svc -n agentgateway-system agentgateway-proxy \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Or port-forward for local testing
kubectl port-forward -n agentgateway-system svc/agentgateway-proxy 8080:8080 &
```

---

## How It Works

Every provider follows 3 Kubernetes resources:

```
Step 1: Secret (API credentials)
Step 2: AgentgatewayBackend (provider configuration)
Step 3: HTTPRoute (traffic routing)
```

**Native providers** (OpenAI, Anthropic, Bedrock, Gemini, Vertex AI) have their own `provider` type — agentgateway understands their API natively.

**OpenAI-compatible providers** (everything else) use `provider.openai` with custom `host`, `port`, `path` overrides + `policies.tls.sni` for HTTPS.

---

## Native Providers

These have first-class support with full API translation in agentgateway.

---

### OpenAI

```bash
# Step 1: Secret
export OPENAI_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: openai-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $OPENAI_API_KEY
EOF

# Step 2: Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: openai
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: gpt-4o
  policies:
    auth:
      secretRef:
        name: openai-secret
EOF

# Step 3: Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: openai
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /openai
    backendRefs:
    - name: openai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/openai" -H content-type:application/json -d '{
  "model": "gpt-4o",
  "messages": [{"role": "user", "content": "Hello!"}]
}' | jq
```

#### OpenAI with Multiple Endpoints (embeddings, models, responses)

```bash
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: openai
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: gpt-4o
  policies:
    auth:
      secretRef:
        name: openai-secret
    ai:
      routes:
        "/v1/chat/completions": "completions"
        "/v1/embeddings": "passthrough"
        "/v1/models": "passthrough"
        "/v1/responses": "passthrough"
        "*": "passthrough"
EOF
```

#### Cleanup

```bash
kubectl delete AgentgatewayBackend openai -n agentgateway-system
kubectl delete HTTPRoute openai -n agentgateway-system
kubectl delete secret openai-secret -n agentgateway-system
```

---

### Anthropic

```bash
# Step 1: Secret
export ANTHROPIC_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: anthropic-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $ANTHROPIC_API_KEY
EOF

# Step 2: Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: anthropic
  namespace: agentgateway-system
spec:
  ai:
    provider:
      anthropic:
        model: "claude-sonnet-4-20250514"
  policies:
    auth:
      secretRef:
        name: anthropic-secret
EOF

# Step 3: Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: anthropic
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /anthropic
    backendRefs:
    - name: anthropic
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test — native Messages API
curl "localhost:8080/anthropic" -H content-type:application/json -d '{
  "model": "claude-sonnet-4-20250514",
  "messages": [{"role": "user", "content": "Hello!"}]
}' | jq
```

#### Anthropic with Claude Code CLI support

To use with Claude Code, set the model to `{}` (any model) and add passthrough routes:

```bash
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: anthropic
  namespace: agentgateway-system
spec:
  ai:
    provider:
      anthropic: {}
  policies:
    ai:
      routes:
        '/v1/messages': Messages
        '*': Passthrough
    auth:
      secretRef:
        name: anthropic-secret
EOF
```

```bash
# Connect Claude Code CLI
ANTHROPIC_BASE_URL="http://localhost:8080" claude
```

---

### Amazon Bedrock

```bash
# Step 1: Secret (IAM credentials)
export AWS_ACCESS_KEY_ID="<your-access-key>"
export AWS_SECRET_ACCESS_KEY="<your-secret-key>"
export AWS_SESSION_TOKEN="<your-session-token>"

kubectl create secret generic bedrock-secret \
  -n agentgateway-system \
  --from-literal=accessKey="$AWS_ACCESS_KEY_ID" \
  --from-literal=secretKey="$AWS_SECRET_ACCESS_KEY" \
  --from-literal=sessionToken="$AWS_SESSION_TOKEN" \
  --type=Opaque \
  --dry-run=client -o yaml | kubectl apply -f -

# Step 2: Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: bedrock
  namespace: agentgateway-system
spec:
  ai:
    provider:
      bedrock:
        model: "us.anthropic.claude-sonnet-4-20250514-v1:0"
        region: "us-east-1"
  policies:
    auth:
      secretRef:
        name: bedrock-secret
EOF

# Step 3: Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: bedrock
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /bedrock
    backendRefs:
    - name: bedrock
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/bedrock" -H content-type:application/json -d '{
  "model": "",
  "messages": [{"role": "user", "content": "Hello from Bedrock!"}]
}' | jq
```

> To use **IRSA** (IAM Roles for Service Accounts) instead of static credentials, omit the `policies.auth` section entirely.

---

### Google Gemini

```bash
# Step 1: Secret
export GOOGLE_KEY=<your-gemini-api-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: google-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $GOOGLE_KEY
EOF

# Step 2: Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: gemini
  namespace: agentgateway-system
spec:
  ai:
    provider:
      gemini:
        model: gemini-2.5-flash
  policies:
    auth:
      secretRef:
        name: google-secret
EOF

# Step 3: Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: gemini
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /gemini
    backendRefs:
    - name: gemini
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/gemini" -H content-type:application/json -d '{
  "model": "gemini-2.5-flash",
  "messages": [{"role": "user", "content": "Hello from Gemini!"}]
}' | jq
```

---

### Google Vertex AI

```bash
# Step 1: Secret
export VERTEX_AI_API_KEY=<your-vertex-api-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: vertex-ai-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $VERTEX_AI_API_KEY
EOF

# Step 2: Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: vertex-ai
  namespace: agentgateway-system
spec:
  ai:
    provider:
      vertexai:
        model: gemini-pro
        projectId: "my-gcp-project"
        region: "us-central1"
  policies:
    auth:
      secretRef:
        name: vertex-ai-secret
EOF

# Step 3: Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: vertex-ai
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /vertex
    backendRefs:
    - name: vertex-ai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/vertex" -H content-type:application/json -d '{
  "model": "gemini-pro",
  "messages": [{"role": "user", "content": "Hello from Vertex AI!"}]
}' | jq
```

---

### Azure OpenAI

```bash
# Step 1: Secret
export AZURE_API_KEY=<your-azure-api-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: azure-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $AZURE_API_KEY
EOF

# Step 2: Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: azure-openai
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: gpt-4o
        host: your-resource.openai.azure.com
        port: 443
        path: "/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21"
  policies:
    auth:
      secretRef:
        name: azure-secret
    tls:
      sni: your-resource.openai.azure.com
EOF

# Step 3: Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: azure-openai
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /azure
    backendRefs:
    - name: azure-openai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/azure" -H content-type:application/json -d '{
  "model": "gpt-4o",
  "messages": [{"role": "user", "content": "Hello from Azure!"}]
}' | jq
```

---

## OpenAI-Compatible Providers

All providers below use `provider.openai` with custom `host`, `port`, `path` overrides. This is the pattern for any provider that exposes an OpenAI-compatible `/v1/chat/completions` endpoint.

Key differences from native providers:
- **`host`** and **`port`** are required in the `openai:` block
- **`policies.tls.sni`** is required for HTTPS endpoints
- HTTPRoute uses a **`URLRewrite` filter** with `hostname` for path-matched routes

---

### Mistral AI

```bash
# Step 1: Secret
export MISTRAL_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: mistral-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $MISTRAL_API_KEY
EOF

# Step 2: Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: mistral
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: mistral-medium-2505
        host: api.mistral.ai
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: mistral-secret
    tls:
      sni: api.mistral.ai
EOF

# Step 3: Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: mistral
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /mistral
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.mistral.ai
    backendRefs:
    - name: mistral
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/mistral" -H content-type:application/json -d '{
  "model": "mistral-medium-2505",
  "messages": [{"role": "user", "content": "Hello from Mistral!"}]
}' | jq
```

---

### DeepSeek

```bash
export DEEPSEEK_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: deepseek-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $DEEPSEEK_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: deepseek
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: deepseek-chat
        host: api.deepseek.com
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: deepseek-secret
    tls:
      sni: api.deepseek.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: deepseek
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /deepseek
    backendRefs:
    - name: deepseek
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/deepseek" -H content-type:application/json -d '{
  "model": "deepseek-chat",
  "messages": [{"role": "user", "content": "Hello from DeepSeek!"}]
}' | jq
```

---

### xAI (Grok)

```bash
export XAI_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: xai-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $XAI_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: xai
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: grok-2-latest
        host: api.x.ai
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: xai-secret
    tls:
      sni: api.x.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: xai
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /xai
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.x.ai
    backendRefs:
    - name: xai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/xai" -H content-type:application/json -d '{
  "model": "grok-2-latest",
  "messages": [{"role": "user", "content": "Hello from Grok!"}]
}' | jq
```

---

### Groq

```bash
export GROQ_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: groq-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $GROQ_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: groq
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: llama-3.3-70b-versatile
        host: api.groq.com
        port: 443
        path: "/openai/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: groq-secret
    tls:
      sni: api.groq.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: groq
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /groq
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.groq.com
    backendRefs:
    - name: groq
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/groq" -H content-type:application/json -d '{
  "model": "llama-3.3-70b-versatile",
  "messages": [{"role": "user", "content": "Hello from Groq!"}]
}' | jq
```

---

### Cohere

```bash
export COHERE_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: cohere-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $COHERE_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: cohere
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: command-r-plus
        host: api.cohere.ai
        port: 443
        path: "/compatibility/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: cohere-secret
    tls:
      sni: api.cohere.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: cohere
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /cohere
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.cohere.ai
    backendRefs:
    - name: cohere
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/cohere" -H content-type:application/json -d '{
  "model": "command-r-plus",
  "messages": [{"role": "user", "content": "Hello from Cohere!"}]
}' | jq
```

---

### Together AI

```bash
export TOGETHER_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: together-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $TOGETHER_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: together
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo
        host: api.together.xyz
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: together-secret
    tls:
      sni: api.together.xyz
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: together
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /together
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.together.xyz
    backendRefs:
    - name: together
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/together" -H content-type:application/json -d '{
  "model": "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo",
  "messages": [{"role": "user", "content": "Hello from Together AI!"}]
}' | jq
```

---

### Fireworks AI

```bash
export FIREWORKS_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: fireworks-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $FIREWORKS_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: fireworks
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: accounts/fireworks/models/llama-v3p1-70b-instruct
        host: api.fireworks.ai
        port: 443
        path: "/inference/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: fireworks-secret
    tls:
      sni: api.fireworks.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: fireworks
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /fireworks
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.fireworks.ai
    backendRefs:
    - name: fireworks
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/fireworks" -H content-type:application/json -d '{
  "model": "accounts/fireworks/models/llama-v3p1-70b-instruct",
  "messages": [{"role": "user", "content": "Hello from Fireworks!"}]
}' | jq
```

---

### Perplexity AI

```bash
export PERPLEXITY_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: perplexity-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $PERPLEXITY_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: perplexity
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: sonar-pro
        host: api.perplexity.ai
        port: 443
        path: "/chat/completions"
  policies:
    auth:
      secretRef:
        name: perplexity-secret
    tls:
      sni: api.perplexity.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: perplexity
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /perplexity
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.perplexity.ai
    backendRefs:
    - name: perplexity
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/perplexity" -H content-type:application/json -d '{
  "model": "sonar-pro",
  "messages": [{"role": "user", "content": "Hello from Perplexity!"}]
}' | jq
```

---

### OpenRouter

```bash
export OPENROUTER_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: openrouter-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $OPENROUTER_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: openrouter
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: anthropic/claude-sonnet-4-20250514
        host: openrouter.ai
        port: 443
        path: "/api/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: openrouter-secret
    tls:
      sni: openrouter.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: openrouter
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /openrouter
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: openrouter.ai
    backendRefs:
    - name: openrouter
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/openrouter" -H content-type:application/json -d '{
  "model": "anthropic/claude-sonnet-4-20250514",
  "messages": [{"role": "user", "content": "Hello from OpenRouter!"}]
}' | jq
```

---

### Cerebras

```bash
export CEREBRAS_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: cerebras-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $CEREBRAS_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: cerebras
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: llama-3.3-70b
        host: api.cerebras.ai
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: cerebras-secret
    tls:
      sni: api.cerebras.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: cerebras
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /cerebras
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.cerebras.ai
    backendRefs:
    - name: cerebras
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/cerebras" -H content-type:application/json -d '{
  "model": "llama-3.3-70b",
  "messages": [{"role": "user", "content": "Hello from Cerebras!"}]
}' | jq
```

---

### SambaNova

```bash
export SAMBANOVA_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: sambanova-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $SAMBANOVA_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: sambanova
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: Meta-Llama-3.1-70B-Instruct
        host: api.sambanova.ai
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: sambanova-secret
    tls:
      sni: api.sambanova.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: sambanova
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /sambanova
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.sambanova.ai
    backendRefs:
    - name: sambanova
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### DeepInfra

```bash
export DEEPINFRA_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: deepinfra-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $DEEPINFRA_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: deepinfra
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta-llama/Llama-3.3-70B-Instruct-Turbo
        host: api.deepinfra.com
        port: 443
        path: "/v1/openai/chat/completions"
  policies:
    auth:
      secretRef:
        name: deepinfra-secret
    tls:
      sni: api.deepinfra.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: deepinfra
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /deepinfra
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.deepinfra.com
    backendRefs:
    - name: deepinfra
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### HuggingFace Inference

```bash
export HF_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: huggingface-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $HF_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: huggingface
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta-llama/Llama-3.1-70B-Instruct
        host: api-inference.huggingface.co
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: huggingface-secret
    tls:
      sni: api-inference.huggingface.co
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: huggingface
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /huggingface
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api-inference.huggingface.co
    backendRefs:
    - name: huggingface
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Nvidia NIM

```bash
export NVIDIA_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: nvidia-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $NVIDIA_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: nvidia-nim
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta/llama-3.1-70b-instruct
        host: integrate.api.nvidia.com
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: nvidia-secret
    tls:
      sni: integrate.api.nvidia.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: nvidia-nim
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /nvidia
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: integrate.api.nvidia.com
    backendRefs:
    - name: nvidia-nim
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Replicate

```bash
export REPLICATE_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: replicate-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $REPLICATE_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: replicate
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta/llama-3.1-405b-instruct
        host: api.replicate.com
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: replicate-secret
    tls:
      sni: api.replicate.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: replicate
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /replicate
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.replicate.com
    backendRefs:
    - name: replicate
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### AI21

```bash
export AI21_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ai21-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $AI21_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: ai21
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: jamba-1.5-large
        host: api.ai21.com
        port: 443
        path: "/studio/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: ai21-secret
    tls:
      sni: api.ai21.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: ai21
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /ai21
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.ai21.com
    backendRefs:
    - name: ai21
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Cloudflare Workers AI

Replace `<ACCOUNT_ID>` with your Cloudflare account ID.

```bash
export CLOUDFLARE_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: cloudflare-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $CLOUDFLARE_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: cloudflare
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: "@cf/meta/llama-3.1-8b-instruct"
        host: api.cloudflare.com
        port: 443
        path: "/client/v4/accounts/<ACCOUNT_ID>/ai/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: cloudflare-secret
    tls:
      sni: api.cloudflare.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: cloudflare
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /cloudflare
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.cloudflare.com
    backendRefs:
    - name: cloudflare
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Lambda AI

```bash
export LAMBDA_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: lambda-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $LAMBDA_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: lambda
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: hermes-3-llama-3.1-405b-fp8
        host: api.lambdalabs.com
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: lambda-secret
    tls:
      sni: api.lambdalabs.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: lambda
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /lambda
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.lambdalabs.com
    backendRefs:
    - name: lambda
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Nebius AI Studio

```bash
export NEBIUS_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: nebius-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $NEBIUS_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: nebius
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta-llama/Llama-3.1-70B-Instruct
        host: api.studio.nebius.com
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: nebius-secret
    tls:
      sni: api.studio.nebius.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: nebius
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /nebius
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.studio.nebius.com
    backendRefs:
    - name: nebius
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Novita AI

```bash
export NOVITA_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: novita-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $NOVITA_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: novita
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta-llama/llama-3.1-70b-instruct
        host: api.novita.ai
        port: 443
        path: "/v3/openai/chat/completions"
  policies:
    auth:
      secretRef:
        name: novita-secret
    tls:
      sni: api.novita.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: novita
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /novita
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.novita.ai
    backendRefs:
    - name: novita
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Hyperbolic

```bash
export HYPERBOLIC_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: hyperbolic-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $HYPERBOLIC_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: hyperbolic
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta-llama/Llama-3.1-70B-Instruct
        host: api.hyperbolic.xyz
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: hyperbolic-secret
    tls:
      sni: api.hyperbolic.xyz
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: hyperbolic
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /hyperbolic
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.hyperbolic.xyz
    backendRefs:
    - name: hyperbolic
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

## Enterprise Cloud Providers

### Databricks

Replace `<your-workspace>` with your Databricks workspace URL.

```bash
export DATABRICKS_TOKEN=<your-token>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: databricks-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $DATABRICKS_TOKEN
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: databricks
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: databricks-meta-llama-3-1-70b-instruct
        host: <your-workspace>.cloud.databricks.com
        port: 443
        path: "/serving-endpoints/databricks-meta-llama-3-1-70b-instruct/invocations"
  policies:
    auth:
      secretRef:
        name: databricks-secret
    tls:
      sni: <your-workspace>.cloud.databricks.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: databricks
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /databricks
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: <your-workspace>.cloud.databricks.com
    backendRefs:
    - name: databricks
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### GitHub Models

```bash
export GITHUB_TOKEN=<your-github-pat>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: github-models-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $GITHUB_TOKEN
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: github-models
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: gpt-4o
        host: models.inference.ai.azure.com
        port: 443
        path: "/chat/completions"
  policies:
    auth:
      secretRef:
        name: github-models-secret
    tls:
      sni: models.inference.ai.azure.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: github-models
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /github-models
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: models.inference.ai.azure.com
    backendRefs:
    - name: github-models
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Scaleway

```bash
export SCALEWAY_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: scaleway-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $SCALEWAY_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: scaleway
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: llama-3.1-70b-instruct
        host: api.scaleway.ai
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: scaleway-secret
    tls:
      sni: api.scaleway.ai
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: scaleway
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /scaleway
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.scaleway.ai
    backendRefs:
    - name: scaleway
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

## Regional & Emerging Providers

### Dashscope (Qwen / Alibaba)

```bash
export DASHSCOPE_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: dashscope-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $DASHSCOPE_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: dashscope
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: qwen-turbo
        host: dashscope.aliyuncs.com
        port: 443
        path: "/compatible-mode/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: dashscope-secret
    tls:
      sni: dashscope.aliyuncs.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: dashscope
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /dashscope
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: dashscope.aliyuncs.com
    backendRefs:
    - name: dashscope
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Moonshot AI

```bash
export MOONSHOT_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: moonshot-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $MOONSHOT_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: moonshot
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: moonshot-v1-8k
        host: api.moonshot.cn
        port: 443
        path: "/v1/chat/completions"
  policies:
    auth:
      secretRef:
        name: moonshot-secret
    tls:
      sni: api.moonshot.cn
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: moonshot
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /moonshot
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.moonshot.cn
    backendRefs:
    - name: moonshot
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Zhipu AI (Z.AI)

```bash
export ZHIPU_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: zhipu-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $ZHIPU_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: zhipu
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: glm-4
        host: open.bigmodel.cn
        port: 443
        path: "/api/paas/v4/chat/completions"
  policies:
    auth:
      secretRef:
        name: zhipu-secret
    tls:
      sni: open.bigmodel.cn
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: zhipu
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /zhipu
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: open.bigmodel.cn
    backendRefs:
    - name: zhipu
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Volcano Engine (ByteDance)

```bash
export VOLC_API_KEY=<your-key>
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: volc-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: $VOLC_API_KEY
EOF

kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: volcengine
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        host: ark.cn-beijing.volces.com
        port: 443
        path: "/api/v3/chat/completions"
  policies:
    auth:
      secretRef:
        name: volc-secret
    tls:
      sni: ark.cn-beijing.volces.com
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: volcengine
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /volcengine
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: ark.cn-beijing.volces.com
    backendRefs:
    - name: volcengine
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

## Local & Self-Hosted Models (In-Cluster)

No TLS or external secrets needed — models run as K8s Services.

### Ollama (In-Cluster)

```bash
# Deploy Ollama
kubectl apply -f- <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  namespace: agentgateway-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
      - name: ollama
        image: ollama/ollama:latest
        ports:
        - containerPort: 11434
---
apiVersion: v1
kind: Service
metadata:
  name: ollama
  namespace: agentgateway-system
spec:
  selector:
    app: ollama
  ports:
  - port: 11434
    targetPort: 11434
EOF

# Backend — no TLS, no auth
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: ollama
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: llama3.2
        host: ollama.agentgateway-system.svc.cluster.local
        port: 11434
        path: "/v1/chat/completions"
EOF

# Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: ollama
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /ollama
    backendRefs:
    - name: ollama
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF

# Test
curl "localhost:8080/ollama" -H content-type:application/json -d '{
  "model": "llama3.2",
  "messages": [{"role": "user", "content": "Hello from Ollama!"}]
}' | jq
```

---

### vLLM (In-Cluster)

```bash
# Deploy vLLM
kubectl apply -f- <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm
  namespace: agentgateway-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm
  template:
    metadata:
      labels:
        app: vllm
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        args: ["--model", "meta-llama/Llama-3.1-8B-Instruct"]
        ports:
        - containerPort: 8000
        resources:
          limits:
            nvidia.com/gpu: 1
---
apiVersion: v1
kind: Service
metadata:
  name: vllm
  namespace: agentgateway-system
spec:
  selector:
    app: vllm
  ports:
  - port: 8000
    targetPort: 8000
EOF

# Backend
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: vllm
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        model: meta-llama/Llama-3.1-8B-Instruct
        host: vllm.agentgateway-system.svc.cluster.local
        port: 8000
        path: "/v1/chat/completions"
EOF

# Route
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: vllm
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /vllm
    backendRefs:
    - name: vllm
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### llama.cpp (In-Cluster)

```bash
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: llamacpp
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        host: llamacpp.agentgateway-system.svc.cluster.local
        port: 8080
        path: "/v1/chat/completions"
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: llamacpp
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /llamacpp
    backendRefs:
    - name: llamacpp
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

### Triton Inference Server (In-Cluster)

```bash
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: triton
  namespace: agentgateway-system
spec:
  ai:
    provider:
      openai:
        host: triton.agentgateway-system.svc.cluster.local
        port: 8000
        path: "/v1/chat/completions"
EOF

kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: triton
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /triton
    backendRefs:
    - name: triton
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

---

## Multi-Provider Routing

Route all providers through a single agentgateway proxy with path-based routing.

```bash
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: multi-llm
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  # Default -> OpenAI
  - matches:
    - path:
        type: PathPrefix
        value: /v1/chat/completions
    backendRefs:
    - name: openai
      group: agentgateway.dev
      kind: AgentgatewayBackend
  # Native providers
  - matches:
    - path:
        type: PathPrefix
        value: /openai
    backendRefs:
    - name: openai
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /anthropic
    backendRefs:
    - name: anthropic
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /gemini
    backendRefs:
    - name: gemini
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /bedrock
    backendRefs:
    - name: bedrock
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /vertex
    backendRefs:
    - name: vertex-ai
      group: agentgateway.dev
      kind: AgentgatewayBackend
  # OpenAI-compatible providers
  - matches:
    - path:
        type: PathPrefix
        value: /mistral
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.mistral.ai
    backendRefs:
    - name: mistral
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /deepseek
    backendRefs:
    - name: deepseek
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /groq
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.groq.com
    backendRefs:
    - name: groq
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /together
    filters:
    - type: URLRewrite
      urlRewrite:
        hostname: api.together.xyz
    backendRefs:
    - name: together
      group: agentgateway.dev
      kind: AgentgatewayBackend
  - matches:
    - path:
        type: PathPrefix
        value: /ollama
    backendRefs:
    - name: ollama
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

**Test multi-provider routing:**
```bash
# Route to OpenAI
curl "localhost:8080/openai" -H content-type:application/json \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Hi"}]}' | jq

# Route to Anthropic
curl "localhost:8080/anthropic" -H content-type:application/json \
  -d '{"model":"claude-sonnet-4-20250514","messages":[{"role":"user","content":"Hi"}]}' | jq

# Route to Groq
curl "localhost:8080/groq" -H content-type:application/json \
  -d '{"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"Hi"}]}' | jq

# Route to Ollama (local)
curl "localhost:8080/ollama" -H content-type:application/json \
  -d '{"model":"llama3.2","messages":[{"role":"user","content":"Hi"}]}' | jq
```

---

## Quick Reference Table

| Provider | Type | Host | Path | TLS |
|---|---|---|---|---|
| **OpenAI** | Native `openai:` | (default) | (auto) | auto |
| **Anthropic** | Native `anthropic:` | (default) | (auto) | auto |
| **Bedrock** | Native `bedrock:` | (default) | (auto) | auto |
| **Gemini** | Native `gemini:` | (default) | (auto) | auto |
| **Vertex AI** | Native `vertexai:` | (default) | (auto) | auto |
| **Azure OpenAI** | OpenAI-compat | `your-resource.openai.azure.com` | `/openai/deployments/...` | `sni` |
| **Mistral** | OpenAI-compat | `api.mistral.ai` | `/v1/chat/completions` | `sni` |
| **DeepSeek** | OpenAI-compat | `api.deepseek.com` | `/v1/chat/completions` | `sni` |
| **xAI (Grok)** | OpenAI-compat | `api.x.ai` | `/v1/chat/completions` | `sni` |
| **Groq** | OpenAI-compat | `api.groq.com` | `/openai/v1/chat/completions` | `sni` |
| **Cohere** | OpenAI-compat | `api.cohere.ai` | `/compatibility/v1/chat/completions` | `sni` |
| **Together AI** | OpenAI-compat | `api.together.xyz` | `/v1/chat/completions` | `sni` |
| **Fireworks AI** | OpenAI-compat | `api.fireworks.ai` | `/inference/v1/chat/completions` | `sni` |
| **Perplexity** | OpenAI-compat | `api.perplexity.ai` | `/chat/completions` | `sni` |
| **OpenRouter** | OpenAI-compat | `openrouter.ai` | `/api/v1/chat/completions` | `sni` |
| **Cerebras** | OpenAI-compat | `api.cerebras.ai` | `/v1/chat/completions` | `sni` |
| **SambaNova** | OpenAI-compat | `api.sambanova.ai` | `/v1/chat/completions` | `sni` |
| **DeepInfra** | OpenAI-compat | `api.deepinfra.com` | `/v1/openai/chat/completions` | `sni` |
| **HuggingFace** | OpenAI-compat | `api-inference.huggingface.co` | `/v1/chat/completions` | `sni` |
| **Nvidia NIM** | OpenAI-compat | `integrate.api.nvidia.com` | `/v1/chat/completions` | `sni` |
| **Replicate** | OpenAI-compat | `api.replicate.com` | `/v1/chat/completions` | `sni` |
| **AI21** | OpenAI-compat | `api.ai21.com` | `/studio/v1/chat/completions` | `sni` |
| **Cloudflare** | OpenAI-compat | `api.cloudflare.com` | `/client/v4/accounts/.../ai/v1/chat/completions` | `sni` |
| **Lambda AI** | OpenAI-compat | `api.lambdalabs.com` | `/v1/chat/completions` | `sni` |
| **Nebius** | OpenAI-compat | `api.studio.nebius.com` | `/v1/chat/completions` | `sni` |
| **Novita AI** | OpenAI-compat | `api.novita.ai` | `/v3/openai/chat/completions` | `sni` |
| **Hyperbolic** | OpenAI-compat | `api.hyperbolic.xyz` | `/v1/chat/completions` | `sni` |
| **Databricks** | OpenAI-compat | `<ws>.cloud.databricks.com` | `/serving-endpoints/.../invocations` | `sni` |
| **GitHub Models** | OpenAI-compat | `models.inference.ai.azure.com` | `/chat/completions` | `sni` |
| **Scaleway** | OpenAI-compat | `api.scaleway.ai` | `/v1/chat/completions` | `sni` |
| **Dashscope** | OpenAI-compat | `dashscope.aliyuncs.com` | `/compatible-mode/v1/chat/completions` | `sni` |
| **Moonshot** | OpenAI-compat | `api.moonshot.cn` | `/v1/chat/completions` | `sni` |
| **Zhipu AI** | OpenAI-compat | `open.bigmodel.cn` | `/api/paas/v4/chat/completions` | `sni` |
| **Volcano Engine** | OpenAI-compat | `ark.cn-beijing.volces.com` | `/api/v3/chat/completions` | `sni` |
| **Ollama** | Local | `ollama.svc:11434` | `/v1/chat/completions` | none |
| **vLLM** | Local | `vllm.svc:8000` | `/v1/chat/completions` | none |
| **llama.cpp** | Local | `llamacpp.svc:8080` | `/v1/chat/completions` | none |
| **Triton** | Local | `triton.svc:8000` | `/v1/chat/completions` | none |

---

## References

- [Agentgateway K8s Provider Docs](https://agentgateway.dev/docs/kubernetes/latest/llm/providers)
- [OpenAI-Compatible Provider Guide](https://agentgateway.dev/docs/kubernetes/latest/llm/providers/openai-compatible)
- [Multiple Endpoints Guide](https://agentgateway.dev/docs/kubernetes/latest/llm/providers/multiple-endpoints)
- [Agentgateway GitHub](https://github.com/agentgateway/agentgateway)
- [kgateway Docs](https://kgateway.dev/docs/agentgateway/latest)
- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/)
