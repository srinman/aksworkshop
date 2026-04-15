package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"time"

	pb "github.com/srinman/istiogrpc/server/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

type server struct {
	pb.UnimplementedGreeterServer
	podIP    string
	hostname string
}

func (s *server) SayHello(ctx context.Context, req *pb.HelloRequest) (*pb.HelloReply, error) {
	log.Printf("[pod=%s ip=%s] Received SayHello from: %s", s.hostname, s.podIP, req.GetName())
	return &pb.HelloReply{
		Message:   fmt.Sprintf("Hello %s!", req.GetName()),
		ServerIp:  s.podIP,
		Hostname:  s.hostname,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}, nil
}

func main() {
	podIP := os.Getenv("POD_IP")
	hostname, _ := os.Hostname()

	port := "50051"
	if p := os.Getenv("GRPC_PORT"); p != "" {
		port = p
	}

	lis, err := net.Listen("tcp", ":"+port)
	if err != nil {
		log.Fatalf("failed to listen on port %s: %v", port, err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterGreeterServer(grpcServer, &server{
		podIP:    podIP,
		hostname: hostname,
	})
	reflection.Register(grpcServer)

	log.Printf("gRPC server starting on :%s (pod=%s ip=%s)", port, hostname, podIP)
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
