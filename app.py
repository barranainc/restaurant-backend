from flask import Flask, jsonify
import datetime

app = Flask(__name__)

@app.route("/")
def root():
    return jsonify({
        "message": "Restaurant Reservation API is running",
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route("/ping")
def ping():
    return jsonify({"pong": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
