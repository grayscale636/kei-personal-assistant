# Discord Bot with AI Integration & Persistent Memory

An advanced Discord bot that integrates Dify's AI with a persistent memory system and comprehensive search features.

## 🚀 Features

### Core Features
- **AI Integration**: Uses the Dify AI API with streaming responses
- **Persistent Memory**: SQLite database to store all conversations
- **Context Management**: Bot remembers conversation history and can refer to previous messages
- **Search System**: Local search per channel and global cross-channel search
- **Command System**: Prefix `!kei` to avoid conflicts with other bots

### Available Commands
```
!kei help - Show all available commands
!kei chat <message> - Chat with AI (or mention the bot directly)
!kei search <word> - Search the current channel
!kei gsearch <word> - Search all channels (global)
!kei stats - Channel statistics and database
!kei reset - Reset conversations in this channel (soft reset)
!kei purge - Delete ALL data in this channel (hard reset)
```

## 📦 Installation

### Requirements
- Python 3.11+
- Docker & Docker Compose
- Discord Bot Tokens
- Dify AI API Access

### Setup

1. **Clone repository**
```bash
git clone <repository-url>
cd bot_dc
```

2. **Environment Configuration**
Create `.env` file:
```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_WEBHOOK_URL=your_webhook_url (optional)
DIFY_API_URL=http://your-dify-server:port/v1/chat-messages
DIFY_API_KEY=your_dify_api_key
```

3. **Discord Bot Setup**
- Create a bot in [Discord Developer Portal](https://discord.com/developers/applications)
- Enable **Message Content Intent**, **Server Members Intent**, **Presence Intent**
- Invite bot to server with permissions: 
- Send Messages 
- Read Message History 
- Use Slash Commands 
- Embed Links

4. **Deploy with Docker**
```bash
docker-compose build
docker-compose up -d
```

## 🏗️ Architecture

```
├── bot.py # Main Discord bot logic
├── dify_client.py # AI API client
├── memory_db.py # Database operations
├── main.py # Application entry point
├── requirements.txt # Python dependencies
├── docker-compose.yml # Docker configuration
└── data/ # SQLite database storage (persistent volume)
```

## 💾 Database Schema

```sql
CREATE TABLE conversations ( 
id INTEGER PRIMARY KEY AUTOINCREMENT, 
guild_id TEXT NOT NULL, 
channel_id TEXT NOT NULL, 
user_id TEXT NOT NULL, 
conversation_id TEXT, 
message TEXT NOT NULL, 
response TEXT NOT NULL, 
timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

## 📱 Usage Examples

### Basic Chat
```
@BotName hello, how are you?
# or
!kei chat hello, how are you?
```

### Search Messages
```
!kei search docker # Search for "docker" in this channel
!kei gsearch error # Search for "error" in all channels
```

### Memory Management
```
!kei stats # View statistics
!kei reset # Reset conversation (soft)
!kei purge # Clear all channel data (hard)
```

## 🔧 Configuration

### Docker Environment
- **Port**: 8000 (internal FastAPI), 8002 (host mapping)
- **Volume**: `./data:/app/data` for persistent storage
- **Network**: Bridge network for communication between containers

### Memory System
- **Local Search**: `!kei search` - search within the current channel
- **Global Search**: `!kei gsearch` - search across all channels
- **Auto-cleanup**: The system automatically manages the database Size
- Indexing: Indexed database for optimal performance

## 🎨 Features Detail

### AI Context Management
The bot uses a combination of:
1. Recent Messages: The last 10 messages from the channel
2. Memory Database: Conversation history from the database
3. Dify Conversation: AI conversation state management

### Search System
- Keyword Search: Search by keyword
- Channel Grouping: Global search results grouped per channel
- Smart Truncation: Auto-truncate for Discord message limits
- Color Coding: Blue embed for global, green for local

### Error Handling
- Timeout Management: 30-second timeout for confirmation
- Graceful Degradation: The bot continues running even if there is a database error
- Retry Logic: Auto-retry for API calls
- Detailed Logging: Comprehensive error tracking

## 📊 Version History

### V2.2 (Current)
- ✅ Global search with `!kei gsearch`
- ✅ Enhanced search UI with color coding
- ✅ Channel detection for smart search routing
- ✅ Better result grouping and display

### V2.1
- ✅ Command prefix migration to `!kei`
- ✅ Backward compatibility support
- ✅ Enhanced help system
- ✅ Legacy command warnings

### V2.0
- ✅ Persistent SQLite memory
- ✅ Search functionality
- ✅ Database statistics
- ✅ Soft vs hard reset system

### V1.0
- ✅ Basic Discord bot
- ✅ Dify AI integration
- ✅ Streaming responses
- ✅ Docker deployment

## 🛠️ Development

###Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run bots locally
python main.py
```

### Database Management
```python
# Access database directly
import sqlite3
conn = sqlite3.connect('data/bot_memory.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM conversations LIMIT 5")
```

### Adding New Commands
1. Edit `bot.py`
2. Add a command handler with `@bot.command(name="commandname")`
3. Update help text
4. Test and deploy

## 🔒 Security

- **Environment Variables**: Sensitive data in `.env`
- **Docker Isolation**: Bot runs in containers
- **Input Validation**: All user input is validated
- **Rate Limiting**: Discord natural rate limiting

## 📈 Monitoring

### Health Check
Bot expose health endpoint at `http://localhost:8002/health`

### Logs
```bash
# View container logs
docker-compose logs -f

# Database statistics
!kei stats # in Discord
```

### Performance
- SQLite with indexing for optimal performance
- Async operations for non-blocking I/O
- Memory efficient with cleanup routines

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Test changes thoroughly
4. Submit pull requests

## 📄 License

[Add your license here]

## 🆘 Troubleshooting

### Bot Not Responding
1. Check Discord permissions (Message Content Intent)
2. Verify `.env` configuration
3. Check container status: `docker-compose ps`

### Database Issues
1. Check volume mapping: `./data:/app/data`
2. Verify SQLite file permissions
3. Try database reset: `!kei purge` (DANGER: deletes all data)

### API Errors
1. Verify Dify API URL and key
2. Check network connectivity
3. Monitor API rate limits

---

**Made with ❤️ for the awesome Discord community!**