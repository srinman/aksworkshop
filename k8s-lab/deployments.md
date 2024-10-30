Sure, I'll update the instructions to include the `kubectl apply -f - <<EOF` and `EOF` syntax for each YAML file to make it easier to apply the configurations directly from the command line.


# Kubernetes Deployment Strategies

## Introduction
Kubernetes supports various deployment strategies to manage application updates. The primary components involved are deployments, replica sets, pods, and labels.

- **Deployment**: Manages the desired state of your application, including the number of replicas and the update strategy.
- **ReplicaSet**: Ensures a specified number of pod replicas are running at any given time.
- **Pod**: The smallest deployable unit in Kubernetes, which runs your containerized application.
- **Labels**: Key-value pairs attached to objects like pods and services, used for organization and selection.

## Rolling Update Strategy

### Step 1: Create a Namespace

Create a new namespace called `deploymentns`:

```bash
kubectl create namespace deploymentns
```

### Step 2: Create a Deployment with Version v1

Apply the following configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: istioapi-deployment
  namespace: deploymentns
  labels:
    app: istioapi
spec:
  replicas: 3
  selector:
    matchLabels:
      app: istioapi
  template:
    metadata:
      labels:
        app: istioapi
    spec:
      containers:
      - name: istioapi
        image: srinmantest.azurecr.io/istioapi:v1
        ports:
        - containerPort: 5000
EOF
```

### Step 3: Verify the Deployment

Check the status of the deployment, replica sets, and pods in the `deploymentns` namespace:

```bash
kubectl get deployments -n deploymentns
kubectl get replicasets -n deploymentns
kubectl get pods -n deploymentns
```

### Step 4: Update the Deployment to Version v2

Open a terminal
```bash
while true; do kubectl rollout status deployment/istioapi-deployment -n deploymentns; sleep 1; done
```
Apply the following configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: istioapi-deployment
  namespace: deploymentns
  labels:
    app: istioapi
spec:
  replicas: 3
  selector:
    matchLabels:
      app: istioapi
  template:
    metadata:
      labels:
        app: istioapi
    spec:
      containers:
      - name: istioapi
        image: srinmantest.azurecr.io/istioapi:v2
        ports:
        - containerPort: 5000
EOF
```

### Step 5: Monitor the Rolling Update

Watch the rollout status to see the progress of the update:

```bash
kubectl rollout status deployment/istioapi-deployment -n deploymentns

while true; do kubectl rollout status deployment/istioapi-deployment -n deploymentns; sleep 1; done
```

### Step 6: Verify the Update

Check the status of the deployment, replica sets, and pods in the `deploymentns` namespace to ensure the update was successful:

```bash
kubectl get deployments -n deploymentns
kubectl get replicasets -n deploymentns
kubectl get pods -n deploymentns
```

## Blue-Green Deployment Strategy

### Step 1: Create a Deployment for Version v1 (Blue)

Apply the following configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: istioapi-blue
  namespace: deploymentns
  labels:
    app: istioapi
    version: blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: istioapi
      version: blue
  template:
    metadata:
      labels:
        app: istioapi
        version: blue
    spec:
      containers:
      - name: istioapi
        image: srinmantest.azurecr.io/istioapi:v1
        ports:
        - containerPort: 5000
EOF
```

### Step 2: Create a Service for the Blue Deployment

Tips: You can setup service and port-forward to test the deployment. 

In a new terminal, run the following command to forward traffic to the service:
```bash
kubectl port-forward svc/istioapi-service -n deploymentns 8090:80
```
In another terminal, run the following command to test the deployment:
```bash
while true; do curl localhost:8090/authors; sleep 1; done
```



Apply the following configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: istioapi-service
  namespace: deploymentns
spec:
  selector:
    app: istioapi
    version: blue
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5000
EOF
```

### Step 3: Verify the Blue Deployment

Check the status of the deployment, service, and pods in the `deploymentns` namespace:

```bash
kubectl get deployments -n deploymentns
kubectl get services -n deploymentns
kubectl get pods -n deploymentns
```

### Step 4: Create a Deployment for Version v2 (Green)

Apply the following configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: istioapi-green
  namespace: deploymentns
  labels:
    app: istioapi
    version: green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: istioapi
      version: green
  template:
    metadata:
      labels:
        app: istioapi
        version: green
    spec:
      containers:
      - name: istioapi
        image: srinmantest.azurecr.io/istioapi:v2
        ports:
        - containerPort: 5000
EOF
```

### Step 5: Update the Service to Point to the Green Deployment

Apply the following configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: istioapi-service
  namespace: deploymentns
spec:
  selector:
    app: istioapi
    version: green
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5000
EOF
```

### Step 6: Verify the Green Deployment

Check the status of the deployment, service, and pods in the `deploymentns` namespace to ensure the update was successful:

```bash
kubectl get deployments -n deploymentns
kubectl get services -n deploymentns
kubectl get pods -n deploymentns
```


### Step 5: Update the Service to Point to Blue or Green Deployment


```bash
while true; do curl localhost:8090/authors; sleep 1; done
``` 

At this time you can switch the service to point to the blue or green deployment.

Apply the following configuration:

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: istioapi-service
  namespace: deploymentns
spec:
  type: LoadBalancer
  selector:
    app: istioapi
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5000
EOF
```

Test the deployment:

```bash
while true; do curl 48.214.24.42/authors; sleep 1; done
```

## More insights

Review MC AKS cluster resource group to see the load balancer IP address.

Review NSG rules to see the load balancer rules.


## Conclusion
These examples demonstrate how to use Kubernetes deployments, replica sets, pods, and labels to manage application updates using rolling update and blue-green deployment strategies. By following these steps, you can effectively deploy and update your applications in a Kubernetes cluster.
```

