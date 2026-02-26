# Vertex AI — GCP Service Account Credentials in Agentgateway

Deep dive into how agentgateway supports GCP service account credentials for Vertex AI authentication. Based on source code analysis of both [agentgateway OSS](https://github.com/agentgateway/agentgateway) and [agentgateway enterprise](https://github.com/solo-io/agentgateway-enterprise).

---

## TL;DR

**Yes, agentgateway fully supports GCP service account credentials for Vertex AI.** The Vertex AI provider automatically uses GCP Application Default Credentials (ADC) with `AccessToken` type — no explicit auth config is required if valid GCP credentials are available in the environment.

---

## How It Works (Source Code Analysis)

### GCP Auth Implementation

The GCP authentication is implemented in `crates/agentgateway/src/http/auth.rs` (identical in both OSS and enterprise repos):

```rust
pub enum GcpAuth {
    // Fetch an id token
    IdToken {
        type: IdToken,
        audience: Option<String>,  // If not set, destination host is used
    },
    // Fetch an access token (DEFAULT)
    AccessToken {
        type: Option<AccessToken>,
    },
}

impl Default for GcpAuth {
    fn default() -> Self {
        Self::AccessToken { type: Default::default() }
    }
}
```

Two authentication modes:
| Mode | Use Case | Default? |
|------|----------|----------|
| `AccessToken` | Authenticate to GCP services (Vertex AI, Gemini, etc.) | Yes |
| `IdToken` | Authenticate to Cloud Run, custom services | No |

### Vertex AI Auto-Injects GCP Auth

In `crates/agentgateway/src/llm/mod.rs`, the Vertex AI provider automatically configures GCP auth:

```rust
AIProvider::Vertex(p) => {
    let bp = BackendPolicies {
        backend_tls: Some(http::backendtls::SYSTEM_TRUST.clone()),
        backend_auth: Some(BackendAuth::Gcp(GcpAuth::default())),  // <-- Auto GCP AccessToken
        ..Default::default()
    };
    (Target::Hostname(p.get_host(), 443), bp)
},
```

This means **Vertex AI backends always get GCP `AccessToken` auth by default** — you don't need to explicitly configure it.

### Application Default Credentials (ADC) Chain

The GCP auth uses `google_cloud_auth::credentials::Builder::default().build_access_token_credentials()` which follows the standard [Google ADC chain](https://cloud.google.com/docs/authentication/application-default-credentials):

1. **`GOOGLE_APPLICATION_CREDENTIALS` env var** → Points to a service account JSON key file
2. **Well-known ADC path** → `~/.config/gcloud/application_default_credentials.json` (Linux/Mac) or `%APPDATA%/gcloud/application_default_credentials.json` (Windows)
3. **GKE Metadata Server** → Automatically used on GKE (supports Workload Identity and node service accounts)

The ADC resolution code is in `crates/agentgateway/src/http/auth.rs`:

```rust
mod adc {
    fn adc_path() -> Option<PathBuf> {
        if let Ok(path) = std::env::var("GOOGLE_APPLICATION_CREDENTIALS") {
            return Some(path.into());
        }
        Some(adc_well_known_path()?.into())
    }

    fn adc_well_known_path() -> Option<String> {
        std::env::var("HOME")
            .ok()
            .map(|root| root + "/.config/gcloud/application_default_credentials.json")
    }
}
```

### K8s CRD Support

The `AgentgatewayPolicy` CRD supports explicit GCP auth configuration:

```yaml
# From controller/api/v1alpha1/agentgateway/agentgateway_policy_types.go
type GcpAuth struct {
    Type     *GcpAuthType `json:"type,omitempty"`      # AccessToken or IdToken
    Audience *ShortString `json:"audience,omitempty"`   # Only valid with IdToken
}
```

CRD validation ensures `audience` is only set with `IdToken`:
```yaml
x-kubernetes-validations:
- message: audience is only valid with IdToken
  rule: 'has(self.audience) ? self.type == ''IdToken'' : true'
```

---

## Configuration Methods

### Method 1: GKE Workload Identity (Recommended for Production)

The most secure approach — no key files needed. The GKE pod's Kubernetes service account is mapped to a GCP IAM service account.

```bash
# 1. Enable Workload Identity on your GKE cluster
gcloud container clusters update CLUSTER_NAME \
  --workload-pool=PROJECT_ID.svc.id.goog

# 2. Create a GCP service account for Vertex AI
gcloud iam service-accounts create agentgateway-vertex \
  --display-name="Agentgateway Vertex AI"

# 3. Grant the Vertex AI User role
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:agentgateway-vertex@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# 4. Bind the GCP SA to the K8s SA
gcloud iam service-accounts add-iam-policy-binding \
  agentgateway-vertex@PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:PROJECT_ID.svc.id.goog[agentgateway-system/agentgateway]"

# 5. Annotate the K8s service account
kubectl annotate serviceaccount agentgateway \
  --namespace agentgateway-system \
  iam.gke.io/gcp-service-account=agentgateway-vertex@PROJECT_ID.iam.gserviceaccount.com
```

The agentgateway test data shows IAM annotations support in `AgentgatewayParameters`:

```yaml
# From controller/test/deployer/testdata/agentgateway-sa-iam-annotations.yaml
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayParameters
metadata:
  name: sa-iam-agwp
  namespace: default
spec:
  serviceAccount:
    metadata:
      annotations:
        # For AWS EKS IRSA:
        eks.amazonaws.com/role-arn: "arn:aws:iam::123456789012:role/agentgateway-role"
        # For GKE Workload Identity, use:
        # iam.gke.io/gcp-service-account: "agentgateway-vertex@PROJECT_ID.iam.gserviceaccount.com"
```

Then create the Vertex AI backend — **no Secret or auth policy needed**:

```bash
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
        model: gemini-2.0-flash
        projectId: "my-gcp-project"
        region: "us-central1"
---
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
  - backendRefs:
    - name: vertex-ai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

### Method 2: Service Account JSON Key File (Standalone or K8s)

Mount a GCP service account key file and set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

```bash
# 1. Create the service account and download the key
gcloud iam service-accounts create agentgateway-vertex \
  --display-name="Agentgateway Vertex AI"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:agentgateway-vertex@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud iam service-accounts keys create vertex-sa-key.json \
  --iam-account=agentgateway-vertex@PROJECT_ID.iam.gserviceaccount.com

# 2. Create K8s secret from the key file
kubectl create secret generic gcp-sa-key \
  --namespace agentgateway-system \
  --from-file=key.json=vertex-sa-key.json

# 3. Deploy with the mounted key
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayParameters
metadata:
  name: vertex-params
  namespace: agentgateway-system
spec:
  deployment:
    spec:
      template:
        spec:
          containers:
          - name: agentgateway
            env:
            - name: GOOGLE_APPLICATION_CREDENTIALS
              value: /var/secrets/google/key.json
            volumeMounts:
            - name: gcp-sa-key
              mountPath: /var/secrets/google
              readOnly: true
          volumes:
          - name: gcp-sa-key
            secret:
              secretName: gcp-sa-key
---
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: vertex-ai
  namespace: agentgateway-system
spec:
  ai:
    provider:
      vertexai:
        model: gemini-2.0-flash
        projectId: "my-gcp-project"
        region: "us-central1"
---
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
  - backendRefs:
    - name: vertex-ai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

### Method 3: API Key via K8s Secret (Current Docs Approach)

This is what the [official docs](https://agentgateway.dev/docs/kubernetes/latest/llm/providers/vertex/) currently show:

```bash
kubectl apply -f- <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: vertex-ai-secret
  namespace: agentgateway-system
type: Opaque
stringData:
  Authorization: "Bearer YOUR_API_KEY"
---
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
---
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
  - backendRefs:
    - name: vertex-ai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

### Method 4: Explicit GCP Auth Policy via AgentgatewayPolicy

Use an `AgentgatewayPolicy` to explicitly configure GCP auth with `AccessToken` or `IdToken`:

```bash
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
        model: gemini-2.0-flash
        projectId: "my-gcp-project"
        region: "us-central1"
---
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata:
  name: vertex-gcp-auth
  namespace: agentgateway-system
spec:
  targetRefs:
  - kind: HTTPRoute
    name: vertex-ai
    group: gateway.networking.k8s.io
  backend:
    auth:
      gcp:
        type: AccessToken
---
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
  - backendRefs:
    - name: vertex-ai
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

For IdToken (e.g., routing through Cloud Run):

```yaml
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata:
  name: vertex-gcp-id-token
  namespace: agentgateway-system
spec:
  targetRefs:
  - kind: HTTPRoute
    name: vertex-ai
    group: gateway.networking.k8s.io
  backend:
    auth:
      gcp:
        type: IdToken
        audience: "https://my-vertex-proxy.run.app"
```

### Method 5: Standalone Configuration

For standalone (non-K8s) agentgateway, configure the Vertex AI provider in your config file:

```yaml
# agentgateway config
listeners:
  - name: llm
    port: 8080
    routes:
      - name: vertex
        provider:
          vertex:
            model: gemini-2.0-flash
            vertex_project: my-gcp-project
            vertex_region: us-central1
        # Option A: Explicit GCP auth (AccessToken is default)
        policies:
          backend_auth:
            gcp: {}

        # Option B: With IdToken
        # policies:
        #   backend_auth:
        #     gcp:
        #       type: idToken
        #       audience: "https://my-service.run.app"

        # Option C: No backend_auth needed — Vertex auto-injects GCP AccessToken auth
```

For standalone, make sure one of these is available:
```bash
# Option 1: Service account key file
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Option 2: gcloud user credentials (dev only)
gcloud auth application-default login

# Option 3: Running on GCE/GKE — automatic via metadata server
```

---

## Comparison: Auth Methods for Vertex AI

| Method | Security | Rotation | Best For |
|--------|----------|----------|----------|
| GKE Workload Identity | Highest | Automatic | GKE production |
| SA JSON Key + `GOOGLE_APPLICATION_CREDENTIALS` | Medium | Manual | Non-GKE K8s, standalone |
| API Key via K8s Secret | Low | Manual | Quick testing |
| `gcloud auth application-default login` | Low | Automatic | Local development |
| GCE Metadata Server (node SA) | High | Automatic | GCE/GKE without Workload Identity |

---

## Anthropic Models on Vertex AI

Agentgateway automatically detects and routes Anthropic Claude models on Vertex AI. The model name normalization converts date suffixes (e.g., `claude-sonnet-4-5-20251001` → `claude-sonnet-4-5@20251001`):

```bash
kubectl apply -f- <<EOF
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayBackend
metadata:
  name: vertex-claude
  namespace: agentgateway-system
spec:
  ai:
    provider:
      vertexai:
        model: claude-sonnet-4-5-20251001
        projectId: "my-gcp-project"
        region: "us-east5"
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: vertex-claude
  namespace: agentgateway-system
spec:
  parentRefs:
  - name: agentgateway-proxy
    namespace: agentgateway-system
  rules:
  - backendRefs:
    - name: vertex-claude
      namespace: agentgateway-system
      group: agentgateway.dev
      kind: AgentgatewayBackend
EOF
```

Agentgateway handles:
- Routing to the correct Anthropic publisher endpoint on Vertex AI
- Adding `anthropic_version` header (`vertex-2023-10-16`)
- Stripping the `model` field from the request body (required by Vertex AI Anthropic API)
- Converting model name format (e.g., `claude-sonnet-4-5-20251001` → `claude-sonnet-4-5@20251001`)

Supported model name formats:
| Input Format | Normalized Output |
|---|---|
| `claude-sonnet-4-5-20251001` | `claude-sonnet-4-5@20251001` |
| `anthropic/claude-haiku-4-5-20251001` | `claude-haiku-4-5@20251001` |
| `publishers/anthropic/models/claude-sonnet-4-5-20251001` | `claude-sonnet-4-5@20251001` |
| `claude-opus-4-6` (no date) | `claude-opus-4-6` |
| `claude-3-5-sonnet-20241022` (legacy) | `claude-3-5-sonnet@20241022` |

---

## Troubleshooting

### "Failed to initialize credentials"
The GCP ADC chain couldn't find valid credentials. Ensure one of these is configured:
```bash
# Check if GOOGLE_APPLICATION_CREDENTIALS is set
echo $GOOGLE_APPLICATION_CREDENTIALS

# Check if ADC exists at default path
cat ~/.config/gcloud/application_default_credentials.json

# On GKE, check Workload Identity is enabled
kubectl describe serviceaccount agentgateway -n agentgateway-system
```

### "No region found" errors
Vertex AI requires a region. Make sure `region` is set in the `VertexAIConfig`:
```yaml
vertexai:
  projectId: "my-project"
  region: "us-central1"  # Required
```

### Token type mismatch
If routing through Cloud Run or a custom service, use `IdToken` instead of the default `AccessToken`:
```yaml
backend:
  auth:
    gcp:
      type: IdToken
      audience: "https://my-service.run.app"
```

---

## Source Code References

| File | What It Contains |
|------|------------------|
| `crates/agentgateway/src/http/auth.rs` | `GcpAuth` enum, ADC resolution, token insertion |
| `crates/agentgateway/src/llm/vertex.rs` | Vertex AI provider (model, region, project_id) |
| `crates/agentgateway/src/llm/mod.rs` | Auto-injection of GCP auth for Vertex backends |
| `controller/api/v1alpha1/agentgateway/agentgateway_policy_types.go` | K8s CRD types for `GcpAuth` |
| `controller/pkg/agentgateway/plugins/backend_policies.go` | K8s → agentgateway GCP auth translation |
| `controller/install/helm/agentgateway-crds/templates/agentgateway.dev_agentgatewaybackends.yaml` | CRD schema with GCP auth validation |
