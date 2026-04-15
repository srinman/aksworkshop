package main

import (
	"context"
	"log"
	"os"
	"time"

	pb "github.com/srinman/istiogrpc/client/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

func main() {
	serverAddr := os.Getenv("SERVER_ADDR")
	if serverAddr == "" {
		serverAddr = "grpc-server:50051"
	}

	// NOTE: intentionally NOT using dns:/// scheme or round_robin policy.
	// This mirrors how many real-world gRPC clients are written and reproduces
	// the stale-IP failure when the upstream headless-service pods are bounced.
	// The single Dial() resolves DNS once; with Istio the sidecar can end up
	// holding a dead connection to the original pod IP.
	log.Printf("Dialing %s (passthrough resolver, no explicit LB policy)", serverAddr)

	conn, err := grpc.Dial(
		serverAddr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.Fatalf("failed to connect to %s: %v", serverAddr, err)
	}
	defer conn.Close()

	client := pb.NewGreeterClient(conn)

	var callCount, failCount int64
	for {
		callCount++
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		resp, err := client.SayHello(ctx, &pb.HelloRequest{Name: "grpc-client"})
		cancel()

		if err != nil {
			failCount++
			log.Printf("[#%d] ERROR (failures=%d/%d): %v", callCount, failCount, callCount, err)
		} else {
			log.Printf("[#%d] OK  server_ip=%-15s hostname=%s ts=%s",
				callCount, resp.GetServerIp(), resp.GetHostname(), resp.GetTimestamp())
		}

		time.Sleep(1 * time.Second)
	}
}
