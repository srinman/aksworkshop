
# Lab: Istio Advanced Traffic Management

## Overview
In this comprehensive lab, you will master Istio's traffic management capabilities through hands-on exercises. You'll learn how to:

- **Understand core traffic management components**: Gateway, VirtualService, and DestinationRule
- **Implement sophisticated routing strategies**: Header-based, weight-based, and path-based routing
- **Configure locality-aware load balancing** across multiple availability zones
- **Manage traffic policies**: Circuit breakers, retries, and timeouts
- **Compare external vs internal traffic routing** patterns
- **Apply advanced deployment patterns**: Canary deployments and blue-green deployments

## Prerequisites
- AKS cluster with Istio add-on enabled across **3 availability zones**
- External ingress gateway configured and operational
- Access logging enabled for observability
- Basic understanding of Kubernetes services and deployments

## 🏗️ Understanding Istio Traffic Management Components

### 🌐 Gateway
- **Purpose**: Defines entry points for external traffic into the service mesh
- **Scope**: Edge of the mesh, configures load balancer settings
- **Function**: Opens network ports and defines acceptable hostnames

### 🚦 VirtualService  
- **Purpose**: Defines routing rules and traffic manipulation
- **Scope**: Can work with Gateway (external) or standalone (internal)
- **Function**: Controls where requests go based on headers, paths, weights

### 🎯 DestinationRule
- **Purpose**: Defines policies for traffic **after** routing decisions
- **Scope**: Applies to service subsets and traffic policies
- **Function**: Load balancing, circuit breakers, TLS settings, subsets

### 🔗 How They Work Together
```
External Request → Gateway (entry point) → VirtualService (routing logic) → DestinationRule (traffic policies) → Service Subsets → Pods
```

---

## Part 1: Cluster Setup and Verification

### Step 1.1: Verify Multi-Zone Deployment

First, let's verify that our cluster has nodes distributed across multiple zones:

```bash
# Set environment variables
export CLUSTER=aksistio4
export RESOURCE_GROUP=aksistio4rg
export LOCATION=eastus2

# Create resource group if it doesn't exist
az group delete --name $RESOURCE_GROUP
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create multi-zone cluster with proper parameters
az aks create \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER \
  --location $LOCATION \
  --node-count 2 \
  --zones 1 3 \
  --enable-asm \
  --generate-ssh-keys \
  --node-vm-size Standard_D8s_v3

# Get cluster credentials
az aks get-credentials --resource-group $RESOURCE_GROUP --name $CLUSTER

# Verify node distribution across zones
kubectl get nodes -o custom-columns=NAME:.metadata.name,ZONE:.metadata.labels.'topology\.kubernetes\.io/zone',REGION:.metadata.labels.'topology\.kubernetes\.io/region'
```

📝 **Expected Output**: You should see nodes distributed across zones 1 and 3 in eastus2.

### Step 1.2: Enable External Ingress Gateway

```bash
# Enable external ingress gateway
az aks mesh enable-ingress-gateway \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER \
  --ingress-gateway-type external

# Verify ingress gateway deployment
kubectl get all -n aks-istio-ingress
kubectl get svc -n aks-istio-ingress
```

### Step 1.3: Enable Access Logging

```bash
# Apply global telemetry configuration for access logging
kubectl apply -n aks-istio-system -f - <<EOF
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
  name: mesh-logging-default
spec:
  accessLogging:
  - providers:
    - name: envoy
EOF

# Restart ingress gateway to pick up configuration
kubectl rollout restart deployment/aks-istio-ingressgateway-external-asm-1-25 -n aks-istio-ingress
kubectl rollout status deployment/aks-istio-ingressgateway-external-asm-1-25 -n aks-istio-ingress
```

### Step 1.4: Get External IP

```bash
# Get the external IP for testing
EXTERNAL_IP=$(kubectl get svc aks-istio-ingressgateway-external -n aks-istio-ingress -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "External IP: $EXTERNAL_IP"
```

---

## Part 2: Deploy Multi-Version Test Application

### Step 2.1: Create and Label Namespace

```bash
# Create namespace for our test application
kubectl create namespace testproduct

# Label namespace for sidecar injection (check your Istio revision)
kubectl get namespaces -l istio.io/rev --show-labels
kubectl label namespace testproduct istio.io/rev=asm-1-25

# Verify the label
kubectl get namespace testproduct --show-labels
```

### Step 2.2: Deploy Multi-Version Application

Deploy v1 and v2 versions of our test API with zone affinity:

```bash
kubectl apply -f - <<EOF
# Version 1 Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: testapi-v1
  namespace: testproduct
  labels:
    app: testapi
    version: v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: testapi
      version: v1
  template:
    metadata:
      labels:
        app: testapi
        version: v1
    spec:
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            preference:
              matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values: ["1"]
      containers:
      - name: testapi
        image: srinmantest.azurecr.io/istioapi:v1
        ports:
        - containerPort: 5000
        env:
        - name: VERSION
          value: "v1"
        - name: ZONE_INFO
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
---
# Version 2 Deployment  
apiVersion: apps/v1
kind: Deployment
metadata:
  name: testapi-v2
  namespace: testproduct
  labels:
    app: testapi
    version: v2
spec:
  replicas: 2
  selector:
    matchLabels:
      app: testapi
      version: v2
  template:
    metadata:
      labels:
        app: testapi
        version: v2
    spec:
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            preference:
              matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values: ["3"]
      containers:
      - name: testapi
        image: srinmantest.azurecr.io/istioapi:v2
        ports:
        - containerPort: 5000
        env:
        - name: VERSION
          value: "v2"
        - name: ZONE_INFO
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
---
# Main Service (selects both versions)
apiVersion: v1
kind: Service
metadata:
  name: testapi
  namespace: testproduct
  labels:
    app: testapi
spec:
  ports:
  - port: 80
    name: http
    targetPort: 5000
  selector:
    app: testapi
---
# Version-specific Services  
apiVersion: v1
kind: Service
metadata:
  name: testapi-v1
  namespace: testproduct
  labels:
    app: testapi
    version: v1
spec:
  ports:
  - port: 80
    name: http
    targetPort: 5000
  selector:
    app: testapi
    version: v1
---
apiVersion: v1
kind: Service
metadata:
  name: testapi-v2
  namespace: testproduct
  labels:
    app: testapi
    version: v2
spec:
  ports:
  - port: 80
    name: http
    targetPort: 5000
  selector:
    app: testapi
    version: v2
EOF
```

### Step 2.3: Verify Deployment and Zone Distribution

```bash
# Check deployments
kubectl get deployments -n testproduct

# Verify pods are running with sidecar injection (should show 2/2)
kubectl get pods -n testproduct --show-labels

# Check pod distribution across zones
kubectl get pods -n testproduct -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,VERSION:.metadata.labels.version

# Verify services
kubectl get services -n testproduct

# Check which zones the pods are running in
for pod in $(kubectl get pods -n testproduct -o jsonpath='{.items[*].metadata.name}'); do
  node=$(kubectl get pod $pod -n testproduct -o jsonpath='{.spec.nodeName}')
  zone=$(kubectl get node $node -o jsonpath='{.metadata.labels.topology\.kubernetes\.io/zone}')
  version=$(kubectl get pod $pod -n testproduct -o jsonpath='{.metadata.labels.version}')
  echo "Pod: $pod, Version: $version, Node: $node, Zone: $zone"
done
```

---

## Part 3: Basic Gateway and VirtualService Configuration

### Step 3.1: Create Gateway for External Access

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: testproduct-gateway-external
  namespace: testproduct
spec:
  selector:
    istio: aks-istio-ingressgateway-external
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "istiotraffic.srinman.com"
EOF
```

**🔍 Gateway Explanation:**
- **selector**: Binds to the external ingress gateway pods
- **hosts**: Only accepts requests with this specific Host header
- **port 80**: Listens for HTTP traffic on standard port

### Step 3.2: Create Basic VirtualService (Round-Robin)

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-basic
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  - match:
    - uri:
        exact: /testproduct
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        port:
          number: 80
EOF
```

**🔍 VirtualService Explanation:**
- **hosts**: Must match Gateway configuration
- **gateways**: Links to our Gateway resource
- **rewrite**: Transforms `/testproduct` to `/authors` before forwarding
- **destination**: Routes to the `testapi` service (both v1 and v2 pods)

### Step 3.3: Test Basic Routing

```bash
# Test the basic routing (should round-robin between v1 and v2)
# Repeat this following command multipe times:  
curl -s http://$EXTERNAL_IP/testproduct --header "Host: istiotraffic.srinman.com"

# Check access logs to see the routing
kubectl logs -n aks-istio-ingress -l app=aks-istio-ingressgateway-external --tail=10
```

📝 **Expected Behavior**: You should see requests alternating between v1 and v2 responses.

---

## Part 4: Advanced Traffic Management with DestinationRule

### Step 4.1: Understanding DestinationRule

**DestinationRule Purpose:**
- **Subsets**: Partition service endpoints into named groups
- **Traffic Policies**: Apply load balancing, circuit breakers, TLS settings
- **Post-Routing Configuration**: Applied after VirtualService makes routing decisions

### Step 4.2: Create DestinationRule with Subsets

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: testapi-destination-rule
  namespace: testproduct
spec:
  host: testapi
  trafficPolicy:
    loadBalancer:
      simple: LEAST_REQUEST
  subsets:
  - name: v1
    labels:
      version: v1
    trafficPolicy:
      loadBalancer:
        simple: ROUND_ROBIN
  - name: v2
    labels:
      version: v2
    trafficPolicy:
      loadBalancer:
        simple: RANDOM
EOF
```

**🔍 DestinationRule Explanation:**
- **host**: Applies to the `testapi` service
- **trafficPolicy**: Default load balancing policy (LEAST_REQUEST)
- **subsets**: Define v1 and v2 groups based on version labels
- **subset trafficPolicy**: Override default policy per subset

### Step 4.3: Test Subset-Specific Routing

Create a VirtualService that routes to specific subsets:

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-subsets
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  - match:
    - uri:
        exact: /testproduct-v1
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: v1
        port:
          number: 80
  - match:
    - uri:
        exact: /testproduct-v2
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: v2
        port:
          number: 80
EOF
```

### Step 4.4: Test Subset Routing

```bash
# Test v1 subset routing
curl -s http://$EXTERNAL_IP/testproduct-v1 --header "Host: istiotraffic.srinman.com"


# Test v2 subset routing  
curl -s http://$EXTERNAL_IP/testproduct-v2 --header "Host: istiotraffic.srinman.com"


```

📝 **Expected Results**: 
- `/testproduct-v1` should always return v1
- `/testproduct-v2` should always return v2

---

## Part 5: Header-Based Routing (Canary Testing)

### Step 5.1: Implement Header-Based Routing

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-headers
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  # Route to v2 if canary header is present
  - match:
    - headers:
        x-canary-user:
          exact: "beta-tester"
      uri:
        exact: /testproduct-canary
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: v2
        port:
          number: 80
  # Default route to v1
  - match:
    - uri:
        exact: /testproduct-canary
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: v1
        port:
          number: 80
EOF
```

**🔍 Header-Based Routing Explanation:**
- **Match Priority**: First rule with header match takes precedence
- **Canary Testing**: Beta users get v2, everyone else gets v1
- **Exact Header Match**: Must match `x-canary-user: beta-tester` exactly

### Step 5.2: Test Header-Based Routing

```bash
# Test without canary header (should get v1)
echo "Without canary header (v1 expected):"
curl -s http://$EXTERNAL_IP/testproduct-canary --header "Host: istiotraffic.srinman.com"


# Test with canary header (should get v2)
echo "With canary header (v2 expected):"
curl -s http://$EXTERNAL_IP/testproduct-canary --header "Host: istiotraffic.srinman.com" --header "x-canary-user: beta-tester" 

# Test with wrong header value (should get v1)
echo "With wrong header value (v1 expected):"
curl -s http://$EXTERNAL_IP/testproduct-canary --header "Host: istiotraffic.srinman.com" --header "x-canary-user: regular-user"


```

---

## Part 6: Weight-Based Routing (Blue-Green Deployment)

### Step 6.1: Implement Weight-Based Traffic Splitting

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-weighted
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  - match:
    - uri:
        exact: /testproduct-weighted
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: v1
        port:
          number: 80
      weight: 80
    - destination:
        host: testapi
        subset: v2
        port:
          number: 80
      weight: 20
EOF
```

**🔍 Weight-Based Routing Explanation:**
- **Traffic Split**: 80% to v1, 20% to v2
- **Gradual Rollout**: Allows controlled exposure of new version
- **Total Weight**: Must add up to 100

### Step 6.2: Test Weight-Based Routing

```bash
# Test weighted routing (should see ~80% v1, ~20% v2)
echo "Testing weighted routing (80% v1, 20% v2):"
curl -s http://$EXTERNAL_IP/testproduct-weighted --header "Host: istiotraffic.srinman.com"
```

---

## Part 7: Internal Mesh Traffic vs External Gateway Traffic

### Step 7.1: Deploy Internal Client Application

```bash
# Create tooling namespace
kubectl create namespace toolns
kubectl label namespace toolns istio.io/rev=asm-1-25

# Deploy netshoot client for internal testing
kubectl run netshoot -n toolns --image=nicolaka/netshoot -- sh -c 'sleep 3600'


```

### Step 7.2: Create Internal VirtualService (Mesh-Only)

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-internal
  namespace: testproduct
spec:
  hosts:
  - testapi.testproduct.svc.cluster.local
  http:
  - match:
    - uri:
        prefix: /internal
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: v2
        port:
          number: 80
  - route:
    - destination:
        host: testapi
        subset: v1
        port:
          number: 80
EOF
```

**🔍 Internal vs External Routing:**
- **No Gateway**: Internal VirtualService doesn't specify gateways
- **FQDN Host**: Uses full service DNS name
- **Mesh Traffic**: Only affects pod-to-pod communication

### Step 7.3: Test Internal vs External Routing

```bash
# Test internal routing from netshoot pod
echo "Testing internal mesh routing:"
kubectl exec netshoot -n toolns -- curl -s http://testapi.testproduct.svc.cluster.local/internal  
kubectl exec netshoot -n toolns -- curl -s http://testapi.testproduct.svc.cluster.local/authors  

# Compare with external routing
echo "Testing external gateway routing:"
curl -s http://$EXTERNAL_IP/testproduct-v1 --header "Host: istiotraffic.srinman.com"  
curl -s http://$EXTERNAL_IP/testproduct-v2 --header "Host: istiotraffic.srinman.com"  
```

--- 
```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: testapi
    version: v1 
  name: testapi1
  namespace: testproduct 
spec:
  replicas: 1
  selector:
    matchLabels:
      app: testapi
      version: v1
  template:
    metadata:
      labels:
        app: testapi
        version: v1
    spec:
      containers:
      - image: srinmantest.azurecr.io/istioapi:v1
        name: istio-api-1
---
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: testapi
    version: v2
  name: testapi2
  namespace: testproduct 
spec:
  replicas: 1
  selector:
    matchLabels:
      app: testapi
      version: v2
  template:
    metadata:
      labels:
        app: testapi
        version: v2
    spec:
      containers:
      - image: srinmantest.azurecr.io/istioapi:v2
        name: istio-api-2
---
apiVersion: v1
kind: Service
metadata:
  creationTimestamp: null
  labels:
    app: testapi
  name: testapi
  namespace: testproduct
spec:
  ports:
  - port: 80
    name: http
    targetPort: 5000
  selector:
    app: testapi
---
apiVersion: v1
kind: Service
metadata:
  creationTimestamp: null
  labels:
    app: testapi2
  name: testapi2
  namespace: testproduct
spec:
  ports:
  - port: 80
    name: http
    targetPort: 5000
  selector:
    app: testapi
    version: v2
EOF
```
k get deploy -n testproduct 
k get pod -n testproduct --show-labels 
k describe svc testapi -n testproduct

testapi service is routing traffic to both testapi1 and testapi2 deployments.  testapi selector is pointing to app: testapi.  testapi1 and testapi2 deployments have the label app: testapi.  So, the service is routing traffic to both deployments. 


Let's create a virtual service to route traffic to the testapi1 service. 

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: testproduct-gateway-external
  namespace: testproduct
spec:
  selector:
    istio: aks-istio-ingressgateway-external
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "istiotraffic.srinman.com"
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  - match:
    - uri:
        exact: /testproduct
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        port:
          number: 80
EOF
``` 

k get vs -n testproduct
k get gateway -n testproduct
testproduct-vs is routing traffic to the testapi service.  It should be routing to both testapi1 and testapi2 deployments.   
Verify 
curl -v http://135.232.45.103:80/testproduct --header "Host: istiotraffic.srinman.com"  

### DestinationRule 

Partioning Kubernetes service into multiple subsets.  
A subset of endpoints of a service. 

In this following example, we are creating two subsets for the testapi service.  One subset is for v1 and the other subset is for v2.  You can consider v2 as a canary deployment or blue-green deployment.   

k get vs -n testproduct
k get dr -n testproduct

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: testproduct-dr
  namespace: testproduct
spec:
  host: testapi
  subsets:
  - name: subset-v1
    labels:
      version: v1
  - name: subset-v2
    labels:
      version: v2
EOF
```
Let's define a newvirtual service to route traffic to the subsets v2. 

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-dr
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  - match:
    - uri:
        exact: /testproduct-dr
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: subset-v2
        port:
          number: 80
EOF
```

curl -v http://135.232.45.103:80/testproduct-dr --header "Host: istiotraffic.srinman.com"  

from browser, IP/testproduct-dr should route traffic to v2 only.  
IP/testproduct should route traffic to v1 or v2.

#### Header based routing with VirtualService    

https://istio.io/latest/blog/2017/0.1-canary/#focused-canary-testing   

v1 is our default version.  We will route traffic to v2 based on the header value.  
```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-dr
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  - match:
    - headers:
        x-istio-test: 
          exact: "testversion"
      uri:
        exact: /testproduct-dr
    rewrite:
      uri: /authors
    route: 
    - destination:
        host: testapi
        subset: subset-v2
        port:
          number: 80
  - match:
    - uri:
        exact: /testproduct-dr
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: subset-v1
        port:
          number: 80
EOF
```

curl http://52.252.69.106/testproduct-dr -H 'x-istio-test: testversion' should route traffic to v2.
curl -v http://135.232.45.103:80/testproduct-dr --header "Host: istiotraffic.srinman.com" --header "x-istio-test: testversion"

curl http://52.252.69.106/testproduct-dr should always route traffic to v1.

#### Weight based routing with VirtualService  


```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: testproduct-vs-dr
  namespace: testproduct
spec:
  hosts:
  - "istiotraffic.srinman.com"
  gateways:
  - testproduct-gateway-external
  http:
  - match:
    - uri:
        exact: /testproduct-weighted
    rewrite:
      uri: /authors
    route:
    - destination:
        host: testapi
        subset: subset-v1
        port:
          number: 80
      weight: 10
    - destination:
        host: testapi
        subset: subset-v2
        port:
          number: 80
      weight: 90
EOF
```

curl -v http://135.232.45.103:80/testproduct-weighted --header "Host: istiotraffic.srinman.com" 

### Traffic calls withing the mesh


k create ns toolns
kubectl label namespace toolns istio.io/rev=asm-1-22

k -n toolns run netshoot --image=nicolaka/netshoot -- sh -c 'sleep 2000'  

k exec netshoot -n toolns -it -- bash 

curl -v http://135.232.45.103:80/testproduct-dr --header "Host: istiotraffic.srinman.com" --header "x-istio-test: testversion"



### Locality Load Balancing  


NOT TESTED YET.
```bash
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: httpbin
spec:
  host: httpbin
  trafficPolicy:
    loadBalancer:
      localityLbSetting:
        enabled: true
        distribute:
          - from: "us-west/zone1"
            to:
              "us-west/zone1": 100
              "us-west/zone2": 0
              "us-west/zone3": 0
          - from: "us-west/zone2"
            to:
              "us-west/zone2": 100
              "us-west/zone1": 0
              "us-west/zone3": 0
          - from: "us-west/zone3"
            to:
              "us-west/zone3": 100
              "us-west/zone1": 0
              "us-west/zone2": 0
        failover:
          - from: "us-west/zone1"
            to: "us-west/zone2"
          - from: "us-west/zone2"
            to: "us-west/zone3"
          - from: "us-west/zone3"
            to: "us-west/zone1"
    connectionPool:
      tcp:
        maxConnections: 1
      http:
        http1MaxPendingRequests: 1
        maxRequestsPerConnection: 1
    outlierDetection:
      consecutive5xxErrors: 1
      interval: 1s
      baseEjectionTime: 3m
      maxEjectionPercent: 100
```