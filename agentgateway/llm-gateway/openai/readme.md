# OpenAI with agentgateway on kind

Follow these steps after completing Step 1 (kind cluster setup).

## Step 2: Install the Kubernetes Gateway API CRDs

Install the custom resources for the Kubernetes Gateway API.

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/standard-install.yaml
```

Example output:

```text
customresourcedefinition.apiextensions.k8s.io/gatewayclasses.gateway.networking.k8s.io created
customresourcedefinition.apiextensions.k8s.io/gateways.gateway.networking.k8s.io created
customresourcedefinition.apiextensions.k8s.io/httproutes.gateway.networking.k8s.io created
customresourcedefinition.apiextensions.k8s.io/referencegrants.gateway.networking.k8s.io created
customresourcedefinition.apiextensions.k8s.io/grpcroutes.gateway.networking.k8s.io created
```

## Step 3: Install agentgateway CRDs

Deploy the agentgateway CRDs using Helm. This creates the `agentgateway-system` namespace and installs the custom resource definitions.

```bash
helm upgrade -i --create-namespace \
  --namespace agentgateway-system \
  --version v2.2.1 agentgateway-crds oci://ghcr.io/kgateway-dev/charts/agentgateway-crds
```

## Step 4: Install the agentgateway control plane

Install the agentgateway control plane with Helm.

```bash
helm upgrade -i -n agentgateway-system agentgateway oci://ghcr.io/kgateway-dev/charts/agentgateway \
  --version v2.2.1
```

Verify that the control plane is running:

```bash
kubectl get pods -n agentgateway-system
```

Example output:

```text
NAME                              READY   STATUS    RESTARTS   AGE
agentgateway-78658959cd-cz6jt     1/1     Running   0          12s
```

Verify that the `GatewayClass` was created:

```bash
kubectl get gatewayclass agentgateway
```

## Step 5: Create a Gateway

Create a `Gateway` resource that sets up the agentgateway proxy with an HTTP listener.

```bash
kubectl apply -f- <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: agentgateway-proxy
  namespace: agentgateway-system
spec:
  gatewayClassName: agentgateway
  listeners:
  - protocol: HTTP
    port: 80
    name: http
    allowedRoutes:
      namespaces:
        from: All
EOF
```

Wait for the `Gateway` and its proxy deployment to become ready:

```bash
kubectl get gateway agentgateway-proxy -n agentgateway-system
kubectl get deployment agentgateway-proxy -n agentgateway-system
```

Example output:

```text
NAME                 CLASS            ADDRESS   PROGRAMMED   AGE
agentgateway-proxy   agentgateway                True         30s

NAME                 READY   UP-TO-DATE   AVAILABLE   AGE
agentgateway-proxy   1/1     1            1           32s
```

## Step 6: Configure OpenAI as the LLM provider

### Set your API key

```bash
export OPENAI_API_KEY=<insert-your-api-key>
```

### Create the Kubernetes secret

```bash
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
```

### Create the LLM backend

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
        model: gpt-4.1-nano
  policies:
    auth:
      secretRef:
        name: openai-secret
EOF
```

### Create the HTTPRoute

```bash
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
    - backendRefs:
      - name: openai
        namespace: agentgateway-system
        group: agentgateway.dev
        kind: AgentgatewayBackend
EOF
```

## Step 7: Test the API

Set up port-forwarding to access the agentgateway proxy from your local machine:

```bash
kubectl port-forward deployment/agentgateway-proxy -n agentgateway-system 8080:80 &
```

Send a request to OpenAI through agentgateway:

```bash
curl "localhost:8080/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1-nano",
    "messages": [{"role": "user", "content": "Hello! What is Kubernetes in one sentence?"}]
  }' | jq
```

Example output:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Kubernetes is an open-source container orchestration platform that automates the deployment, scaling, and management of containerized applications."
      },
      "index": 0,
      "finish_reason": "stop"
    }
  ]
}
```

## Cleanup

When you are done, stop port-forwarding and delete the kind cluster:

```bash
# Stop port-forward (if running in background)
kill %1 2>/dev/null

# Delete the kind cluster
kind delete cluster --name agentgateway
```
