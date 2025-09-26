# Hub-to-Spoke Direct Deployment using Managed Identity (Workload identity)

This document demonstrates how to use the hub cluster's managed identity to directly deploy resources to a spoke cluster without ArgoCD. This showcases the underlying permissions and authentication mechanisms that enable the hub-spoke architecture.

## Prerequisites


```bash
# Set spoke cluster information
SPOKE_CLUSTER_NAME="myorg-dev-aks"
SPOKE_RG="myorg-dev-rg"

# Get cluster details
echo "Getting spoke cluster details..."
SPOKE_CLUSTER_FQDN=$(az aks show --resource-group $SPOKE_RG --name $SPOKE_CLUSTER_NAME --query fqdn -o tsv)
SPOKE_CLUSTER_ID=$(az aks show --resource-group $SPOKE_RG --name $SPOKE_CLUSTER_NAME --query id -o tsv)

echo "Spoke Cluster: $SPOKE_CLUSTER_NAME"
echo "Resource Group: $SPOKE_RG"
echo "FQDN: $SPOKE_CLUSTER_FQDN"
echo "Cluster ID: $SPOKE_CLUSTER_ID"
echo "Server Endpoint: https://$SPOKE_CLUSTER_FQDN"
```

###  Verify Hub Identity Permissions on Spoke Cluster

```bash
# Get hub cluster managed identity details
HUB_RG="myorg-hub-rg"
HUB_IDENTITY_NAME="myorg-hub-identity"
HUB_CLUSTER_NAME="myorg-hub-aks"

HUB_IDENTITY_PRINCIPAL_ID=$(az identity show --resource-group $HUB_RG --name $HUB_IDENTITY_NAME --query principalId -o tsv)
HUB_IDENTITY_CLIENT_ID=$(az identity show --resource-group $HUB_RG --name $HUB_IDENTITY_NAME --query clientId -o tsv)

echo "Hub Identity Principal ID: $HUB_IDENTITY_PRINCIPAL_ID"
echo "Hub Identity Client ID: $HUB_IDENTITY_CLIENT_ID"

# Create federated credentials for workload identity authentication
echo "Creating federated credentials for workload identity..."
AKS_OIDC_ISSUER=$(az aks show --resource-group $HUB_RG --name $HUB_CLUSTER_NAME --query "oidcIssuerProfile.issuerUrl" -o tsv)

az identity federated-credential create \
    --name "hub-to-spoke-federated-credential" \
    --identity-name $HUB_IDENTITY_NAME \
    --resource-group $HUB_RG \
    --issuer $AKS_OIDC_ISSUER \
    --subject system:serviceaccount:hub-operations:hub-to-spoke-sa \
    --audience api://AzureADTokenExchange

echo "✅ Federated credentials created for workload identity"




###  Run Deployment from Hub Cluster

Execute the deployment from a pod running on the hub cluster using the managed identity:

```bash
# Ensure you're on the hub cluster context
kubectl config use-context hub-cluster

# Create a deployment job on the hub cluster that will deploy to spoke cluster
cat > hub-deployment-job.yaml << EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: hub-to-spoke-deployment
  namespace: hub-operations
  labels:
    job-type: cross-cluster-deployment
spec:
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        azure.workload.identity/use: "true"
        job-type: cross-cluster-deployment
    spec:
      serviceAccountName: hub-to-spoke-sa
      restartPolicy: OnFailure
      containers:
      - name: deployment-container
        image: mcr.microsoft.com/azure-cli:latest
        env:
        - name: SPOKE_CLUSTER_NAME
          value: "$SPOKE_CLUSTER_NAME"
        - name: SPOKE_RG
          value: "$SPOKE_RG"
        command: ["/bin/bash"]
        args:
          - -c
          - |
            set -e
            echo "🚀 Starting hub-to-spoke deployment"
            echo "Target: \$SPOKE_CLUSTER_NAME in \$SPOKE_RG"
            
            # Install kubectl
            echo "Installing kubectl..."
            curl -LO "https://dl.k8s.io/release/\$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
            chmod +x kubectl && mv kubectl /usr/local/bin/
            echo "✅ kubectl installed"
            
            # Try to install kubelogin - use fallback if needed
            echo "Installing kubelogin..."
            if curl -L https://github.com/Azure/kubelogin/releases/latest/download/kubelogin-linux-amd64.tar.gz | tar xz; then
                mv bin/linux_amd64/kubelogin /usr/local/bin/ && chmod +x /usr/local/bin/kubelogin
                echo "✅ kubelogin installed via tar"
            else
                echo "⚠️  kubelogin installation failed, trying alternative..."
                # Download zip and try python extraction
                curl -L "https://github.com/Azure/kubelogin/releases/latest/download/kubelogin-linux-amd64.zip" -o kubelogin.zip
                python3 -c "import zipfile; zipfile.ZipFile('kubelogin.zip').extractall()"
                mv bin/linux_amd64/kubelogin /usr/local/bin/ && chmod +x /usr/local/bin/kubelogin
                echo "✅ kubelogin installed via python"
            fi
            
            # Verify installations
            kubectl version --client || kubectl version
            kubelogin --version
            
            # Check workload identity
            echo "Environment check:"
            echo "AZURE_CLIENT_ID: \$AZURE_CLIENT_ID"
            echo "AZURE_TENANT_ID: \$AZURE_TENANT_ID"
            echo "AZURE_FEDERATED_TOKEN_FILE: \$AZURE_FEDERATED_TOKEN_FILE"
            
            # Authenticate
            echo "Authenticating with Azure..."
            if [ -f "\$AZURE_FEDERATED_TOKEN_FILE" ]; then
                az login --service-principal --username "\$AZURE_CLIENT_ID" --tenant "\$AZURE_TENANT_ID" --federated-token "\$(cat \$AZURE_FEDERATED_TOKEN_FILE)"
                echo "✅ Authenticated"
            else
                echo "❌ Token file not found: \$AZURE_FEDERATED_TOKEN_FILE"
                exit 1
            fi
            
            # Get credentials - use correct command for this Azure CLI version
            echo "Getting AKS credentials..."
            az aks get-credentials --resource-group \$SPOKE_RG --name \$SPOKE_CLUSTER_NAME --overwrite-existing
            
            # Configure for workload identity
            echo "Converting kubeconfig for workload identity..."
            kubelogin convert-kubeconfig -l workloadidentity
            
            # Test connection
            echo "Testing cluster connectivity..."
            kubectl cluster-info --request-timeout=30s
            
            # Deploy resources
            echo "📦 Creating namespace..."
            kubectl create namespace demo-app --dry-run=client -o yaml | kubectl apply -f -
            
            echo "🚀 Deploying nginx..."
            kubectl create deployment nginx-demo --image=nginx:1.25 --replicas=3 -n demo-app
            kubectl set resources deployment nginx-demo --requests=cpu=100m,memory=128Mi --limits=cpu=200m,memory=256Mi -n demo-app
            
            echo "🌐 Creating service..."
            kubectl expose deployment nginx-demo --port=80 --type=LoadBalancer -n demo-app --name=nginx-demo-service
            
            # Wait for deployment
            echo "⏳ Waiting for deployment..."
            kubectl wait --for=condition=available --timeout=300s deployment/nginx-demo -n demo-app
            
            echo "📋 Final status:"
            kubectl get all -n demo-app
            echo "✅ Deployment completed!"
EOF

# Create the hub-operations namespace if it doesn't exist
echo "Creating hub-operations namespace..."
kubectl create namespace hub-operations --dry-run=client -o yaml | kubectl apply -f -

# Create the service account for workload identity
echo "Creating service account for workload identity..."
cat > hub-to-spoke-sa.yaml << EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: hub-to-spoke-sa
  namespace: hub-operations
  annotations:
    azure.workload.identity/client-id: "$HUB_IDENTITY_CLIENT_ID"
  labels:
    azure.workload.identity/use: "true"
EOF

kubectl apply -f hub-to-spoke-sa.yaml

# Apply the job
kubectl apply -f hub-deployment-job.yaml

echo "✅ Hub-to-spoke deployment job created"
