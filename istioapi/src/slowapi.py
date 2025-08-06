from flask import Flask, jsonify, request
import time
import random
import os

app = Flask(__name__)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "slowapi"}), 200

@app.route('/fast')
def fast_endpoint():
    """Fast response - no delay"""
    return jsonify({
        "message": "Fast response", 
        "delay": 0,
        "timestamp": time.time(),
        "service": "slowapi"
    }), 200

@app.route('/slow')
def slow_endpoint():
    """Slow response - 3-8 second delay"""
    delay = random.uniform(3, 8)
    time.sleep(delay)
    return jsonify({
        "message": "Slow response", 
        "delay": f"{delay:.2f}s",
        "timestamp": time.time(),
        "service": "slowapi"
    }), 200

@app.route('/very-slow')
def very_slow_endpoint():
    """Very slow response - 10-15 second delay"""
    delay = random.uniform(10, 15)
    time.sleep(delay)
    return jsonify({
        "message": "Very slow response", 
        "delay": f"{delay:.2f}s",
        "timestamp": time.time(),
        "service": "slowapi"
    }), 200

@app.route('/timeout-test')
def timeout_test():
    """Test different timeout scenarios"""
    scenario = request.args.get('scenario', 'fast')
    
    if scenario == 'fast':
        return fast_endpoint()
    elif scenario == 'slow':
        return slow_endpoint()
    elif scenario == 'very-slow':
        return very_slow_endpoint()
    else:
        return jsonify({"error": "Unknown scenario"}), 400

@app.route('/configurable-delay')
def configurable_delay():
    """Configurable delay endpoint"""
    try:
        delay = float(request.args.get('delay', 0))
        max_delay = float(os.environ.get('MAX_DELAY', 30))
        
        if delay > max_delay:
            delay = max_delay
            
        time.sleep(delay)
        return jsonify({
            "message": f"Response after {delay}s delay",
            "delay": f"{delay:.2f}s",
            "timestamp": time.time(),
            "service": "slowapi"
        }), 200
    except ValueError:
        return jsonify({"error": "Invalid delay parameter"}), 400

@app.route('/')
def root():
    """Root endpoint with service info"""
    return jsonify({
        "service": "slowapi",
        "version": "1.0",
        "endpoints": [
            "/health",
            "/fast",
            "/slow", 
            "/very-slow",
            "/timeout-test?scenario=fast|slow|very-slow",
            "/configurable-delay?delay=<seconds>"
        ],
        "timestamp": time.time()
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
