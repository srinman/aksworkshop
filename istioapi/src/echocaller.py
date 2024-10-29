from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/echo', methods=['GET'])
def echo():
    caller_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    host = request.headers.get('Host')
    accept = request.headers.get('Accept')
    accept_language = request.headers.get('Accept-Language')
    referer = request.headers.get('Referer')
    content_type = request.headers.get('Content-Type')
    content_length = request.headers.get('Content-Length')
    authorization = request.headers.get('Authorization')
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    x_real_ip = request.headers.get('X-Real-IP')

    response = {
        'caller_ip': caller_ip,
        'user_agent': user_agent,
        'host': host,
        'accept': accept,
        'accept_language': accept_language,
        'referer': referer,
        'content_type': content_type,
        'content_length': content_length,
        'authorization': authorization,
        'x_forwarded_for': x_forwarded_for,
        'x_real_ip': x_real_ip
    }

    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)