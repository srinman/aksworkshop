# Resiliency with Istio  

Istio provides a number of features to help you build resilient applications.  These features include:  

- Retries
- Circuit Breaker
- Timeouts
- Fault Injection




## Retries


### Prep the Environment
Create a new namespace called `retryns` and label it with the Istio revision:  

```bash
k create ns retryns  
kubectl label namespace retryns istio.io/rev=asm-1-22  
```


### Deploy the Flask App (appflaky)

Deploy the flask app and a load balancer service with the following command:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: appflaky
  namespace: retryns
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
  namespace: retryns
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



### Use tools/resiliencytest.py to test the appflaky service

Get IP from the service to test the appflaky service from your local machine:

```bash
k get svc -n retryns  
```


```bash
export ENDPOINT_URL="http://135.224.217.16/unstable-endpoint"
python tools/resiliencytest.py  
```

Even though the appflaky is added to service mesh, it is still accepting traffic from outside the mesh.  To restrict the traffic to the appflaky service to only the services within the mesh, apply the following PeerAuthentication policy.

```bash
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: retryns
spec:
  mtls:
    mode: STRICT
EOF
```


### Deploy the client app (clientapp)

Deploy the client app with the following command:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: client
  namespace: retryns
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
          value: "http://appflaky.retryns.svc.cluster.local/unstable-endpoint"
EOF
```

Monitor the logs of the client app to see the succcess/failure of the requests:

```bash
k logs  -n retryns -l app=client
```

### Apply the Retry Policy 

Apply the following retry policy to the client app:

attempts is set to 10 and perTryTimeout is set to 5ms. This is to simulate the retries in a short time frame.

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: appflaky
  namespace: retryns
spec:
  hosts:
  - appflaky.retryns.svc.cluster.local
  http:
  - route:
    - destination:
        host: appflaky
        port:
          number: 80
    retries:
      attempts: 10
      perTryTimeout: 5ms
EOF
```
Check logs of the client app to see the retries:

```bash 
kubectl logs -l app=client -n retryns
```
Understand the reason for the success/failure of the requests.  Default retry policy settings are not addressing retries.  The client app is still getting errors.


### Apply the Retry Policy with Retry on 5xx

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: appflaky
  namespace: retryns
spec:
  hosts:
  - appflaky.retryns.svc.cluster.local
  http:
  - route:
    - destination:
        host: appflaky
        port:
          number: 80
    retries:
      attempts: 10
      perTryTimeout: 5ms
      retryOn: "5xx"
EOF
```

Check logs of the client app to see the retries:

```bash 
kubectl logs -l app=client -n retryns
```

Confirm success rate of 100% for the requests.  

Use tools/resiliencytest.py to test the appflaky service from your local machine:

Let's also relax the PeerAuthentication policy to allow traffic from outside the mesh. 
```bash
kubectl apply -f - <<EOF
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: retryns
spec:
  mtls:
    mode: PERMISSIVE
EOF
```

```bash
export ENDPOINT_URL="http://135.232.54.218/unstable-endpoint"
python tools/resiliencytest.py  
```

You should see a mixed success and failure rate since the retries are not being applied for the calls from outside the mesh.  

kubectl logs -l app=aks-istio-ingressgateway-external -n aks-istio-ingress
kubectl logs -l app=appflaky -n retryns
kubectl logs -l app=client -n retryns

