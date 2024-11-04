from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def hello_world():
    return jsonify({"message": "Hello, World!"})

@app.route("/test")
def test():
    return jsonify({"status": "Server is running!"})
