# Build commands

cd istioapi
```bash
az acr build --registry srinmantest --image istioapi:v1 --file Dockerfilev1 .
az acr build --registry srinmantest --image istioapi:v2 --file Dockerfilev2 .
az acr build --registry srinmantest --image istioapi:v3 --file Dockerfilev3 .
az acr build --registry srinmantest --image appflaky:v1 --file Dockerfileflaky .
az acr build --registry srinmantest --image echocaller:v1 --file Dockerfileechocaller .
az acr build --registry srinmantest --image clientapp:v1 --file Dockerfileclientapp .
```