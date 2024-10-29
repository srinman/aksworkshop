import os
from flask import Flask, jsonify

app = Flask(__name__)

books = [
    {"id": 1, "title": "Book One", "author": "Author A"},
    {"id": 2, "title": "Book Two", "author": "Author B"},
    {"id": 3, "title": "Book Three", "author": "Author C"}
]

authors = [
    {"id": 1, "name": "Author A"},
    {"id": 2, "name": "Author B"},
    {"id": 3, "name": "Author C"}
]

@app.route('/', methods=['GET'])
def get_default():
    return jsonify("Supported endpoints: /books and /authors")

@app.route('/books', methods=['GET'])
def get_books():
    return jsonify(books)

@app.route('/authors', methods=['GET'])
def get_authors():
    author_names = [author["name"] + " v1" for author in authors]
    return jsonify(author_names)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)