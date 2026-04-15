# gRPC + Istio: Stale Connection Issue with Headless Services

## Problem Description

When a gRPC client calls an upstream service exposed via a **headless Kubernetes Service** (`clusterIP: None`) and Istio sidecar injection is enabled, bouncing the upstream pods causes persistent call failures. The same setup works without the service mesh.

**Why it fails:**

| Factor | Detail |
|--------|--------|
| Headless service | DNS returns individual pod IPs instead of a stable ClusterIP VIP |
| gRPC / HTTP2 | Long-lived multiplexed connections are reused; the gRPC client does not re-resolve DNS on every call |
| Istio passthrough | For headless services, Envoy uses `ORIGINAL_DST` passthrough — it routes to whatever IP the client resolved |
| Pod bounce | New pods get new IPs; the old pod IP is gone |
| Net result | Envoy forwards to the dead IP, the TCP handshake fails, and gRPC calls error out until the client is restarted or the connection is forcibly dropped |

Without Istio the same issue exists, but vanilla gRPC-go's built-in backoff reconnects directly to a new pod IP after DNS TTL expiry. With Istio, the intercepted connection stays dead longer because Envoy's passthrough path doesn't apply its own endpoint health checks.

---

## Repository Layout

```
istiogrpc/
├── README.md
├── k8s/
│   ├── namespace.yaml
│   └── destination-rule-fix.yaml   # applied in Phase 3 to confirm the fix
├── server/
│   ├── main.go
│   ├── go.mod
│   ├── Dockerfile
│   ├── pb/
│   │   └── greeting.proto
│   └── k8s/
│       ├── deployment.yaml
│       └── service.yaml            # headless (clusterIP: None)
└── client/
    ├── main.go
    ├── go.mod
    ├── Dockerfile
    ├── pb/
    │   └── greeting.proto
    └── k8s/
        └── deployment.yaml
```

---

## Test Environment

This issue was reproduced on the following environment. All details are provided to help the upstream OSS Istio community reproduce and investigate.

| Component | Version / Detail |
|-----------|-----------------|
| **Cloud** | Microsoft Azure — region `westus` |
| **AKS** | Kubernetes server `v1.34.4` |
| **kubectl client** | `v1.33.3` |
| **Azure Service Mesh addon** | `1.0.0-v20260317-addon-260321-1` (Helm chart) |
| **Istio revision** | `asm-1-27` |
| **Istio control plane (istiod)** | `mcr.microsoft.com/oss/v2/istio/pilot:v1.27.7-1` |
| **Istio data plane (sidecar proxy / Envoy)** | `mcr.microsoft.com/oss/v2/istio/proxyv2:v1.27.7-1` |
| **Node OS** | Ubuntu 22.04.5 LTS |
| **Kernel** | `5.15.0-1102-azure` |
| **Container runtime** | `containerd://1.7.30-2` |
| **Node SKU** | `Standard_D4s_v3` (2 nodes) |
| **Network plugin** | Azure CNI (`azure`) |
| **gRPC server** | Go `google.golang.org/grpc v1.63.2`, 3 replicas |
| **gRPC client** | Go `google.golang.org/grpc v1.63.2`, passthrough resolver, no `round_robin` policy |
| **Upstream service type** | Headless (`clusterIP: None`) |

> The Azure Service Mesh addon distributes Istio `1.27.x` builds. The underlying Istio upstream version is **1.27.7**. The passthrough/ORIGINAL_DST behavior for headless services is standard upstream Istio behavior and is not specific to the AKS addon.

---

## Prerequisites

- Azure CLI (`az`) ≥ 2.56 with `aks-preview` extension
- `kubectl`
- `helm` (optional, for manual Istio inspection)
- Access to the `srinmantest` Azure Container Registry

```bash
az extension add --name aks-preview
az extension update --name aks-preview
```

---

## Step 1 — Create Resource Group and AKS Cluster

```bash
export RG="rg-istiogrpc-demo"
export CLUSTER="aks-istiogrpc"
export LOCATION="westus"
export ACR="srinmantest"

az group create --name $RG --location $LOCATION

az aks create \
  --resource-group $RG \
  --name $CLUSTER \
  --node-count 2 \
  --node-vm-size Standard_D4s_v3 \
  --network-plugin azure \
  --generate-ssh-keys \
  --attach-acr $ACR

# Fetch credentials
az aks get-credentials --resource-group $RG --name $CLUSTER --overwrite-existing
kubectl get nodes
```

> **Note:** `--attach-acr` grants the cluster's managed identity `AcrPull` on the registry so nodes can pull images without separate credentials.

---

## Step 2 — Build and Push Container Images

From the repository root (`istiogrpc/`):

```bash
# Build and push gRPC server
az acr build \
  --registry $ACR \
  --image grpc-server:latest \
  ./server

# Build and push gRPC client
az acr build \
  --registry $ACR \
  --image grpc-client:latest \
  ./client
```

Both Dockerfiles use a multi-stage build: the builder stage installs `protoc` and the Go plugins, generates `.pb.go` files, then compiles a static binary. The final stage is a minimal Alpine image.

Verify images exist:

```bash
az acr repository list --name $ACR --output table
az acr repository show-tags --name $ACR --repository grpc-server --output table
az acr repository show-tags --name $ACR --repository grpc-client --output table
```

---

## Phase 1 — Test WITHOUT Istio

### Step 3 — Deploy the Namespace and Services

```bash
# Create namespace (no Istio injection label yet)
kubectl apply -f k8s/namespace.yaml

# Deploy the upstream (server) — 3 replicas, headless service
kubectl apply -f server/k8s/deployment.yaml
kubectl apply -f server/k8s/service.yaml

# Deploy the calling (client) — 1 replica, polls server every second
kubectl apply -f client/k8s/deployment.yaml

kubectl -n grpc-demo rollout status deployment/grpc-server
kubectl -n grpc-demo rollout status deployment/grpc-client
```

### Step 4 — Verify Headless DNS Resolution

The headless service should return one A record per pod:

```bash
# Run a one-shot DNS lookup inside the cluster
kubectl run -it --rm dns-test --image=busybox:1.36 --restart=Never -n grpc-demo -- \
  nslookup grpc-server.grpc-demo.svc.cluster.local
```

Expected output — multiple A records (one per pod):

```
Name:      grpc-server.grpc-demo.svc.cluster.local
Address 1: 10.244.0.12 grpc-server-xxxx-1.grpc-server.grpc-demo.svc.cluster.local
Address 2: 10.244.0.13 grpc-server-xxxx-2.grpc-server.grpc-demo.svc.cluster.local
Address 3: 10.244.1.7  grpc-server-xxxx-3.grpc-server.grpc-demo.svc.cluster.local
```

### Step 5 — Confirm Client is Calling Successfully (No Mesh)

```bash
kubectl -n grpc-demo logs -l app=grpc-client -f
```

Expected — steady stream of `OK` lines, spread across all three server pods:

```
[#1] OK  server_ip=10.244.0.12  hostname=grpc-server-xxx-1 ts=2026-04-15T10:00:01Z
[#2] OK  server_ip=10.244.0.13  hostname=grpc-server-xxx-2 ts=2026-04-15T10:00:02Z
...
```

### Step 6 — Bounce the Upstream Pods (No Mesh)

Open a second terminal and watch the client logs continuously, then in another terminal:

```bash
kubectl -n grpc-demo rollout restart deployment/grpc-server
```

**Observe:** The client may log a brief burst of errors (a few seconds) while pods restart, but **recovers on its own** once gRPC reconnects and CoreDNS updates. This is the baseline healthy behavior.

---

## Phase 2 — Enable Istio and Reproduce the Failure

### Step 7 — Enable Azure Service Mesh (Istio) on AKS

```bash
az aks mesh enable --resource-group $RG --name $CLUSTER

# Confirm the addon is Running
az aks show --resource-group $RG --name $CLUSTER \
  --query serviceMeshProfile -o json
```

Get the installed Istio revision (needed for namespace labeling):

```bash
REVISION=$(kubectl get configmap -n aks-istio-system \
  -o jsonpath='{.items[0].metadata.labels.istio\.io/rev}' 2>/dev/null || \
  az aks show --resource-group $RG --name $CLUSTER \
    --query 'serviceMeshProfile.istio.revisions[0]' -o tsv)

echo "Istio revision: $REVISION"
```

### Step 8 — Enable Sidecar Injection on the Namespace

```bash
# Label the namespace to trigger automatic sidecar injection
kubectl label namespace grpc-demo istio.io/rev=$REVISION --overwrite

# Restart all pods so sidecars are injected
kubectl -n grpc-demo rollout restart deployment/grpc-server
kubectl -n grpc-demo rollout restart deployment/grpc-client

kubectl -n grpc-demo rollout status deployment/grpc-server
kubectl -n grpc-demo rollout status deployment/grpc-client
```

Confirm each pod now has 2 containers (app + istio-proxy):

```bash
kubectl -n grpc-demo get pods
# Each pod should show READY 2/2
```

### Step 9 — Confirm Steady State Under Istio (Before Bounce)

```bash
kubectl -n grpc-demo logs -l app=grpc-client -c grpc-client -f
```

Calls succeed, but **all requests go to the same single pod IP** — every line will show the same `server_ip` and `hostname`. This is the first visible symptom of the problem: Istio's passthrough model locks the connection to whichever pod IP was resolved at dial time. None of the other two server pods receive any traffic.

```
2026/04/15 20:21:29 [#214] OK  server_ip=10.224.0.35  hostname=grpc-server-xxx-427j6 ts=...
2026/04/15 20:21:30 [#215] OK  server_ip=10.224.0.35  hostname=grpc-server-xxx-427j6 ts=...
2026/04/15 20:21:31 [#216] OK  server_ip=10.224.0.35  hostname=grpc-server-xxx-427j6 ts=...
```

### Step 10 — Reproduce the Failure: Bounce Upstream Pods

In one terminal, tail the client logs:

```bash
kubectl -n grpc-demo logs -l app=grpc-client -c grpc-client -f
```

In a second terminal, bounce the server:

```bash
kubectl -n grpc-demo rollout restart deployment/grpc-server
```

**Observe:** Unlike Phase 1, after the old pod IP becomes unreachable the client logs a **continuous stream of errors** that do NOT self-heal. The error message originates from the Envoy sidecar (not the gRPC library), and the call interval widens as gRPC's exponential backoff kicks in:

```
2026/04/15 20:22:51 [#296] ERROR (failures=1/296): rpc error: code = Unavailable
  desc = upstream connect error or disconnect/reset before headers.
  retried and the latest reset reason: remote connection failure,
  transport failure reason: delayed connect error: No route to host
2026/04/15 20:22:52 [#297] ERROR (failures=2/297): rpc error: code = Unavailable ...
2026/04/15 20:22:53 [#298] ERROR (failures=3/298): rpc error: code = Unavailable ...
2026/04/15 20:22:55 [#299] ERROR (failures=4/299): rpc error: code = Unavailable ...
2026/04/15 20:22:59 [#300] ERROR (failures=5/300): rpc error: code = Unavailable ...
```

Key observations:
- Error is **`No route to host`** (EHOSTUNREACH), not `connection refused` — Envoy is forwarding to the dead pod IP and the network itself rejects it
- Calls are **1-per-second at first**, then space out to every 3-4 seconds as gRPC's backoff increases
- The failure count never resets — errors continue indefinitely until the client is restarted

The client pod must be restarted to recover:

```bash
kubectl -n grpc-demo rollout restart deployment/grpc-client
```

---

## Root Cause Analysis

```
  grpc-client pod                  Istio sidecar (Envoy)        grpc-server pod
  ─────────────                    ──────────────────────────   ─────────────────
  Dial("grpc-server:50051")
    → DNS → 10.244.0.12 (pod A)
    → TCP connect to :15001 (intercepted by iptables)
                                   ORIGINAL_DST = 10.244.0.12
                                   → forwards to 10.244.0.12:50051  ← Pod A serving

  [kubectl rollout restart]
                                                                 Pod A DELETED
                                                                 Pod A' created → 10.244.0.55

  grpc call #N
    → reuses existing HTTP/2 connection (no re-dial)
                                   ORIGINAL_DST = 10.244.0.12 (stale)
                                   → tries 10.244.0.12:50051    ← IP GONE → ECONNREFUSED

  gRPC client receives Unavailable
  but passthrough Envoy has no
  health-check on 10.244.0.12 →
  never marks it dead →
  every subsequent call fails.
```

**Key difference vs. no-mesh:** Without Istio, gRPC-go's transport layer gets the TCP RST directly, triggers a backoff reconnect, re-resolves DNS (returns Pod A' IP), and recovers within seconds. With Istio passthrough, the same RST arrives but gRPC's reconnect logic still targets `grpc-server:50051`, which Envoy again resolves via `ORIGINAL_DST` to the dead IP — the cycle repeats.

---

## Phase 3 — Apply the Fix

### Option A: DestinationRule (recommended — no code change)

Apply a `DestinationRule` that switches Istio from passthrough to active endpoint management with ROUND_ROBIN:

```bash
kubectl apply -f k8s/destination-rule-fix.yaml
```

Then restart the client to re-establish the gRPC connection under the new policy:

```bash
kubectl -n grpc-demo rollout restart deployment/grpc-client
```

Confirm steady state, then bounce the server again:

```bash
kubectl -n grpc-demo rollout restart deployment/grpc-server
```

**Expected:** The client recovers automatically in a few seconds without needing a restart.

### Option B: Change to Regular (ClusterIP) Service

Convert the headless service to a normal ClusterIP service. Istio then manages load balancing through its own EDS and the stale-IP problem disappears entirely:

```bash
# Edit service.yaml: remove "clusterIP: None"
kubectl apply -f server/k8s/service.yaml
```

> This changes DNS behaviour — clients now get the stable VIP instead of pod IPs — which may affect applications that depend on headless DNS semantics.

### Option C: Use the `dns:///` Resolver in the gRPC Client

Change the client `Dial` address and add the `round_robin` load balancing policy so the gRPC library itself periodically re-resolves DNS and balances across all pod IPs:

```go
conn, err := grpc.Dial(
    "dns:///grpc-server:50051",
    grpc.WithTransportCredentials(insecure.NewCredentials()),
    grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
)
```

This requires a code change but makes the client resilient regardless of whether Istio is present.

---

## Cleanup

```bash
kubectl delete namespace grpc-demo

# To remove the Istio addon
az aks mesh disable --resource-group $RG --name $CLUSTER

# To delete the cluster entirely
az aks delete --resource-group $RG --name $CLUSTER --yes --no-wait
az group delete --name $RG --yes --no-wait
```
