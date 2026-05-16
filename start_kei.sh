#!/bin/bash
# Startup script untuk bot @Kei dengan migrasi Langchain + DeepSeek

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Check if bot is already running
if [ -f kei.pid ] && kill -0 $(cat kei.pid) 2>/dev/null; then
    echo "❌ Bot @Kei is already running with PID: $(cat kei.pid)"
    exit 1
fi

# Start the bot
echo "🚀 Starting bot @Kei with Langchain + DeepSeek migration..."
nohup python bot.py > kei.log 2>&1 &
PID=$!

# Save PID
echo $PID > kei.pid

# Wait a bit and check if it's running
sleep 3
if kill -0 $PID 2>/dev/null; then
    echo "✅ Bot @Kei started successfully with PID: $PID"
    echo "📝 Logs: kei.log"
    echo "🛑 To stop: kill $PID"
    
    # Show recent logs
    echo -e "\n=== Recent Logs ==="
    tail -10 kei.log 2>/dev/null || echo "No logs yet..."
else
    echo "❌ Bot failed to start. Check kei.log for errors."
    tail -20 kei.log 2>/dev/null
    exit 1
fi