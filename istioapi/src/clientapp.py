import os
import requests
import time
import sys
from datetime import datetime

def call_unstable_endpoint(endpoint):
    try:
        response = requests.get(endpoint)
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.exceptions.RequestException:
        return False

if __name__ == "__main__":
    endpoint = os.getenv('ENDPOINT_URL', 'http://appflaky.retryns.svc.cluster.local/unstable-endpoint')
    
    while True:
        success_count = 0
        failure_count = 0

        start_time = datetime.now()
        print(f"Test starts at {start_time}")
        sys.stdout.flush()

        for _ in range(100):
            if call_unstable_endpoint(endpoint):
                success_count += 1
            else:
                failure_count += 1

        end_time = datetime.now()
        print(f"Test ends at {end_time}")
        sys.stdout.flush()
        
        total_requests = success_count + failure_count
        success_rate = (success_count / total_requests) * 100
        failure_rate = (failure_count / total_requests) * 100
        
        print(f"Success Rate: {success_rate:.2f}% ({success_count}/{total_requests}), Failure Rate: {failure_rate:.2f}% ({failure_count}/{total_requests})")
        sys.stdout.flush()
        
        time.sleep(10)