#!/usr/bin/env python3
"""
Istio Resiliency Test Script

This script tests the resiliency features of Istio by making HTTP requests
to services and measuring success rates, response times, and failure patterns.

Usage:
    python3 resiliencytest.py [--endpoint URL] [--requests COUNT] [--timeout SECONDS]

Requirements:
    - requests library: pip3 install requests
"""

import requests
import time
import json
import sys
import argparse
import os
from collections import defaultdict
from datetime import datetime

class ResiliencyTester:
    def __init__(self, endpoint_url, timeout=10):
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        self.results = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'timeouts': 0,
            'response_times': [],
            'status_codes': defaultdict(int),
            'errors': []
        }
    
    def make_request(self):
        """Make a single HTTP request and record the result"""
        start_time = time.time()
        try:
            response = requests.get(
                self.endpoint_url, 
                timeout=self.timeout,
                headers={'User-Agent': 'Istio-Resiliency-Tester/1.0'}
            )
            end_time = time.time()
            response_time = end_time - start_time
            
            self.results['total_requests'] += 1
            self.results['response_times'].append(response_time)
            self.results['status_codes'][response.status_code] += 1
            
            if response.status_code == 200:
                self.results['successful_requests'] += 1
                return True, response_time, response.status_code, None
            else:
                self.results['failed_requests'] += 1
                return False, response_time, response.status_code, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            end_time = time.time()
            response_time = end_time - start_time
            self.results['total_requests'] += 1
            self.results['failed_requests'] += 1
            self.results['timeouts'] += 1
            self.results['response_times'].append(response_time)
            error_msg = "Request timeout"
            self.results['errors'].append(error_msg)
            return False, response_time, 0, error_msg
            
        except requests.exceptions.RequestException as e:
            end_time = time.time()
            response_time = end_time - start_time
            self.results['total_requests'] += 1
            self.results['failed_requests'] += 1
            self.results['response_times'].append(response_time)
            error_msg = str(e)
            self.results['errors'].append(error_msg)
            return False, response_time, 0, error_msg
    
    def run_test(self, num_requests=100, delay_between_requests=0.1):
        """Run the resiliency test"""
        print(f"🚀 Starting resiliency test against: {self.endpoint_url}")
        print(f"📊 Making {num_requests} requests with {delay_between_requests}s delay between requests")
        print(f"⏱️  Timeout set to {self.timeout}s")
        print("-" * 80)
        
        start_test_time = time.time()
        
        for i in range(num_requests):
            success, response_time, status_code, error = self.make_request()
            
            # Print progress every 10 requests
            if (i + 1) % 10 == 0:
                success_rate = (self.results['successful_requests'] / (i + 1)) * 100
                avg_response_time = sum(self.results['response_times']) / len(self.results['response_times'])
                print(f"Progress: {i+1:3d}/{num_requests} | "
                      f"Success Rate: {success_rate:5.1f}% | "
                      f"Avg Response Time: {avg_response_time:6.3f}s")
            
            # Add delay between requests to avoid overwhelming the service
            if delay_between_requests > 0:
                time.sleep(delay_between_requests)
        
        end_test_time = time.time()
        test_duration = end_test_time - start_test_time
        
        self.print_summary(test_duration)
        return self.results
    
    def print_summary(self, test_duration):
        """Print test summary and statistics"""
        print("\n" + "=" * 80)
        print("📈 RESILIENCY TEST RESULTS")
        print("=" * 80)
        
        # Basic statistics
        total = self.results['total_requests']
        success_rate = (self.results['successful_requests'] / total) * 100 if total > 0 else 0
        failure_rate = (self.results['failed_requests'] / total) * 100 if total > 0 else 0
        timeout_rate = (self.results['timeouts'] / total) * 100 if total > 0 else 0
        
        print(f"🎯 Test Configuration:")
        print(f"   • Endpoint: {self.endpoint_url}")
        print(f"   • Total Requests: {total}")
        print(f"   • Test Duration: {test_duration:.2f}s")
        print(f"   • Requests/Second: {total/test_duration:.2f}")
        
        print(f"\n📊 Success/Failure Statistics:")
        print(f"   • Successful Requests: {self.results['successful_requests']:4d} ({success_rate:5.1f}%)")
        print(f"   • Failed Requests:     {self.results['failed_requests']:4d} ({failure_rate:5.1f}%)")
        print(f"   • Timeout Requests:    {self.results['timeouts']:4d} ({timeout_rate:5.1f}%)")
        
        # Response time statistics
        if self.results['response_times']:
            response_times = self.results['response_times']
            avg_time = sum(response_times) / len(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            
            # Calculate percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.5)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            
            print(f"\n⏱️  Response Time Statistics:")
            print(f"   • Average:  {avg_time:.3f}s")
            print(f"   • Minimum:  {min_time:.3f}s")
            print(f"   • Maximum:  {max_time:.3f}s")
            print(f"   • 50th percentile (P50): {p50:.3f}s")
            print(f"   • 95th percentile (P95): {p95:.3f}s")
            print(f"   • 99th percentile (P99): {p99:.3f}s")
        
        # HTTP status codes
        if self.results['status_codes']:
            print(f"\n🔢 HTTP Status Code Distribution:")
            for status_code, count in sorted(self.results['status_codes'].items()):
                percentage = (count / total) * 100
                status_name = {
                    200: "OK",
                    500: "Internal Server Error", 
                    503: "Service Unavailable",
                    504: "Gateway Timeout"
                }.get(status_code, "Unknown")
                print(f"   • {status_code} ({status_name}): {count:4d} ({percentage:5.1f}%)")
        
        # Error summary
        if self.results['errors']:
            error_counts = defaultdict(int)
            for error in self.results['errors']:
                error_counts[error] += 1
            
            print(f"\n❌ Error Summary:")
            for error, count in error_counts.items():
                percentage = (count / total) * 100
                print(f"   • {error}: {count} ({percentage:.1f}%)")
        
        # Resiliency insights
        print(f"\n🔍 Resiliency Insights:")
        if success_rate > 95:
            print("   ✅ Excellent resiliency - very high success rate")
        elif success_rate > 80:
            print("   ⚠️  Good resiliency - some failures observed")
        else:
            print("   ❌ Poor resiliency - high failure rate detected")
        
        if timeout_rate > 10:
            print("   ⏰ High timeout rate - consider increasing timeout or checking service performance")
        
        if self.results['response_times']:
            avg_time = sum(self.results['response_times']) / len(self.results['response_times'])
            if avg_time > 5.0:
                print("   🐌 High average response time - service may be overloaded")
        
        print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description='Test Istio resiliency features')
    parser.add_argument('--endpoint', '-e', 
                       default=os.environ.get('ENDPOINT_URL', 'http://localhost:5000/unstable-endpoint'),
                       help='Endpoint URL to test (default: ENDPOINT_URL env var or localhost)')
    parser.add_argument('--requests', '-r', type=int, default=100,
                       help='Number of requests to make (default: 100)')
    parser.add_argument('--timeout', '-t', type=float, default=10.0,
                       help='Request timeout in seconds (default: 10.0)')
    parser.add_argument('--delay', '-d', type=float, default=0.1,
                       help='Delay between requests in seconds (default: 0.1)')
    parser.add_argument('--output', '-o', 
                       help='Output results to JSON file')
    
    args = parser.parse_args()
    
    # Validate endpoint URL
    if not args.endpoint:
        print("❌ Error: No endpoint URL provided. Set ENDPOINT_URL environment variable or use --endpoint flag.")
        sys.exit(1)
    
    if not args.endpoint.startswith(('http://', 'https://')):
        print("❌ Error: Endpoint URL must start with http:// or https://")
        sys.exit(1)
    
    try:
        # Create tester and run test
        tester = ResiliencyTester(args.endpoint, args.timeout)
        results = tester.run_test(args.requests, args.delay)
        
        # Save results to file if requested
        if args.output:
            results['test_config'] = {
                'endpoint': args.endpoint,
                'requests': args.requests,
                'timeout': args.timeout,
                'delay': args.delay,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n💾 Results saved to: {args.output}")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running test: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()