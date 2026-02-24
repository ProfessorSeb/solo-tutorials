Step 1: Create a kind cluster 
Create a local Kubernetes cluster with kind. This cluster is where you will install agentgateway.

kind create cluster --name agentgateway

Example output:

Creating cluster "agentgateway" ...
 ✓ Ensuring node image (kindest/node:v1.32.0) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-agentgateway"

Verify the cluster is running:

kubectl cluster-info --context kind-agentgateway
kubectl get nodes