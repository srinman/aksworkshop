
# Istio add-on installation on AKS

## Prerequisites

### Tools

- Azure CLI
- kubectl
- helm
- istioctl

#### Azure CLI

```bash
az --version
```

#### kubectl

```bash
kubectl version --client
```

#### istioctl

```bash
istioctl version
```




### Create AKS cluster with Istio add-on

```bash
export CLUSTER=aksistio1
export RESOURCE_GROUP=aksistiorg
export LOCATION=eastus2
```



```bash

az aks mesh get-revisions --location ${LOCATION} -o table  

az group create --name ${RESOURCE_GROUP} --location ${LOCATION}

az aks create --resource-group ${RESOURCE_GROUP} --name ${CLUSTER} --enable-asm --generate-ssh-keys


az aks show --resource-group ${RESOURCE_GROUP} --name ${CLUSTER} 

az aks show --resource-group ${RESOURCE_GROUP} --name ${CLUSTER}  --query 'serviceMeshProfile.mode'

az aks show --name $CLUSTER --resource-group $RESOURCE_GROUP --query 'serviceMeshProfile'

az aks get-credentials --resource-group ${RESOURCE_GROUP} --name ${CLUSTER}

k get ns 
k get all -n aks-istio-system
k get all -n aks-istio-ingress
k get all -n aks-istio-egress


az aks show --resource-group ${RESOURCE_GROUP} --name ${CLUSTER}  --query 'serviceMeshProfile.istio.revisions'
```

Note down the revision number.  


### Basic Istio configurations 

Understand Istio CRDs 

```bash
k get crd | grep istio  
authorizationpolicies.security.istio.io                      2024-10-21T20:57:52Z
destinationrules.networking.istio.io                         2024-10-21T20:57:52Z
envoyfilters.networking.istio.io                             2024-10-21T20:57:52Z
gateways.networking.istio.io                                 2024-10-21T20:57:52Z
peerauthentications.security.istio.io                        2024-10-21T20:57:52Z
proxyconfigs.networking.istio.io                             2024-10-21T20:57:52Z
requestauthentications.security.istio.io                     2024-10-21T20:57:52Z
serviceentries.networking.istio.io                           2024-10-21T20:57:52Z
sidecars.networking.istio.io                                 2024-10-21T20:57:52Z
telemetries.telemetry.istio.io                               2024-10-21T20:57:52Z
virtualservices.networking.istio.io                          2024-10-21T20:57:52Z
wasmplugins.extensions.istio.io                              2024-10-21T20:57:52Z
workloadentries.networking.istio.io                          2024-10-21T20:57:52Z
workloadgroups.networking.istio.io                           2024-10-21T20:57:52Z 
```

Configmap

A default ConfigMap (for example, istio-asm-1-18 for revision asm-1-18) is created in aks-istio-system namespace on the cluster when the Istio add-on is enabled. 
Issue the following command to get the ConfigMap:

```bash
k get cm istio-asm-1-22 -n aks-istio-system -o yaml
```

Use the output of --query 'serviceMeshProfile.istio.revisions' to get the revision number


**Attention**  Use of Telemetry is recommended.   Following configmap can be skipped if you follow Telemetry method. 
In the below example, the revision number is 1-22
```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-shared-configmap-asm-1-22
  namespace: aks-istio-system
data:
  mesh: |-
    accessLogFile: /dev/stdout
    defaultConfig:
      holdApplicationUntilProxyStarts: true
EOF
```


Telemtry:   

```bash
cat <<EOF | kubectl apply -n aks-istio-system -f -
apiVersion: telemetry.istio.io/v1
kind: Telemetry
metadata:
  name: mesh-logging-default
spec:
  accessLogging:
  - providers:
    - name: envoy
EOF
```



###  Create a sample application and check sidecar injection

change registryname to yours  
cd istioapi
```bash
az acr build --registry srinmantest --image istioapi:v1 --file Dockerfilev1 .
az acr build --registry srinmantest --image istioapi:v2 --file Dockerfilev2 .
az acr build --registry srinmantest --image istioapi:v3 --file Dockerfilev3 .
az acr build --registry srinmantest --image appflaky:v1 --file Dockerfileflaky .
az acr build --registry srinmantest --image echocaller:v1 --file Dockerfileechocaller .
az acr build --registry srinmantest --image clientapp:v1 --file Dockerfileclientapp .
```

Attach ACR to AKS  
    
```bash
az aks update --resource-group ${RESOURCE_GROUP} --name ${CLUSTER} --attach-acr "/subscriptions/.../Microsoft.ContainerRegistry/registries/srinmantest"
```   

```bash
k create ns sampleapp
k create ns testns
```


```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: istioapi
  namespace: sampleapp
spec:
  replicas: 2
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
        imagePullPolicy: Always
        ports:
        - containerPort: 5000
---
apiVersion: v1
kind: Service
metadata:
  name: istioapi
  namespace: sampleapp
spec:
  selector:
    app: istioapi
  ports:
  - protocol: TCP
    port: 80
    targetPort: 5000
EOF
```

Check connectivity to the application deployed.  
```bash
k -n testns run netshoot --image=nicolaka/netshoot -- sh -c 'sleep 2000'
k -n testns exec -it netshoot -- curl istioapi.sampleapp.svc.cluster.local
```

```bash
kubectl label namespace sampleapp istio.io/rev=asm-1-22
k get pod -n sampleapp
k delete pod xyz -n sampleapp
k get pod -n sampleapp
k logs -l app=istioapi -c istio-proxy  -n sampleapp
```

You should see the sidecar injected in the pod.  You should also see the logs. 


