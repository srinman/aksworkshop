# Istio Ingress Gateway

## Enable Istio Ingress Gateway  (AKS managed)

```bash
export CLUSTER=aksistio4
export RESOURCE_GROUP=aksistiorg
export LOCATION=eastus2
```

```bash
az aks mesh enable-ingress-gateway --resource-group $RESOURCE_GROUP --name $CLUSTER --ingress-gateway-type external  
az aks show --name $CLUSTER --resource-group $RESOURCE_GROUP --query 'serviceMeshProfile'
```

k get all -n aks-istio-ingress


## Sample application and Istio Ingress gateway

Istio comes with Ingress gateway.  We can also enable external ingress gateway.  In this lab, we will use the external ingress gateway.  There is no need to deploy nginx ingress controller.  


### Deploy Bookinfo application

```bash

k get ns --show-labels | grep -i asm-  

kubectl label namespace default istio.io/rev=asm-1-22

kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.18/samples/bookinfo/platform/kube/bookinfo.yaml

k get all  

kubectl port-forward service/productpage 9080:9080

```

### Deploy external ingress gateway

```bash

az aks mesh enable-ingress-gateway --resource-group $RESOURCE_GROUP --name $CLUSTER --ingress-gateway-type external  

k get all -n aks-istio-ingress

```

aks show output should look like this 
```json
  "serviceMeshProfile": {
    "istio": {
      "certificateAuthority": null,
      "components": {
        "egressGateways": null,
        "ingressGateways": [
          {
            "enabled": true,
            "mode": "External"
          }
        ]
      },
      "revisions": [
        "asm-1-21"
      ]
    },
    "mode": "Istio"
  },
```

### Deploy Gateway and VirtualService  


istioctl -n aks-istio-ingress proxy-config listener deploy/aks-istio-ingressgateway-external-asm-1-22  

Apply the gateway and virtual service for the bookinfo application   

The Gateway resource defines ports, protocols, and virtual hosts that are exposed by the Gateway.  Gateway is a top-level resource that allows you to configure a load balancer operating at the edge of the mesh.  

The VirtualService resource defines the routing rules for the traffic that matches the Gateway.  It is used to configure the routing of the traffic to the services.  


```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: bookinfo-gateway-external
spec:
  selector:
    istio: aks-istio-ingressgateway-external
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
EOF
```

istioctl -n aks-istio-ingress proxy-config listener deploy/aks-istio-ingressgateway-external-asm-1-22  
istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22  
istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22 -o json --name http.80   
k get gateway
k get virtualservice

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: bookinfo-vs-external
spec:
  hosts:
  - "*"
  gateways:
  - bookinfo-gateway-external
  http:
  - match:
    - uri:
        exact: /productpage
    - uri:
        prefix: /static
    - uri:
        exact: /login
    - uri:
        exact: /logout
    - uri:
        prefix: /api/v1/products
    route:
    - destination:
        host: productpage
        port:
          number: 9080
EOF
```


```bash
istioctl -n aks-istio-ingress proxy-config listener deploy/aks-istio-ingressgateway-external-asm-1-22  
istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22  
istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22 -o json --name http.80   
k get gateway
k get virtualservice
```


Get external IP address of the ingress gateway  
```
kubectl get svc aks-istio-ingressgateway-external -n aks-istio-ingress
```

Open the browser and navigate to the external IP address of the ingress gateway to see the bookinfo application. 
Make sure that you enter IP:port/productpage to see the application. Review virtual service configuration to see the paths that are allowed.  


k get pod  -n aks-istio-ingress
check the logs of the pod to see envoy proxy startup and access log. 
You may not see any access log yet.  


Apply the following configmap to enable access log.

```yaml
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
```

Now check envoy proxy logs again. You should see access logs. 

k logs  -n aks-istio-ingress -l app=aks-istio-ingressgateway-external

```log
[2024-09-13T01:03:55.177Z] "GET /productpage HTTP/1.1" 200 - via_upstream - "-" 0 5289 86 86 "10.224.0.5" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0" "a50c8b8a-99ec-4a7e-bacc-9c8900c34f26" "52.252.69.106" "10.244.1.7:9080" outbound|9080||productpage.default.svc.cluster.local 10.244.2.12:37132 10.244.2.12:80 10.224.0.5:39753 - -
[2024-09-13T01:03:55.438Z] "GET /productpage HTTP/1.1" 200 - via_upstream - "-" 0 4294 31 31 "10.224.0.5" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0" "1c5d304c-fca2-40b9-8d64-0faf8173ba6f" "52.252.69.106" "10.244.1.7:9080" outbound|9080||productpage.default.svc.cluster.local 10.244.2.12:37132 10.244.2.12:80 10.224.0.5:39753 - -
```




```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: sampleapp-gateway-external
  namespace: sampleapp
spec:
  selector:
    istio: aks-istio-ingressgateway-external
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - istiosampleapp.srinman.com
EOF
```

istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22  
istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22 -o json --name http.80   
k get gateway -A
k get virtualservice -A

```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: sampleapp-vs-external
  namespace: sampleapp
spec:
  hosts:
  - istiosampleapp.srinman.com
  gateways:
  - sampleapp-gateway-external
  http:
  - match:
    - uri:
        exact: /sampleapp
    rewrite:
      uri: /authors
    route:
    - destination:
        host: istioapi
        port:
          number: 80
EOF
```

k get virtualservice -A
curl -v http://135.232.45.103:80/sampleapp --header "Host: istiosampleapp.srinman.com"



istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22  
istioctl -n aks-istio-ingress proxy-config route deploy/aks-istio-ingressgateway-external-asm-1-22 -o json --name http.80   
k get gateway -A
k get virtualservice -A
k logs  -n aks-istio-ingress -l app=aks-istio-ingressgateway-external




### Delete   

k delete -f https://raw.githubusercontent.com/istio/istio/release-1.18/samples/bookinfo/platform/kube/bookinfo.yaml  

