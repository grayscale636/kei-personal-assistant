import asyncio
import signal
import sys
from fastapi import FastAPI
from bot import run_bot
import threading
import uvicorn

app = FastAPI()

@app.get("/")
def status():
    return {"status": "Bot aktif"}

def signal_handler(sig, frame):
    print("Gracefully shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start bot in daemon thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Run FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)