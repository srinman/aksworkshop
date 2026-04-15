# ---- Build stage ----
FROM golang:1.22-alpine AS builder

# Install protoc and protobuf libraries
RUN apk add --no-cache protobuf protobuf-dev

# Install protoc Go plugins
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.33.0 && \
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3.0

WORKDIR /app

# Copy all source
COPY . .

# Generate protobuf / gRPC code
RUN protoc \
    --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    pb/greeting.proto

# Generate go.sum and download all dependencies
RUN go mod tidy && go mod download

# Build binary
RUN CGO_ENABLED=0 GOOS=linux go build -o grpc-server .

# ---- Final stage ----
FROM alpine:3.19
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=builder /app/grpc-server .
EXPOSE 50051
CMD ["./grpc-server"]
