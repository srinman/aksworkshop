from flask import Flask, jsonify
import random

app = Flask(__name__)

@app.route('/unstable-endpoint')
def unstable_endpoint():
    # Simulate a failure with a 50% chance
    if random.random() < 0.5:
        return jsonify({"message": "Request failed"}), 500
    else:
        return jsonify({"message": "Request succeeded"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)