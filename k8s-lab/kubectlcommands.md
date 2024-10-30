# Kubectl   



### 

kubectlcommands.md



# Kubernetes and kubectl Commands for Beginners

## 1. Get Cluster Information
```bash
kubectl cluster-info
```
Displays information about the Kubernetes cluster, including the master and DNS services.

## 2. Get Nodes
```bash
kubectl get nodes
```
Lists all the nodes in the cluster, showing their status, roles, age, and version.

## 3. Describe Node
```bash
kubectl describe node <node-name>
```
Provides detailed information about a specific node, including its capacity, conditions, and allocated resources.

## 4. Get Pods
```bash
kubectl get pods
```
Lists all the pods in the default namespace, showing their status, age, and other details.

## 5. Get Pods in All Namespaces
```bash
kubectl get pods --all-namespaces
```
Lists all the pods across all namespaces in the cluster.

## 6. Describe Pod
```bash
kubectl describe pod <pod-name>
```
Provides detailed information about a specific pod, including its containers, events, and resource usage.

## 7. Get Services
```bash
kubectl get services
```
Lists all the services in the default namespace, showing their type, cluster IP, external IP, and ports.

## 8. Get Deployments
```bash
kubectl get deployments
```
Lists all the deployments in the default namespace, showing their status, replicas, and other details.

## 9. Describe Deployment
```bash
kubectl describe deployment <deployment-name>
```
Provides detailed information about a specific deployment, including its strategy, replicas, and events.

## 10. Get Namespaces
```bash
kubectl get namespaces
```
Lists all the namespaces in the cluster, showing their status and age.

## 11. Create Namespace
```bash
kubectl create namespace <namespace-name>
```
Creates a new namespace in the cluster.

## 12. Delete Namespace
```bash
kubectl delete namespace <namespace-name>
```
Deletes a namespace and all the resources within it.

## 13. Apply Configuration
```bash
kubectl apply -f <file.yaml>
```
Applies the configuration specified in a YAML file to the cluster, creating or updating resources as needed.

## 14. Delete Resource
```bash
kubectl delete -f <file.yaml>
```
Deletes the resources specified in a YAML file from the cluster.

## 15. Get Logs
```bash
kubectl logs <pod-name>
```
Displays the logs of a specific pod, useful for debugging and monitoring.

## 16. Execute Command in Pod
```bash
kubectl exec -it <pod-name> -- <command>
```
Executes a command inside a specific pod, allowing you to interact with the pod's container.

## 17. Port Forward
```bash
kubectl port-forward <pod-name> <local-port>:<pod-port>
```
Forwards a local port to a port on a pod, allowing you to access the pod's services locally.

## 18. Scale Deployment
```bash
kubectl scale deployment <deployment-name> --replicas=<number>
```
Scales a deployment to the specified number of replicas.

## 19. Get Events
```bash
kubectl get events
```
Lists all the events in the default namespace, showing recent activities and changes in the cluster.

## 20. Get ConfigMaps
```bash
kubectl get configmaps
```
Lists all the ConfigMaps in the default namespace, showing their names and data.
```

These commands provide a solid foundation for beginners to start exploring and managing Kubernetes clusters using `kubectl`.