import os

if __name__ == "__main__":
    print("🚀 Starting Restaurant Reservation API...")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🌐 Host: 0.0.0.0")
    print(f"🔌 Port: 8000")
    
    from app import app
    app.run(host="0.0.0.0", port=8000, debug=False)
