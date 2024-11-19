
# Istio add-on installation on AKS - Demonstration of 'External Authorization' feature


First part of this demostration shows how to setup 'External Authorization' as a centralized authorization service in Istio on AKS.   
Second part of this demonstration shows how to setup 'External Authorization' as a sidecar in Istio on AKS.  


## Demo 1 - Setup 'External Authorization' as a centralized authorization service (within a cluster)

### Setup environment variables  (assuming that the AKS cluster is already created with Istio add-on enabled)

```bash
export CLUSTER=aksistio1
export RESOURCE_GROUP=aksistiorg
export LOCATION=eastus2
```



```bash

az aks show --resource-group ${RESOURCE_GROUP} --name ${CLUSTER}  --query 'serviceMeshProfile.mode'

az aks show --name $CLUSTER --resource-group $RESOURCE_GROUP --query 'serviceMeshProfile'

k get cm istio-shared-configmap-asm-1-22 -n aks-istio-system -o yaml

k get ns 
k get all -n aks-istio-system
k get all -n aks-istio-ingress
k get all -n aks-istio-egress


az aks show --resource-group ${RESOURCE_GROUP} --name ${CLUSTER}  --query 'serviceMeshProfile.istio.revisions'
```




Configmap

A default ConfigMap (for example, istio-asm-1-18 for revision asm-1-18) is created in aks-istio-system namespace on the cluster when the Istio add-on is enabled. 
Issue the following command to get the ConfigMap:

```bash
k get cm istio-asm-1-22 -n aks-istio-system -o yaml
```


### Update the ConfigMap to add the external authorizers

Use the output of --query 'serviceMeshProfile.istio.revisions' for the revision number. In the below example, the revision number is 1-22

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-shared-configmap-asm-1-22
  namespace: aks-istio-system
data:
  mesh: |-
    # Add the following content to define the external authorizers.
    extensionProviders:
    - name: "sample-ext-authz-grpc"
      envoyExtAuthzGrpc:
        service: "ext-authz.testns.svc.cluster.local"
        port: "9000"
    - name: "sample-ext-authz-http"
      envoyExtAuthzHttp:
        service: "ext-authz.testns.svc.cluster.local"
        port: "8000"
        includeRequestHeadersInCheck: ["x-ext-authz"]
EOF
```


### Deploy sample application (httpbin) in a test namespace

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: httpbin
  namespace: testns
  labels:
    app: httpbin
    service: httpbin
spec:
  ports:
  - name: http
    port: 8000
    targetPort: 8080
  selector:
    app: httpbin
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: httpbin
  namespace: testns
spec:
  replicas: 1
  selector:
    matchLabels:
      app: httpbin
      version: v1
  template:
    metadata:
      labels:
        app: httpbin
        version: v1
    spec:
      serviceAccountName: httpbin
      containers:
      - image: docker.io/mccutchen/go-httpbin:v2.15.0
        imagePullPolicy: IfNotPresent
        name: httpbin
        ports:
        - containerPort: 8080
EOF
```


### Deploy the external authorization service

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: ext-authz
  labels:
    app: ext-authz
spec:
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  - name: grpc
    port: 9000
    targetPort: 9000
  selector:
    app: ext-authz
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ext-authz
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ext-authz
  template:
    metadata:
      labels:
        app: ext-authz
    spec:
      containers:
      - image: gcr.io/istio-testing/ext-authz:latest
        imagePullPolicy: IfNotPresent
        name: ext-authz
        ports:
        - containerPort: 8000
        - containerPort: 9000
EOF
```

### Setup Authorization Policy for the external authorization service

```bash
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: ext-authz
  namespace: testns
spec:
  selector:
    matchLabels:
      app: httpbin
  action: CUSTOM
  provider:
    # The provider name must match the extension provider defined in the mesh config.
    # You can also replace this with sample-ext-authz-http to test the other external authorizer definition.
    name: sample-ext-authz-grpc
  rules:
  # The rules specify when to trigger the external authorizer.
  - to:
    - operation:
        paths: ["/headers"]
EOF
```

### Test the setup


k -n testns run netshoot --image=nicolaka/netshoot -- sh -c 'sleep 2000'

Following command should return the results from httpbin service
```bash
k exec netshoot -n testns -it -- curl httpbin:8000 
```

Following command should fail with 'denied by ext_authz for not found header `x-ext-authz: allow` in the request'  
```bash
k exec netshoot -n testns -it -- curl httpbin:8000/headers
```
denied by ext_authz for not found header `x-ext-authz: allow` in the requestE1118 19:54:03.532680   27457 v3.go:79] EOF






## Demo 2 - Setup 'External Authorization' as a sidecar in Istio on AKS

We will configure sample-ext-authz-grpc-local as a sidecar provider for 'External Authorization' in the mesh.

### Change the ConfigMap to add the external authorizers
```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-shared-configmap-asm-1-22
  namespace: aks-istio-system
data:
  mesh: |-
    # Add the following content to define the external authorizers.
    extensionProviders:
    - name: "sample-ext-authz-grpc"
      envoyExtAuthzGrpc:
        service: "ext-authz.testns.svc.cluster.local"
        port: "9000"
    - name: "sample-ext-authz-http"
      envoyExtAuthzHttp:
        service: "ext-authz.testns.svc.cluster.local"
        port: "8000"
        includeRequestHeadersInCheck: ["x-ext-authz"]
    - name: "sample-ext-authz-grpc-local"
      envoyExtAuthzGrpc:
        service: "external-authz-grpc.local"
        port: "9000"
        includeRequestHeadersInCheck: ["x-ext-authz"]
EOF
```

### ServicEntry for the external authorization service


```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1
kind: ServiceEntry
metadata:
  name: external-authz-grpc-local
  namespace: testns
spec:
  hosts:
  - "external-authz-grpc.local" # The service name to be used in the extension provider in the mesh config.
  endpoints:
  - address: "127.0.0.1"
  ports:
  - name: grpc
    number: 9000 # The port number to be used in the extension provider in the mesh config.
    protocol: GRPC
  resolution: STATIC
EOF
```


### Setup Authorization Policy for the external authorization service

```bash
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: ext-authz
  namespace: testns
spec:
  selector:
    matchLabels:
      app: httpbin
  action: CUSTOM
  provider:
    # The provider name must match the extension provider defined in the mesh config.
    # You can also replace this with sample-ext-authz-http to test the other external authorizer definition.
    name: sample-ext-authz-grpc-local
  rules:
  # The rules specify when to trigger the external authorizer.
  - to:
    - operation:
        paths: ["/headers"]
EOF
```

### Deploy httpbin service with external authorization as a sidecar

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: httpbin
  namespace: testns
  labels:
    app: httpbin
    service: httpbin
spec:
  ports:
  - name: http
    port: 8000
    targetPort: 8080
  selector:
    app: httpbin
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: httpbin
  namespace: testns
spec:
  replicas: 1
  selector:
    matchLabels:
      app: httpbin
      version: v1
  template:
    metadata:
      labels:
        app: httpbin
        version: v1
    spec:
      serviceAccountName: httpbin
      containers:
      - image: docker.io/mccutchen/go-httpbin:v2.15.0
        imagePullPolicy: IfNotPresent
        name: httpbin
        ports:
        - containerPort: 8080
      - image: gcr.io/istio-testing/ext-authz:latest
        imagePullPolicy: IfNotPresent
        name: ext-authz
        ports:
        - containerPort: 8000
        - containerPort: 9000
EOF
```


### Test the setup

Following command should return the results from httpbin service
```bash
k exec netshoot -n testns -it -- curl httpbin:8000 
```

Following command should fail with 'denied by ext_authz for not found header `x-ext-authz: allow` in the request'  
```bash
k exec netshoot -n testns -it -- curl httpbin:8000/headers
```


