# Build commands

cd istioapi
```bash
az acr build --registry srinmantest --image istioapi:v1 --file Dockerfilev1 --platform linux/arm64 .
az acr build --registry srinmantest --image istioapi:v2 --file Dockerfilev2 --platform linux/arm64 .
az acr build --registry srinmantest --image istioapi:v3 --file Dockerfilev3 --platform linux/arm64 .
az acr build --registry srinmantest --image appflaky:v1 --file Dockerfileflaky --platform linux/arm64 .
az acr build --registry srinmantest --image echocaller:v1 --file Dockerfileechocaller --platform linux/arm64 .
az acr build --registry srinmantest --image clientapp:v1 --file Dockerfileclientapp --platform linux/arm64 .
az acr build --registry srinmantest --image slowapi:v1 --file Dockerfileslowapi --platform linux/arm64 .
```