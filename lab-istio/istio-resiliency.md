# Istio Resiliency Lab

## Overview

This lab demonstrates Istio's powerful resiliency features that help build fault-tolerant microservices architectures. Istio provides several mechanisms to handle failures gracefully and improve application reliability without requiring changes to your application code.

## Learning Objectives

By the end of this lab, you will understand and implement:

1. **Retries**: Automatically retry failed requests with configurable policies
2. **Timeouts**: Set request timeout limits to prevent hanging requests
3. **Circuit Breakers**: Prevent cascading failures by temporarily stopping requests to failing services
4. **Fault Injection**: Test application resilience by injecting delays and errors

## Resiliency Features Overview

### Istio Resiliency Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Istio Resiliency Features                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Client Service          Istio Proxy           Target Service   │
│  ┌─────────────┐       ┌─────────────────┐     ┌─────────────┐ │
│  │             │       │                 │     │             │ │
│  │ Application │──────►│   Envoy Proxy   │────►│ Application │ │
│  │             │       │                 │     │             │ │
│  └─────────────┘       └─────────────────┘     └─────────────┘ │
│                               │                                 │
│                               ▼                                 │
│                        ┌─────────────┐                         │
│                        │ Resiliency  │                         │
│                        │ Policies:   │                         │
│                        │ • Retries   │                         │
│                        │ • Timeouts  │                         │
│                        │ • Breakers  │                         │
│                        │ • Injection │                         │
│                        └─────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Concepts

- **VirtualService**: Defines traffic routing rules and resiliency policies
- **DestinationRule**: Configures circuit breaker settings and load balancing
- **Fault Injection**: Introduces artificial delays and errors for testing
- **Retry Policies**: Automatic retry mechanisms with backoff strategies

---

## Prerequisites and Environment Setup

### Verify Istio Installation

```bash
export CLUSTER=aksistio1
export RESOURCE_GROUP=aksistiorg
export LOCATION=eastus2
az aks show --name $CLUSTER --resource-group $RESOURCE_GROUP --query 'serviceMeshProfile'
```

### Create Lab Namespace

```bash
kubectl create ns resiliency-lab
kubectl label namespace resiliency-lab istio.io/rev=asm-1-22
```

### Lab Environment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Lab Environment Setup                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  resiliency-lab namespace (with Istio sidecar injection)       │
│  ┌─────────────────────────────────────────────────────────────┤
│  │                                                             │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  │             │    │             │    │             │     │
│  │  │ Client App  │───►│ Stable API  │    │ Flaky API   │     │
│  │  │ (clientapp) │    │ (api1v1)    │    │ (appflaky)  │     │
│  │  │             │    │             │    │             │     │
│  │  └─────────────┘    └─────────────┘    └─────────────┘     │
│  │                                                             │
│  │  Features Demonstrated:                                     │
│  │  • Client makes requests to both stable and flaky services │
│  │  • Flaky service returns 50% error rate                   │
│  │  • Stable service for comparison testing                   │
│  └─────────────────────────────────────────────────────────────┘
│                                                                 │
│  External Testing:                                              │
│  ┌─────────────────────────────────────────────────────────────┤
│  │ Local Machine ──► Load Balancer ──► Services               │
│  │ (resiliencytest.py script)                                 │
│  └─────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

---


## Lab Exercise 1: Retries

### Understanding Retries

Retries automatically re-attempt failed requests based on configurable policies. This is essential for handling transient failures in distributed systems.

### Retry Configuration Options

- **attempts**: Maximum number of retry attempts
- **perTryTimeout**: Timeout for each individual retry attempt
- **retryOn**: Conditions that trigger retries (5xx, reset, connect-failure, etc.)
- **retryRemoteLocalities**: Whether to retry in other availability zones

### Step 1: Deploy the Flaky Application

The `appflaky` service simulates an unreliable service with a 50% failure rate:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: appflaky
  namespace: resiliency-lab
  labels:
    app: appflaky
spec:
  replicas: 1
  selector:
    matchLabels:
      app: appflaky
  template:
    metadata:
      labels:
        app: appflaky
    spec:
      containers:
      - name: appflaky
        image: srinmantest.azurecr.io/appflaky:v1
        ports:
        - containerPort: 5000
---
apiVersion: v1
kind: Service
metadata:
  name: appflaky
  namespace: resiliency-lab
spec:
  selector:
    app: appflaky
  ports:
  - name: http
    protocol: TCP
    port: 80
    targetPort: 5000
---
apiVersion: v1
kind: Service
metadata:
  name: appflaky-lb
  namespace: resiliency-lab
spec:
  type: LoadBalancer
  selector:
    app: appflaky
  ports:
  - name: http
    protocol: TCP
    port: 80
    targetPort: 5000
EOF
```

### Step 2: Deploy the Client Application

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: client
  namespace: resiliency-lab
  labels:
    app: client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: client
  template:
    metadata:
      labels:
        app: client
    spec:
      containers:
      - name: client
        image: srinmantest.azurecr.io/clientapp:v1
        imagePullPolicy: Always
        env:
        - name: ENDPOINT_URL
          value: "http://appflaky.resiliency-lab.svc.cluster.local/unstable-endpoint"
EOF
```

### Step 3: Observe Baseline Behavior

Monitor the client application logs to see the current success/failure rate:

```bash
kubectl logs -f -l app=client -n resiliency-lab
```

**Expected Result**: You should see approximately 50% success and 50% failure rate.

### Retry Policy Architecture

```
Without Retries:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │    │    Proxy    │    │   Flaky     │
│             │    │             │    │   Service   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │ 1. Request        │                   │
       │ ─────────────────►│                   │
       │                   │ 2. Forward        │
       │                   │ ─────────────────►│
       │                   │                   │
       │                   │ 3. 500 Error     │
       │                   │◄─────────────────│
       │ 4. 500 Error     │                   │
       │◄─────────────────│                   │
       │                                       │
       │ Result: 50% failure rate              │

With Retries:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │    │    Proxy    │    │   Flaky     │
│             │    │ (w/ retry)  │    │   Service   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │ 1. Request        │                   │
       │ ─────────────────►│                   │
       │                   │ 2. Attempt 1     │
       │                   │ ─────────────────►│
       │                   │ 3. 500 Error     │
       │                   │◄─────────────────│
       │                   │ 4. Attempt 2     │
       │                   │ ─────────────────►│
       │                   │ 5. 200 Success   │
       │                   │◄─────────────────│
       │ 6. 200 Success   │                   │
       │◄─────────────────│                   │
       │                                       │
       │ Result: Much higher success rate      │
```

### Step 4: Apply Basic Retry Policy

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: appflaky-retry
  namespace: resiliency-lab
spec:
  hosts:
  - appflaky.resiliency-lab.svc.cluster.local
  http:
  - route:
    - destination:
        host: appflaky
        port:
          number: 80
    retries:
      attempts: 5
      perTryTimeout: 2s
EOF
```

**Observe the logs again**:
```bash
kubectl logs -f -l app=client -n resiliency-lab
```

**Expected Result**: Still showing failures because default retry conditions don't include 5xx errors.

### Step 5: Apply Retry Policy with 5xx Conditions

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: appflaky-retry
  namespace: resiliency-lab
spec:
  hosts:
  - appflaky.resiliency-lab.svc.cluster.local
  http:
  - route:
    - destination:
        host: appflaky
        port:
          number: 80
    retries:
      attempts: 5
      perTryTimeout: 2s
      retryOn: "5xx,reset,connect-failure,refused-stream"
EOF
```

**Observe the logs**:
```bash
kubectl logs -f -l app=client -n resiliency-lab
```

**Expected Result**: Success rate should improve dramatically (close to 100%) due to retries.

### Step 6: Test External Traffic (Without Retries)

Set up mTLS in permissive mode to allow external traffic:

```bash
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: resiliency-lab
spec:
  mtls:
    mode: PERMISSIVE
EOF
```

Get the external load balancer IP:
```bash
kubectl get svc appflaky-lb -n resiliency-lab
export ENDPOINT_URL="http://EXTERNAL_IP/unstable-endpoint"
```

Test from your local machine:
```bash
cd lab-istio/tools
python resiliencytest.py
```

**Expected Result**: External traffic shows ~50% failure rate because retries only apply to traffic within the mesh.

---

## Lab Exercise 2: Timeouts

### Understanding Timeouts

Timeouts prevent requests from hanging indefinitely by setting maximum wait times. This is crucial for maintaining system responsiveness and preventing resource exhaustion.

### Step 1: Create a Slow Service

First, let's create a service that introduces delays to demonstrate timeouts:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: slow-service
  namespace: resiliency-lab
  labels:
    app: slow-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: slow-service
  template:
    metadata:
      labels:
        app: slow-service
    spec:
      containers:
      - name: slow-service
        image: nginx:alpine
        ports:
        - containerPort: 80
        command: ["/bin/sh"]
        args: ["-c", "while true; do echo 'HTTP/1.1 200 OK\r\n\r\nSlow response after 10 seconds' | nc -l -p 80 -q 1; sleep 10; done"]
---
apiVersion: v1
kind: Service
metadata:
  name: slow-service
  namespace: resiliency-lab
spec:
  selector:
    app: slow-service
  ports:
  - name: http
    protocol: TCP
    port: 80
    targetPort: 80
EOF
```

### Step 2: Create a Service with Variable Delays

Let's create a more sophisticated service that simulates variable response times:

```bash
cat > /home/srinman/git/aksworkshop/istioapi/src/slowapi.py << 'EOF'
from flask import Flask, jsonify, request
import time
import random

app = Flask(__name__)

@app.route('/fast')
def fast_endpoint():
    """Fast response - no delay"""
    return jsonify({"message": "Fast response", "delay": 0}), 200

@app.route('/slow')
def slow_endpoint():
    """Slow response - 3-8 second delay"""
    delay = random.uniform(3, 8)
    time.sleep(delay)
    return jsonify({"message": "Slow response", "delay": f"{delay:.2f}s"}), 200

@app.route('/very-slow')
def very_slow_endpoint():
    """Very slow response - 10-15 second delay"""
    delay = random.uniform(10, 15)
    time.sleep(delay)
    return jsonify({"message": "Very slow response", "delay": f"{delay:.2f}s"}), 200

@app.route('/timeout-test')
def timeout_test():
    """Test different timeout scenarios"""
    scenario = request.args.get('scenario', 'fast')
    
    if scenario == 'fast':
        return fast_endpoint()
    elif scenario == 'slow':
        return slow_endpoint()
    elif scenario == 'very-slow':
        return very_slow_endpoint()
    else:
        return jsonify({"error": "Unknown scenario"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF
```

Deploy the slow API service:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: slowapi
  namespace: resiliency-lab
  labels:
    app: slowapi
spec:
  replicas: 1
  selector:
    matchLabels:
      app: slowapi
  template:
    metadata:
      labels:
        app: slowapi
    spec:
      containers:
      - name: slowapi
        image: python:3.9-slim
        ports:
        - containerPort: 5000
        command: ["/bin/bash"]
        args: ["-c", "pip install flask && python -c '
from flask import Flask, jsonify, request
import time
import random

app = Flask(__name__)

@app.route(\"/fast\")
def fast_endpoint():
    return jsonify({\"message\": \"Fast response\", \"delay\": 0}), 200

@app.route(\"/slow\")
def slow_endpoint():
    delay = random.uniform(3, 8)
    time.sleep(delay)
    return jsonify({\"message\": \"Slow response\", \"delay\": f\"{delay:.2f}s\"}), 200

@app.route(\"/very-slow\")
def very_slow_endpoint():
    delay = random.uniform(10, 15)
    time.sleep(delay)
    return jsonify({\"message\": \"Very slow response\", \"delay\": f\"{delay:.2f}s\"}), 200

if __name__ == \"__main__\":
    app.run(host=\"0.0.0.0\", port=5000)
'"]
---
apiVersion: v1
kind: Service
metadata:
  name: slowapi
  namespace: resiliency-lab
spec:
  selector:
    app: slowapi
  ports:
  - name: http
    protocol: TCP
    port: 80
    targetPort: 5000
EOF
```

### Step 3: Test Without Timeouts

Create a client to test the slow service:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: timeout-client
  namespace: resiliency-lab
  labels:
    app: timeout-client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: timeout-client
  template:
    metadata:
      labels:
        app: timeout-client
    spec:
      containers:
      - name: timeout-client
        image: curlimages/curl:latest
        command: ["/bin/sh"]
        args: ["-c", "while true; do echo 'Testing fast endpoint:'; time curl -s http://slowapi.resiliency-lab.svc.cluster.local/fast; echo; echo 'Testing slow endpoint:'; time curl -s http://slowapi.resiliency-lab.svc.cluster.local/slow; echo; sleep 30; done"]
EOF
```

Monitor the client logs:
```bash
kubectl logs -f -l app=timeout-client -n resiliency-lab
```

### Timeout Policy Architecture

```
Without Timeouts:
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │    │    Proxy    │    │   Slow      │
│             │    │             │    │   Service   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │ 1. Request        │                   │
       │ ─────────────────►│                   │
       │                   │ 2. Forward        │
       │                   │ ─────────────────►│
       │                   │                   │ 10s delay
       │                   │                   │
       │                   │ 3. Response       │
       │                   │◄─────────────────│ (after 10s)
       │ 4. Response       │                   │
       │◄─────────────────│                   │
       │                                       │
       │ Total time: 10+ seconds               │

With Timeouts (5s):
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │    │    Proxy    │    │   Slow      │
│             │    │ (w/ timeout)│    │   Service   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       │ 1. Request        │                   │
       │ ─────────────────►│                   │
       │                   │ 2. Forward        │
       │                   │ ─────────────────►│
       │                   │                   │ 10s delay
       │                   │                   │ (but timeout
       │                   │ 3. Timeout        │  at 5s)
       │                   │    (504 error)    │
       │ 4. 504 Error     │                   │
       │◄─────────────────│                   │
       │                                       │
       │ Total time: 5 seconds (timeout)       │
```

### Step 4: Apply Timeout Policy

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: slowapi-timeout
  namespace: resiliency-lab
spec:
  hosts:
  - slowapi.resiliency-lab.svc.cluster.local
  http:
  - route:
    - destination:
        host: slowapi
        port:
          number: 80
    timeout: 5s
EOF
```

### Step 5: Test With Timeouts

Update the client to test different scenarios:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: timeout-client
  namespace: resiliency-lab
  labels:
    app: timeout-client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: timeout-client
  template:
    metadata:
      labels:
        app: timeout-client
    spec:
      containers:
      - name: timeout-client
        image: curlimages/curl:latest
        command: ["/bin/sh"]
        args: ["-c", "while true; do echo '=== Testing with 5s timeout ==='; echo 'Fast endpoint (should work):'; time curl -s http://slowapi.resiliency-lab.svc.cluster.local/fast || echo 'FAILED'; echo; echo 'Slow endpoint (should timeout):'; time curl -s http://slowapi.resiliency-lab.svc.cluster.local/slow || echo 'TIMEOUT'; echo; echo 'Very slow endpoint (should timeout):'; time curl -s http://slowapi.resiliency-lab.svc.cluster.local/very-slow || echo 'TIMEOUT'; echo; sleep 30; done"]
EOF
```

**Observe the results**:
```bash
kubectl logs -f -l app=timeout-client -n resiliency-lab
```

**Expected Results**:
- Fast endpoint: Works normally
- Slow endpoint: Times out after 5 seconds
- Very slow endpoint: Times out after 5 seconds

### Step 6: Advanced Timeout Configuration

Apply different timeouts for different routes:

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: slowapi-timeout
  namespace: resiliency-lab
spec:
  hosts:
  - slowapi.resiliency-lab.svc.cluster.local
  http:
  - match:
    - uri:
        prefix: "/fast"
    route:
    - destination:
        host: slowapi
        port:
          number: 80
    timeout: 2s
  - match:
    - uri:
        prefix: "/slow"
    route:
    - destination:
        host: slowapi
        port:
          number: 80
    timeout: 10s
  - match:
    - uri:
        prefix: "/very-slow"
    route:
    - destination:
        host: slowapi
        port:
          number: 80
    timeout: 20s
EOF
```

---

## Lab Exercise 3: Circuit Breakers

### Understanding Circuit Breakers

Circuit breakers prevent cascading failures by temporarily stopping requests to a failing service, allowing it time to recover. The circuit breaker has three states:
- **CLOSED**: Normal operation, requests flow through
- **OPEN**: Service is failing, requests are immediately rejected
- **HALF-OPEN**: Testing if service has recovered

### Circuit Breaker Architecture

```
Circuit Breaker States:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│ CLOSED State (Normal Operation)                                 │
│ ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│ │   Client    │───►│   Circuit   │───►│   Service   │          │
│ │             │    │   Breaker   │    │             │          │
│ └─────────────┘    └─────────────┘    └─────────────┘          │
│                                                                 │
│ OPEN State (Service Failing)                                   │
│ ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│ │   Client    │───►│   Circuit   │ ✗  │   Service   │          │
│ │             │    │   Breaker   │    │ (failing)   │          │
│ └─────────────┘    └─────────────┘    └─────────────┘          │
│                           │                                     │
│                           ▼                                     │
│                    Immediate rejection                          │
│                    (503 Service Unavailable)                   │
│                                                                 │
│ HALF-OPEN State (Testing Recovery)                             │
│ ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│ │   Client    │───►│   Circuit   │~~~►│   Service   │          │
│ │             │    │   Breaker   │    │ (testing)   │          │
│ └─────────────┘    └─────────────┘    └─────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1: Deploy a Circuit Breaker Configuration

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: appflaky-circuit-breaker
  namespace: resiliency-lab
spec:
  host: appflaky.resiliency-lab.svc.cluster.local
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 10
      http:
        http1MaxPendingRequests: 5
        maxRequestsPerConnection: 2
    outlierDetection:
      consecutiveErrors: 3
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 100
EOF
```

**Circuit Breaker Configuration Explained**:
- **consecutiveErrors: 3**: Open circuit after 3 consecutive failures
- **interval: 30s**: Analysis interval for error detection
- **baseEjectionTime: 30s**: Minimum ejection duration
- **maxEjectionPercent: 100**: Can eject all instances if needed

### Step 2: Create a Load Testing Client

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: load-tester
  namespace: resiliency-lab
  labels:
    app: load-tester
spec:
  replicas: 1
  selector:
    matchLabels:
      app: load-tester
  template:
    metadata:
      labels:
        app: load-tester
    spec:
      containers:
      - name: load-tester
        image: curlimages/curl:latest
        command: ["/bin/sh"]
        args: ["-c", "while true; do for i in \$(seq 1 20); do echo \"Request \$i:\"; curl -s -w \"Status: %{http_code}, Time: %{time_total}s\\n\" http://appflaky.resiliency-lab.svc.cluster.local/unstable-endpoint -o /dev/null; done; echo '--- Batch complete, waiting 5s ---'; sleep 5; done"]
EOF
```

### Step 3: Monitor Circuit Breaker Behavior

```bash
kubectl logs -f -l app=load-tester -n resiliency-lab
```

**Expected Behavior**:
1. Initially: Mix of 200 and 500 responses
2. After consecutive failures: Circuit opens, immediate 503 responses
3. After ejection time: Circuit goes to half-open, tests service
4. If service recovered: Circuit closes, normal operation resumes

### Step 4: Monitor Circuit Breaker Metrics

You can also check the Envoy admin interface to see circuit breaker statistics:

```bash
kubectl exec -it deployment/load-tester -n resiliency-lab -- /bin/sh
```

From inside the pod:
```bash
# Check circuit breaker stats
curl -s localhost:15000/stats | grep circuit_breakers
curl -s localhost:15000/stats | grep outlier_detection
```

### Step 5: Fine-tune Circuit Breaker

Apply a more sensitive circuit breaker configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: appflaky-circuit-breaker
  namespace: resiliency-lab
spec:
  host: appflaky.resiliency-lab.svc.cluster.local
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 5
      http:
        http1MaxPendingRequests: 2
        maxRequestsPerConnection: 1
    outlierDetection:
      consecutiveErrors: 2
      interval: 10s
      baseEjectionTime: 10s
      maxEjectionPercent: 100
      minHealthPercent: 0
EOF
```

---

## Lab Exercise 4: Fault Injection

### Understanding Fault Injection

Fault injection allows you to introduce artificial delays and errors to test your application's resilience. This is essential for chaos engineering and testing failure scenarios.

### Types of Fault Injection

- **Delay Injection**: Introduces artificial latency
- **Abort Injection**: Returns HTTP error codes
- **Combination**: Both delay and abort for comprehensive testing

### Fault Injection Architecture

```
Fault Injection Flow:
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Client Service          Istio Proxy           Target Service   │
│  ┌─────────────┐       ┌─────────────────┐     ┌─────────────┐ │
│  │             │       │                 │     │             │ │
│  │ Application │──────►│   Envoy Proxy   │     │ Application │ │
│  │             │       │                 │     │             │ │
│  └─────────────┘       └─────────────────┘     └─────────────┘ │
│                               │                                 │
│                               ▼                                 │
│                        ┌─────────────┐                         │
│                        │ Fault       │                         │
│                        │ Injection:  │                         │
│                        │ • 50% delay │                         │
│                        │ • 20% abort │                         │
│                        │ • 30% normal│                         │
│                        └─────────────┘                         │
│                                                                 │
│  Scenarios:                                                     │
│  1. Delay: Add 5s delay to 50% of requests                    │
│  2. Abort: Return 503 error for 20% of requests               │
│  3. Normal: 30% requests pass through normally                 │
└─────────────────────────────────────────────────────────────────┘
```

### Step 1: Deploy a Stable Service for Testing

First, let's deploy a reliable service to test fault injection:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stable-api
  namespace: resiliency-lab
  labels:
    app: stable-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: stable-api
  template:
    metadata:
      labels:
        app: stable-api
    spec:
      containers:
      - name: stable-api
        image: srinmantest.azurecr.io/api1v1:latest
        ports:
        - containerPort: 5000
---
apiVersion: v1
kind: Service
metadata:
  name: stable-api
  namespace: resiliency-lab
spec:
  selector:
    app: stable-api
  ports:
  - name: http
    protocol: TCP
    port: 80
    targetPort: 5000
EOF
```

### Step 2: Test Baseline Performance

Create a client to test the stable service:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fault-test-client
  namespace: resiliency-lab
  labels:
    app: fault-test-client
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fault-test-client
  template:
    metadata:
      labels:
        app: fault-test-client
    spec:
      containers:
      - name: fault-test-client
        image: curlimages/curl:latest
        command: ["/bin/sh"]
        args: ["-c", "while true; do echo '=== Testing stable-api ==='; for i in \$(seq 1 10); do echo \"Request \$i:\"; time curl -s -w \"Status: %{http_code}, Time: %{time_total}s\\n\" http://stable-api.resiliency-lab.svc.cluster.local/books -o /dev/null; done; echo; sleep 10; done"]
EOF
```

Observe baseline performance:
```bash
kubectl logs -f -l app=fault-test-client -n resiliency-lab
```

**Expected Result**: All requests should succeed quickly with 200 status codes.

### Step 3: Inject Delays

Apply delay injection to simulate network latency:

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: stable-api-fault
  namespace: resiliency-lab
spec:
  hosts:
  - stable-api.resiliency-lab.svc.cluster.local
  http:
  - fault:
      delay:
        percentage:
          value: 50.0
        fixedDelay: 5s
    route:
    - destination:
        host: stable-api
        port:
          number: 80
EOF
```

**Observe the effects**:
```bash
kubectl logs -f -l app=fault-test-client -n resiliency-lab
```

**Expected Result**: 50% of requests should take 5+ seconds to complete.

### Step 4: Inject Abort Errors

Apply abort injection to simulate service failures:

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: stable-api-fault
  namespace: resiliency-lab
spec:
  hosts:
  - stable-api.resiliency-lab.svc.cluster.local
  http:
  - fault:
      abort:
        percentage:
          value: 30.0
        httpStatus: 503
    route:
    - destination:
        host: stable-api
        port:
          number: 80
EOF
```

**Observe the effects**:
```bash
kubectl logs -f -l app=fault-test-client -n resiliency-lab
```

**Expected Result**: 30% of requests should return 503 Service Unavailable errors.

### Step 5: Combine Delay and Abort

Apply both delay and abort injection:

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: stable-api-fault
  namespace: resiliency-lab
spec:
  hosts:
  - stable-api.resiliency-lab.svc.cluster.local
  http:
  - fault:
      delay:
        percentage:
          value: 20.0
        fixedDelay: 3s
      abort:
        percentage:
          value: 10.0
        httpStatus: 500
    route:
    - destination:
        host: stable-api
        port:
          number: 80
EOF
```

**Expected Results**:
- 20% of requests: 3-second delay
- 10% of requests: 500 Internal Server Error
- 70% of requests: Normal operation

### Step 6: User-Based Fault Injection

Inject faults only for specific users (headers):

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: stable-api-fault
  namespace: resiliency-lab
spec:
  hosts:
  - stable-api.resiliency-lab.svc.cluster.local
  http:
  - match:
    - headers:
        user-type:
          exact: "test-user"
    fault:
      delay:
        percentage:
          value: 100.0
        fixedDelay: 2s
    route:
    - destination:
        host: stable-api
        port:
          number: 80
  - route:
    - destination:
        host: stable-api
        port:
          number: 80
EOF
```

Test with headers:
```bash
kubectl exec -it deployment/fault-test-client -n resiliency-lab -- /bin/sh
```

Inside the pod:
```bash
# Regular user - no delay
curl -H "user-type: regular" http://stable-api.resiliency-lab.svc.cluster.local/books

# Test user - with delay
curl -H "user-type: test-user" http://stable-api.resiliency-lab.svc.cluster.local/books
```

---

## Lab Exercise 5: Comprehensive Resiliency Testing

### Combining All Resiliency Features

Let's create a comprehensive configuration that combines retries, timeouts, circuit breakers, and fault injection:

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: comprehensive-resiliency
  namespace: resiliency-lab
spec:
  hosts:
  - appflaky.resiliency-lab.svc.cluster.local
  http:
  - match:
    - headers:
        test-scenario:
          exact: "chaos-testing"
    fault:
      delay:
        percentage:
          value: 20.0
        fixedDelay: 2s
      abort:
        percentage:
          value: 10.0
        httpStatus: 503
    route:
    - destination:
        host: appflaky
        port:
          number: 80
    retries:
      attempts: 3
      perTryTimeout: 5s
      retryOn: "5xx,reset,connect-failure,refused-stream"
    timeout: 15s
  - route:
    - destination:
        host: appflaky
        port:
          number: 80
    retries:
      attempts: 5
      perTryTimeout: 2s
      retryOn: "5xx,reset,connect-failure,refused-stream"
    timeout: 10s
---
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: comprehensive-circuit-breaker
  namespace: resiliency-lab
spec:
  host: appflaky.resiliency-lab.svc.cluster.local
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 10
      http:
        http1MaxPendingRequests: 5
        maxRequestsPerConnection: 2
    outlierDetection:
      consecutiveErrors: 3
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
EOF
```

### Comprehensive Testing Client

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: comprehensive-tester
  namespace: resiliency-lab
  labels:
    app: comprehensive-tester
spec:
  replicas: 1
  selector:
    matchLabels:
      app: comprehensive-tester
  template:
    metadata:
      labels:
        app: comprehensive-tester
    spec:
      containers:
      - name: comprehensive-tester
        image: curlimages/curl:latest
        command: ["/bin/sh"]
        args: ["-c", "while true; do echo '=== Normal Requests ==='; for i in \$(seq 1 5); do curl -s -w \"Status: %{http_code}, Time: %{time_total}s\\n\" http://appflaky.resiliency-lab.svc.cluster.local/unstable-endpoint -o /dev/null; done; echo; echo '=== Chaos Testing Requests ==='; for i in \$(seq 1 5); do curl -s -H 'test-scenario: chaos-testing' -w \"Status: %{http_code}, Time: %{time_total}s\\n\" http://appflaky.resiliency-lab.svc.cluster.local/unstable-endpoint -o /dev/null; done; echo; sleep 15; done"]
EOF
```

### Monitor All Components

```bash
# Watch comprehensive tester logs
kubectl logs -f -l app=comprehensive-tester -n resiliency-lab

# In another terminal, watch circuit breaker statistics
kubectl exec -it deployment/comprehensive-tester -n resiliency-lab -- /bin/sh
# Inside the pod:
# watch -n 2 'curl -s localhost:15000/stats | grep -E "(circuit_breakers|outlier_detection|retry)"'
```

---

## Monitoring and Observability

### Key Metrics to Monitor

1. **Retry Metrics**:
   - `envoy_cluster_upstream_rq_retry`: Number of retries
   - `envoy_cluster_upstream_rq_retry_success`: Successful retries

2. **Circuit Breaker Metrics**:
   - `envoy_cluster_circuit_breakers_*_open`: Circuit breaker state
   - `envoy_cluster_outlier_detection_ejections_active`: Active ejections

3. **Timeout Metrics**:
   - `envoy_cluster_upstream_rq_timeout`: Request timeouts
   - `envoy_http_downstream_rq_time`: Request duration

### Accessing Envoy Admin Interface

```bash
# Access Envoy admin interface from any pod
kubectl exec -it deployment/client -n resiliency-lab -- /bin/sh

# Inside the pod:
curl localhost:15000/stats | grep retry
curl localhost:15000/stats | grep circuit_breakers
curl localhost:15000/stats | grep timeout
```

### Sample Monitoring Queries

For Prometheus/Grafana integration:

```promql
# Success rate after retries
sum(rate(envoy_cluster_upstream_rq_success[5m])) / sum(rate(envoy_cluster_upstream_rq_total[5m]))

# Circuit breaker ejections
sum(rate(envoy_cluster_outlier_detection_ejections_total[5m]))

# Request timeout rate
sum(rate(envoy_cluster_upstream_rq_timeout[5m])) / sum(rate(envoy_cluster_upstream_rq_total[5m]))
```

---

## Best Practices and Production Considerations

### 1. Retry Configuration Best Practices

```yaml
retries:
  attempts: 3-5              # Don't over-retry
  perTryTimeout: 1-3s        # Shorter than total timeout
  retryOn: "5xx,reset,connect-failure,refused-stream"
  retryRemoteLocalities: true # Try other zones
```

### 2. Timeout Configuration Guidelines

- **Fast services**: 1-5 seconds
- **Medium services**: 5-15 seconds  
- **Slow services**: 15-30 seconds
- **Background jobs**: 60+ seconds

### 3. Circuit Breaker Configuration

```yaml
outlierDetection:
  consecutiveErrors: 3-5     # Not too sensitive
  interval: 30-60s          # Analysis window
  baseEjectionTime: 30s     # Minimum recovery time
  maxEjectionPercent: 50    # Don't eject all instances
```

### 4. Fault Injection Guidelines

- Start with low percentages (1-5%)
- Test during low-traffic periods
- Have rollback procedures ready
- Monitor application behavior closely

---

## Troubleshooting Common Issues

### 1. Retries Not Working

**Symptoms**: Still seeing failures despite retry configuration

**Solutions**:
- Check `retryOn` conditions match the error types
- Verify `perTryTimeout` isn't too short
- Ensure VirtualService is applied correctly

```bash
kubectl describe virtualservice -n resiliency-lab
```

### 2. Circuit Breaker Not Triggering

**Symptoms**: Circuit breaker never opens despite failures

**Solutions**:
- Lower `consecutiveErrors` threshold
- Check error rate is sufficient
- Verify traffic is going through the proxy

```bash
kubectl exec -it deployment/client -n resiliency-lab -- curl localhost:15000/stats | grep outlier
```

### 3. Timeouts Too Aggressive

**Symptoms**: Legitimate requests timing out

**Solutions**:
- Increase timeout values
- Check network latency
- Monitor request duration patterns

### 4. Fault Injection Not Applied

**Symptoms**: No delays or errors observed

**Solutions**:
- Verify VirtualService configuration
- Check traffic is matching rules
- Confirm percentage values are correct

---

## Lab Cleanup

### Clean Up All Resources

```bash
# Delete the namespace (removes all resources)
kubectl delete namespace resiliency-lab

# Or delete individual components
kubectl delete virtualservice --all -n resiliency-lab
kubectl delete destinationrule --all -n resiliency-lab
kubectl delete deployment --all -n resiliency-lab
kubectl delete service --all -n resiliency-lab
kubectl delete peerauthentication --all -n resiliency-lab
```

### Verify Cleanup

```bash
kubectl get all -n resiliency-lab
```

---

## Summary and Key Takeaways

### What We Learned

1. **Retries**: Automatically handle transient failures
   - Configure appropriate retry conditions and limits
   - Use with timeouts to prevent indefinite retries
   - Monitor retry success rates

2. **Timeouts**: Prevent hanging requests
   - Set reasonable timeout values based on service characteristics
   - Use different timeouts for different endpoints
   - Balance responsiveness vs. success rate

3. **Circuit Breakers**: Prevent cascading failures
   - Configure based on error thresholds and recovery times
   - Monitor circuit breaker state changes
   - Use with retries for comprehensive failure handling

4. **Fault Injection**: Test application resilience
   - Start with low percentages for production testing
   - Use for chaos engineering and disaster recovery testing
   - Combine with monitoring to understand impact

### Resiliency Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                Complete Resiliency Strategy                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Request → Timeout → Retry → Circuit Breaker → Service         │
│                                                                 │
│  1. Timeout: Prevents hanging requests                         │
│  2. Retry: Handles transient failures                          │
│  3. Circuit Breaker: Prevents cascading failures               │
│  4. Fault Injection: Tests resilience                          │
│                                                                 │
│  Combined Effect:                                               │
│  • Improved reliability                                        │
│  • Faster failure detection                                    │
│  • Graceful degradation                                        │
│  • Better user experience                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Production Readiness Checklist

- [ ] Retry policies configured for all critical services
- [ ] Appropriate timeouts set based on SLA requirements
- [ ] Circuit breakers configured with proper thresholds
- [ ] Fault injection testing performed regularly
- [ ] Monitoring and alerting set up for resiliency metrics
- [ ] Runbooks created for handling circuit breaker events
- [ ] Regular chaos engineering exercises scheduled
- [ ] Performance impact of resiliency features measured

---

## Additional Resources

### Official Documentation
- [Istio Traffic Management](https://istio.io/latest/docs/concepts/traffic-management/)
- [Istio Fault Injection](https://istio.io/latest/docs/tasks/traffic-management/fault-injection/)
- [Envoy Circuit Breaker](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/circuit_breaking)

### Community Resources
- [Istio by Example - Resiliency](https://istiobyexample.dev/)
- [Chaos Engineering with Istio](https://istio.io/latest/blog/2019/introducing-the-istio-operator/)

---

**Congratulations!** You have successfully completed the Istio Resiliency lab and learned how to implement robust failure handling in your microservices architecture.  

