
## Istio Traffic Management


### VirtualService


k create ns testproduct
kubectl label namespace testproduct istio.io/rev=asm-1-22


Let's deploy a test application in the testproduct namespace. 
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

### Traffic Split

### Traffic Shifting


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