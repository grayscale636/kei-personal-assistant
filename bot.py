import discord
import os
import asyncio
from datetime import datetime, timedelta
from langchain_client import ask_langchain, analyze_image_url
from dotenv import load_dotenv
from memory_db import BotMemoryDB, VALID_PREFS, NICKNAME_MAX_LEN

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

print(f"🚀 Starting bot @Kei...")
print(f"✅ TOKEN loaded: {TOKEN is not None}")
print(f"✅ DEEPSEEK_API_KEY loaded: {os.getenv('DEEPSEEK_API_KEY') is not None}")
print(f"✅ Langchain migration: COMPLETE")

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)

# Dictionary untuk menyimpan conversation_id per channel
channel_conversations = {}
# Dictionary untuk menyimpan context cache per channel
channel_context_cache = {}
CONTEXT_CACHE_DURATION = 300  # 5 menit

# Initialize memory system
memory_db = BotMemoryDB()

async def get_channel_context(channel, limit=10):
    """Ambil konteks dari pesan-pesan sebelumnya di channel"""
    channel_id = channel.id
    current_time = datetime.now()
    
    # Cek apakah ada cache yang masih valid
    if channel_id in channel_context_cache:
        cache_entry = channel_context_cache[channel_id]
        if current_time - cache_entry['timestamp'] < timedelta(seconds=CONTEXT_CACHE_DURATION):
            print(f"[DEBUG] Using cached context for channel {channel_id}")
            return cache_entry['context']
    
    print(f"[DEBUG] Fetching fresh context for channel {channel_id}")
    context_messages = []
    
    try:
        # Ambil pesan-pesan terakhir (kecuali bot's own messages)
        async for message in channel.history(limit=limit):
            if message.author != bot.user and not message.content.startswith('!'):
                # Format: "Username (timestamp): message"
                timestamp = message.created_at.strftime("%H:%M")
                context_messages.append(f"{message.author.display_name} ({timestamp}): {message.content}")
        
        # Reverse agar urutan chronological
        context_messages.reverse()
        context_text = "\n".join(context_messages)
        
        # Cache the result
        channel_context_cache[channel_id] = {
            'context': context_text,
            'timestamp': current_time
        }
        
        return context_text
        
    except Exception as e:
        print(f"[ERROR] Failed to get channel context: {e}")
        return ""

async def send_long_message(channel, text, max_length=2000):
    """Send long message by splitting into chunks"""
    if len(text) <= max_length:
        await channel.send(text)
        return
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for paragraph in paragraphs:
        # If single paragraph is too long, split by sentences
        if len(paragraph) > max_length:
            sentences = paragraph.split('. ')
            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 2 > max_length:
                    if current_chunk:
                        await channel.send(current_chunk.strip())
                        current_chunk = sentence + '. '
                    else:
                        # Single sentence too long, force split
                        while len(sentence) > max_length:
                            await channel.send(sentence[:max_length])
                            sentence = sentence[max_length:]
                        current_chunk = sentence + '. '
                else:
                    current_chunk += sentence + '. '
        else:
            # Normal paragraph
            if len(current_chunk) + len(paragraph) + 2 > max_length:
                if current_chunk:
                    await channel.send(current_chunk.strip())
                current_chunk = paragraph + '\n\n'
            else:
                current_chunk += paragraph + '\n\n'
    
    # Send remaining chunk
    if current_chunk.strip():
        await channel.send(current_chunk.strip())

@bot.event
async def on_ready():
    print(f"[✓] Bot aktif sebagai {bot.user}")
    print(f"[✓] Context management enabled")
    await memory_db.init_db()
    print(f"[✓] Memory database initialized")
    print(f"[✓] Bot siap dengan fitur V2.2:")
    print("    - Konteks percakapan per channel")
    print("    - History pesan sebagai konteks")
    print("    - Cache konteks (5 menit)")
    print("    - Persistent conversation memory")
    print("    - Local search (!kei search) per channel")
    print("    - Global search (!kei gsearch) across all channels")
    print("    - Channel statistics & database overview")
    print("    - Command prefix: !kei untuk menghindari konflik")
    print("    - Soft reset (!kei reset) vs Hard reset (!kei purge)")
    print("    - Mention @Kei atau !kei ask untuk bertanya")

@bot.event
async def on_message(message):
    # Hindari balas diri sendiri
    if message.author == bot.user:
        return

    channel_id = message.channel.id
    
    # Deteksi jika pesan mention bot
    if bot.user in message.mentions:
        query = message.content.replace(f"<@{bot.user.id}>", "").strip()

        # Image-attachment flow: if any image attached, route to vision model
        image_url = next(
            (a.url for a in message.attachments
             if a.content_type and a.content_type.startswith('image/')),
            None,
        )
        if image_url:
            await message.channel.typing()
            prompt = query or "Tolong jelaskan dan analisis gambar ini secara singkat."
            response_text = await analyze_image_url(image_url, prompt)
            await send_long_message(message.channel, response_text)
            try:
                await memory_db.save_conversation(
                    message.channel.id, message.author.id,
                    message.author.display_name,
                    f"[image] {query}".strip(), response_text, None,
                )
            except Exception as e:
                print(f"[WARN] Failed to save image convo: {e}")
            return

        if not query:
            await message.channel.send("Iya kak? Mention doang nih? 😄")
            return

        await message.channel.typing()
        
        # Get conversation ID for this channel
        conversation_id = channel_conversations.get(str(message.channel.id))
        
        # Get enhanced context from memory database
        past_conversations = await memory_db.load_conversation_history(
            message.channel.id, days=7, limit=5
        )
        
        # Format past conversations sebagai context
        memory_context = ""
        if past_conversations:
            memory_context = "Percakapan sebelumnya di channel ini:\n"
            for conv in past_conversations[-3:]:  # Last 3 conversations
                timestamp = conv['timestamp'][:16] if conv['timestamp'] else ""
                memory_context += f"[{timestamp}] {conv['username']}: {conv['message'][:100]}{'...' if len(conv['message']) > 100 else ''}\n"
                memory_context += f"Bot: {conv['response'][:100]}{'...' if len(conv['response']) > 100 else ''}\n\n"
        
        # Ambil konteks channel (recent messages)
        channel_context = await get_channel_context(message.channel)
        
        # Gabung semua context
        full_context = ""
        if memory_context:
            full_context += memory_context
        if channel_context:
            full_context += f"Pesan terbaru:\n{channel_context}\n\n"
        
        # Send to AI dengan enhanced context
        if full_context:
            enhanced_query = f"Konteks:\n{full_context}Pertanyaan: {query}"
        else:
            enhanced_query = query
            
        print(f"[DEBUG] Enhanced query length: {len(enhanced_query)}")
        print(f"[DEBUG] Memory context: {len(memory_context)} chars")
        print(f"[DEBUG] Channel context: {len(channel_context)} chars")

        # Fetch user preferences (falls back to defaults if unset)
        user_prefs = await memory_db.get_user_preferences(message.author.id)

        # Get AI response
        response_text, new_conversation_id = await ask_langchain(
            enhanced_query, str(message.author.id), conversation_id, prefs=user_prefs
        )

        # Update conversation ID jika baru
        if new_conversation_id:
            channel_conversations[str(message.channel.id)] = new_conversation_id
            print(f"[DEBUG] Updated conversation_id for channel {message.channel.id}: {new_conversation_id}")
        
        # Save to memory database
        try:
            await memory_db.save_conversation(
                message.channel.id,
                message.author.id,
                message.author.display_name,
                query,
                response_text,
                new_conversation_id or conversation_id
            )
            print(f"[✓] Conversation saved to memory database")
        except Exception as e:
            print(f"[WARN] Failed to save conversation to memory: {e}")
        
        await send_long_message(message.channel, response_text)

    # Masih bisa handle !ask juga
    elif message.content.startswith("!kei ask "):
        query = message.content[9:]  # Remove "!kei ask "
        await message.channel.typing()
        
        # Get conversation ID for this channel
        conversation_id = channel_conversations.get(str(message.channel.id))
        
        # Get enhanced context from memory database
        past_conversations = await memory_db.load_conversation_history(
            message.channel.id, days=7, limit=5
        )
        
        # Format past conversations sebagai context
        memory_context = ""
        if past_conversations:
            memory_context = "Percakapan sebelumnya di channel ini:\n"
            for conv in past_conversations[-3:]:  # Last 3 conversations
                timestamp = conv['timestamp'][:16] if conv['timestamp'] else ""
                memory_context += f"[{timestamp}] {conv['username']}: {conv['message'][:100]}{'...' if len(conv['message']) > 100 else ''}\n"
                memory_context += f"Bot: {conv['response'][:100]}{'...' if len(conv['response']) > 100 else ''}\n\n"
        
        # Ambil konteks channel untuk !ask juga
        channel_context = await get_channel_context(message.channel)
        
        # Gabung semua context
        full_context = ""
        if memory_context:
            full_context += memory_context
        if channel_context:
            full_context += f"Pesan terbaru:\n{channel_context}\n\n"
        
        if full_context:
            enhanced_query = f"Konteks:\n{full_context}Pertanyaan: {query}"
        else:
            enhanced_query = query

        user_prefs = await memory_db.get_user_preferences(message.author.id)

        response_text, new_conversation_id = await ask_langchain(
            enhanced_query, str(message.author.id), conversation_id, prefs=user_prefs
        )

        if new_conversation_id:
            channel_conversations[str(message.channel.id)] = new_conversation_id
        
        # Save to memory database
        try:
            await memory_db.save_conversation(
                message.channel.id,
                message.author.id,
                message.author.display_name,
                query,
                response_text,
                new_conversation_id or conversation_id
            )
        except Exception as e:
            print(f"[WARN] Failed to save conversation to memory: {e}")
            
        await send_long_message(message.channel, response_text)
    
    # Soft reset - Reset conversation only (preserves database)
    elif message.content.lower() in ["!kei reset", "!kei clear", "!kei new"]:
        channel_id = message.channel.id
        if str(channel_id) in channel_conversations:
            del channel_conversations[str(channel_id)]
        
        # Clear context cache
        if channel_id in channel_context_cache:
            del channel_context_cache[channel_id]
        
        await message.channel.send("🔄 **Conversation reset!** Dify conversation cleared, but memory database preserved.\nUse `!kei purge` to delete all stored conversations.")
    
    # Hard reset - Delete ALL channel data from database
    elif message.content.startswith('!kei purge'):
        try:
            # Confirm with user
            confirm_msg = await message.channel.send(
                "⚠️ **WARNING**: This will permanently delete ALL stored conversations for this channel!\n"
                "React with ✅ to confirm or ❌ to cancel. (30 seconds timeout)"
            )
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")
            
            def check(reaction, user):
                return (user == message.author and 
                       str(reaction.emoji) in ["✅", "❌"] and 
                       reaction.message.id == confirm_msg.id)
            
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Delete from database
                deleted_count = await memory_db.purge_channel_data(message.channel.id)
                
                # Clear conversation and cache
                if str(message.channel.id) in channel_conversations:
                    del channel_conversations[str(message.channel.id)]
                if message.channel.id in channel_context_cache:
                    del channel_context_cache[message.channel.id]
                
                await message.channel.send(f"💥 **Channel purged!** {deleted_count} conversations deleted from database.")
            else:
                await message.channel.send("❌ Purge cancelled.")
                
        except asyncio.TimeoutError:
            await message.channel.send("⏰ Purge confirmation timed out. Operation cancelled.")
        except Exception as e:
            print(f"[ERROR] Purge failed: {e}")
            await message.channel.send("❌ Error during purge operation.")
    
    # Search command (per channel)
    elif message.content.startswith('!kei search'):
        try:
            keyword = message.content[12:].strip()  # Remove "!kei search "
            if not keyword:
                await message.channel.send("❌ Usage: `!kei search <keyword>` (search this channel)")
                return
            
            results = await memory_db.search_conversations(keyword, message.channel.id, days=30, limit=5)
            
            if not results:
                await message.channel.send(f"🔍 No results found in this channel for: `{keyword}`")
                return
            
            embed = discord.Embed(title=f"🔍 Channel Search: '{keyword}'", color=0x00ff00)
            
            for i, result in enumerate(results[:3], 1):
                channel_id, username, msg, response, timestamp = result
                timestamp_str = timestamp[:16] if timestamp else "Unknown"
                
                field_value = f"**{username}:** {msg[:100]}{'...' if len(msg) > 100 else ''}\n"
                field_value += f"**Bot:** {response[:100]}{'...' if len(response) > 100 else ''}"
                
                embed.add_field(
                    name=f"#{i} - {timestamp_str}",
                    value=field_value,
                    inline=False
                )
            
            embed.set_footer(text=f"Found {len(results)} results in this channel")
            await message.channel.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] Search command failed: {e}")
            await message.channel.send("❌ Error during search")
    
    # Global search command (across all channels)
    elif message.content.startswith('!kei gsearch'):
        try:
            keyword = message.content[13:].strip()  # Remove "!kei gsearch "
            if not keyword:
                await message.channel.send("❌ Usage: `!kei gsearch <keyword>` (search all channels)")
                return
            
            # Search without channel_id = search all channels
            results = await memory_db.search_conversations(keyword, channel_id=None, days=30, limit=10)
            
            if not results:
                await message.channel.send(f"🌐 No global results found for: `{keyword}`")
                return
            
            embed = discord.Embed(title=f"🌐 Global Search: '{keyword}'", color=0x0099ff)
            
            # Group results by channel
            channels_found = {}
            for result in results[:8]:  # Limit to 8 results for display
                channel_id, username, msg, response, timestamp = result
                
                # Try to get actual channel name, fallback to ID
                try:
                    channel_obj = bot.get_channel(int(channel_id))
                    channel_name = channel_obj.name if channel_obj else f"Channel-{channel_id[-4:]}"
                except:
                    channel_name = f"Channel-{channel_id[-4:]}"
                
                if channel_name not in channels_found:
                    channels_found[channel_name] = []
                
                channels_found[channel_name].append({
                    'username': username,
                    'message': msg[:80] + '...' if len(msg) > 80 else msg,
                    'response': response[:80] + '...' if len(response) > 80 else response,
                    'timestamp': timestamp[:16] if timestamp else "Unknown"
                })
            
            # Add fields for each channel
            for channel, convos in list(channels_found.items())[:4]:  # Max 4 channels
                field_value = ""
                for convo in convos[:2]:  # Max 2 conversations per channel
                    field_value += f"**{convo['username']}** ({convo['timestamp']}):\n"
                    field_value += f"Q: {convo['message']}\n"
                    field_value += f"A: {convo['response']}\n\n"
                
                embed.add_field(
                    name=f"📍 #{channel}",
                    value=field_value[:1024] if field_value else "No details",  # Discord limit
                    inline=False
                )
            
            embed.set_footer(text=f"Found {len(results)} results across {len(channels_found)} channels")
            await message.channel.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] Global search failed: {e}")
            await message.channel.send("❌ Error during global search")
    
    # Stats command
    elif message.content.startswith('!kei stats'):
        try:
            stats = await memory_db.get_channel_stats(message.channel.id, days=30)
            
            embed = discord.Embed(title="📊 Channel Statistics (30 days)", color=0x00ff00)
            embed.add_field(name="Total Conversations", value=stats['total_conversations'], inline=True)
            embed.add_field(name="Unique Users", value=stats['unique_users'], inline=True)
            embed.add_field(name="First Message", value=stats['first_message'][:16] if stats['first_message'] else "N/A", inline=True)
            embed.add_field(name="Last Message", value=stats['last_message'][:16] if stats['last_message'] else "N/A", inline=True)
            
            await message.channel.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] Stats command failed: {e}")
            await message.channel.send("❌ Error getting statistics")
    
    # Database info command
    elif message.content.startswith('!kei dbinfo'):
        try:
            db_info = await memory_db.get_database_info()
            
            embed = discord.Embed(title="🗄️ Database Information", color=0x00ff00)
            embed.add_field(name="Total Conversations", value=db_info['total_conversations'], inline=True)
            embed.add_field(name="Total Channels", value=db_info['total_channels'], inline=True)
            embed.add_field(name="Total Users", value=db_info['total_users'], inline=True)
            embed.add_field(name="Oldest Message", value=db_info['oldest_message'][:16] if db_info['oldest_message'] else "N/A", inline=True)
            embed.add_field(name="Newest Message", value=db_info['newest_message'][:16] if db_info['newest_message'] else "N/A", inline=True)
            
            await message.channel.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] Database info failed: {e}")
            await message.channel.send("❌ Error getting database information")
    
    # Per-user preferences (lang, tone, nickname, length, emoji)
    elif message.content.startswith('!kei prefs'):
        args = message.content[len('!kei prefs'):].strip()

        # List current prefs
        if not args:
            prefs = await memory_db.get_user_preferences(message.author.id)
            embed = discord.Embed(
                title=f"⚙️ Preferences — {message.author.display_name}",
                color=0x00ff00,
            )
            embed.add_field(name="Language", value=f"`{prefs['lang']}`", inline=True)
            embed.add_field(name="Tone", value=f"`{prefs['tone']}`", inline=True)
            embed.add_field(name="Length", value=f"`{prefs['response_length']}`", inline=True)
            embed.add_field(name="Emoji", value=f"`{prefs['emoji_level']}`", inline=True)
            nick = prefs.get('nickname') or "(default — Discord name)"
            embed.add_field(name="Nickname", value=f"`{nick}`", inline=True)
            embed.set_footer(text="Set: !kei prefs <key>=<value>  •  Reset: !kei prefs reset")
            await message.channel.send(embed=embed)
            return

        # Reset to defaults
        if args.lower() == 'reset':
            await memory_db.reset_user_preferences(message.author.id)
            await message.channel.send("🔄 Preferences reset to defaults.")
            return

        # Parse k=v pairs (space-separated)
        updates = {}
        errors = []
        for pair in args.split():
            if '=' not in pair:
                errors.append(f"Format salah: `{pair}` (harus `key=value`)")
                continue
            key, value = pair.split('=', 1)
            key = key.lower().strip()
            value = value.strip()

            if key == 'nickname':
                if len(value) > NICKNAME_MAX_LEN:
                    errors.append(f"`nickname` max {NICKNAME_MAX_LEN} char")
                else:
                    updates['nickname'] = value or None
            elif key in VALID_PREFS:
                value_lower = value.lower()
                if value_lower not in VALID_PREFS[key]:
                    valid = '`, `'.join(VALID_PREFS[key])
                    errors.append(f"`{key}={value}` invalid. Valid: `{valid}`")
                else:
                    updates[key] = value_lower
            else:
                all_keys = list(VALID_PREFS.keys()) + ['nickname']
                keys_str = '`, `'.join(all_keys)
                errors.append(f"Key `{key}` gak dikenal. Valid keys: `{keys_str}`")

        if errors:
            await message.channel.send("❌ " + "\n❌ ".join(errors))
            return

        if not updates:
            await message.channel.send("❌ Gak ada yang di-update. Usage: `!kei prefs <key>=<value>`")
            return

        await memory_db.set_user_preferences(message.author.id, **updates)
        applied = ', '.join(f"`{k}={v}`" for k, v in updates.items())
        await message.channel.send(f"✅ Preferences updated: {applied}")

    # Personal stats
    elif message.content.lower() == '!kei me':
        info = await memory_db.get_user_info(message.author.id)
        if not info:
            await message.channel.send("Belum ada data lo di DB. Coba mention bot dulu.")
            return
        p = info['prefs']
        embed = discord.Embed(
            title=f"👤 {message.author.display_name}",
            color=0x00ff00,
        )
        embed.add_field(name="Member sejak", value=info['first_seen'][:10], inline=True)
        embed.add_field(name="Terakhir aktif", value=info['last_seen'][:16], inline=True)
        embed.add_field(name="Total messages", value=str(info['total_messages']), inline=True)
        nick = p.get('nickname') or "(default)"
        embed.add_field(
            name="Preferences",
            value=(
                f"`lang={p['lang']}` `tone={p['tone']}` "
                f"`length={p['response_length']}` `emoji={p['emoji_level']}` "
                f"`nickname={nick}`"
            ),
            inline=False,
        )
        await message.channel.send(embed=embed)

    # Channel leaderboard
    elif message.content.lower().startswith('!kei top'):
        top = await memory_db.get_top_users_in_channel(message.channel.id, limit=10)
        if not top:
            await message.channel.send("Belum ada data buat channel ini.")
            return
        ch_name = getattr(message.channel, 'name', 'DM')
        embed = discord.Embed(title=f"🏆 Top users di #{ch_name}", color=0xffd700)
        medals = ['🥇', '🥈', '🥉']
        lines = []
        for i, u in enumerate(top):
            prefix = medals[i] if i < 3 else f"`{i+1:>2}.`"
            name = u['username'] or f"<@{u['user_id']}>"
            lines.append(f"{prefix} **{name}** — {u['msg_count']} msg")
        embed.description = "\n".join(lines)
        await message.channel.send(embed=embed)

    # Admin: lookup activity for another user
    elif message.content.startswith('!kei whois'):
        if not (hasattr(message.author, 'guild_permissions')
                and message.author.guild_permissions.administrator):
            await message.channel.send("❌ Admin only.")
            return
        target = next((u for u in message.mentions if u != bot.user), None)
        if not target:
            await message.channel.send("❌ Usage: `!kei whois @user`")
            return
        info = await memory_db.get_user_info(target.id)
        if not info:
            await message.channel.send(f"Belum ada data `{target.display_name}` di DB.")
            return
        p = info['prefs']
        embed = discord.Embed(
            title=f"🔍 {target.display_name}",
            description=f"`{target.id}`",
            color=0x9b59b6,
        )
        embed.add_field(name="Member sejak", value=info['first_seen'][:10], inline=True)
        embed.add_field(name="Terakhir aktif", value=info['last_seen'][:16], inline=True)
        embed.add_field(name="Total messages", value=str(info['total_messages']), inline=True)
        nick = p.get('nickname') or "(default)"
        embed.add_field(
            name="Preferences",
            value=(
                f"`lang={p['lang']}` `tone={p['tone']}` "
                f"`length={p['response_length']}` `emoji={p['emoji_level']}` "
                f"`nickname={nick}`"
            ),
            inline=False,
        )
        await message.channel.send(embed=embed)

    # Help command
    elif message.content.startswith('!kei help'):
        help_embed = discord.Embed(
            title="🤖 Kei Bot Commands",
            description="Mention `@Kei` atau pakai prefix `!kei`. Tone & bahasa response disesuaikan ke prefs lo.",
            color=0x00ff00,
        )
        help_embed.add_field(
            name="💬 Chat",
            value=(
                "`@Kei <pertanyaan>` — Tanya dengan full context\n"
                "`!kei ask <pertanyaan>` — Sama, pakai prefix\n"
                "📸 Attach gambar saat mention → bot analisis gambarnya"
            ),
            inline=False,
        )
        help_embed.add_field(
            name="⚙️ Preferences",
            value=(
                "`!kei prefs` — Lihat prefs lo\n"
                "`!kei prefs <key>=<value> [...]` — Set (bisa multiple)\n"
                "`!kei prefs reset` — Balik ke default\n\n"
                "**Valid values:**\n"
                "• `lang` — `id`, `en`, `jawa`, `sunda`  *(default: id)*\n"
                "• `tone` — `casual`, `formal`, `santai`, `sarkas`  *(default: casual)*\n"
                "• `response_length` — `short`, `normal`, `detailed`  *(default: short)*\n"
                "• `emoji_level` — `none`, `minimal`, `normal`, `heavy`  *(default: minimal)*\n"
                "• `nickname` — free text, max 32 char  *(default: Discord display name)*\n\n"
                "Contoh: `!kei prefs lang=jawa tone=santai nickname=mas`"
            ),
            inline=False,
        )
        help_embed.add_field(
            name="👤 User",
            value=(
                "`!kei me` — Stats lo (member sejak, total msg, prefs)\n"
                "`!kei top` — Leaderboard channel ini\n"
                "`!kei whois @user` — 🔒 Admin: stats user lain"
            ),
            inline=False,
        )
        help_embed.add_field(
            name="🗃️ Memory & Search",
            value=(
                "`!kei search <keyword>` — Full-text search di channel ini\n"
                "`!kei gsearch <keyword>` — Cari di semua channel\n"
                "`!kei stats` — Statistik channel (30 hari)\n"
                "`!kei dbinfo` — Database overview"
            ),
            inline=False,
        )
        help_embed.add_field(
            name="🔄 Reset & Status",
            value=(
                "`!kei reset` / `clear` / `new` — Soft reset (DB tetap aman)\n"
                "`!kei purge` — Hard reset (HAPUS semua data channel)\n"
                "`!kei status` — Status channel & cache\n"
                "`!kei help` — Menu ini"
            ),
            inline=False,
        )
        await message.channel.send(embed=help_embed)
    
    # Legacy support for old commands (V2.0 backward compatibility)
    elif message.content.startswith('!ask '):
        await message.channel.send("ℹ️ **Command Updated!** Please use `!kei ask <question>` instead of `!ask`.\nType `!kei help` for all new commands.")
    
    elif message.content.startswith('!search'):
        await message.channel.send("ℹ️ **Command Updated!** Please use `!kei search <keyword>` (channel) or `!kei gsearch <keyword>` (global) instead of `!search`.\nType `!kei help` for all new commands.")
    
    elif message.content.startswith('!stats'):
        await message.channel.send("ℹ️ **Command Updated!** Please use `!kei stats` instead of `!stats`.\nType `!kei help` for all new commands.")
    
    elif message.content.startswith('!status'):
        await message.channel.send("ℹ️ **Command Updated!** Please use `!kei status` instead of `!status`.\nType `!kei help` for all new commands.")
    
    elif message.content.startswith('!help'):
        await message.channel.send("ℹ️ **Command Updated!** Please use `!kei help` instead of `!help`.\nType `!kei help` for all new commands.")
    
    elif message.content.lower() in ["!reset", "!clear", "!new"]:
        await message.channel.send("ℹ️ **Command Updated!** Please use `!kei reset` instead of `!reset`.\nType `!kei help` for all new commands.")

    # Status konteks
    elif message.content.lower() == "!kei status":
        channel_id = message.channel.id
        has_conversation = str(channel_id) in channel_conversations
        has_cache = channel_id in channel_context_cache
        
        # Get memory stats
        try:
            stats = await memory_db.get_channel_stats(channel_id, days=7)
            memory_conversations = stats['total_conversations']
        except:
            memory_conversations = 0
        
        status_msg = f"**Status Channel {message.channel.name}:**\n"
        status_msg += f"🗨️ Conversation ID: {'✅ Ada' if has_conversation else '❌ Tidak ada'}\n"
        status_msg += f"💾 Context Cache: {'✅ Ada' if has_cache else '❌ Tidak ada'}\n"
        status_msg += f"🗃️ Memory DB: {memory_conversations} conversations (7 days)\n"
        
        if has_conversation:
            conv_id = channel_conversations[str(channel_id)]
            status_msg += f"🔗 ID: `{conv_id[:20]}...`\n"
            
        if has_cache:
            cache_age = datetime.now() - channel_context_cache[channel_id]['timestamp']
            status_msg += f"⏰ Cache age: {int(cache_age.total_seconds())}s\n"
            
        status_msg += "\n**Commands:**\n"
        status_msg += "`!kei reset` - Soft reset (preserve database)\n"
        status_msg += "`!kei purge` - Hard reset (delete all data)\n"
        status_msg += "`!kei status` - Show this status\n"
        status_msg += "`!kei search <keyword>` - Search this channel\n"
        status_msg += "`!kei gsearch <keyword>` - Global search (all channels)\n"
        status_msg += "`!kei stats` - Channel statistics\n"
        status_msg += "`!kei help` - Complete help menu\n"
        status_msg += "`@Kei <message>` - Ask with full context\n"
        status_msg += "`!kei ask <message>` - Ask with full context"
        
        await message.channel.send(status_msg)

def run_bot():
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Bot error: {e}")
        raise

if __name__ == "__main__":
    run_bot()
