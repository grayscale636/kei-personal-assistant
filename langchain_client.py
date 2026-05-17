import os
import io
import json
import base64
import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Langchain 1.3.x — ConversationBufferMemory pindah ke langchain_classic
from langchain_classic.memory import ConversationBufferMemory
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

load_dotenv()


LANG_MAP = {
    'id': 'Bahasa Indonesia',
    'en': 'English',
    'jawa': 'Bahasa Jawa (informal, ngoko)',
    'sunda': 'Bahasa Sunda (informal)',
}

TONE_MAP = {
    'casual': 'a friendly, casual tone',
    'formal': 'a formal, professional tone',
    'santai': 'a very relaxed, slang-heavy tone',
    'sarkas': 'a witty, lightly sarcastic tone',
}

LENGTH_MAP = {
    'short': 'Keep responses under 30 words unless detail is explicitly requested.',
    'normal': 'Keep responses concise but informative.',
    'detailed': 'Provide thorough, detailed responses with examples when relevant.',
}

EMOJI_MAP = {
    'none': 'Do not use emojis at all.',
    'minimal': 'Use emojis sparingly — at most 1 per response.',
    'normal': 'Use emojis naturally to enhance expressiveness.',
    'heavy': 'Use emojis frequently and expressively.',
}


def build_system_prompt(prefs=None):
    """Generate a system prompt string from user preferences."""
    p = {
        'lang': 'id',
        'tone': 'casual',
        'nickname': None,
        'response_length': 'short',
        'emoji_level': 'minimal',
    }
    if prefs:
        p.update({k: v for k, v in prefs.items() if v is not None or k == 'nickname'})

    parts = [
        "You are Kei, a helpful AI assistant in a Discord server.",
        f"Respond in {LANG_MAP.get(p['lang'], LANG_MAP['id'])} with {TONE_MAP.get(p['tone'], TONE_MAP['casual'])}.",
        LENGTH_MAP.get(p['response_length'], LENGTH_MAP['short']),
        EMOJI_MAP.get(p['emoji_level'], EMOJI_MAP['minimal']),
    ]
    if p.get('nickname'):
        parts.append(f'Address the user as "{p["nickname"]}".')

    return " ".join(parts)

class LangchainDeepSeekClient:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            openai_api_key=self.api_key,
            openai_api_base=self.base_url,
            temperature=0.5,
            max_tokens=500
        )
        
        self.conversation_memories = {}
    
    async def analyze_image(self, image_url: str, prompt: str) -> str:
        try:
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            
            if openrouter_key:
                resp = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openrouter_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://kei-bot.discord",
                    },
                    json={
                        "model": "google/gemini-2.5-flash",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": image_url}}
                            ]
                        }],
                        "max_tokens": 500
                    },
                    timeout=30
                )
                if resp.ok:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                print(f"[WARN] OpenRouter image fail: {resp.status_code}")
            return "Maaf, saya tidak bisa menganalisis gambar saat ini."
        except Exception as e:
            print(f"[ERROR] Image analysis: {e}")
            return "Maaf, error saat analisis gambar."

    def get_memory(self, conversation_id):
        if conversation_id not in self.conversation_memories:
            self.conversation_memories[conversation_id] = ConversationBufferMemory(
                memory_key="history",
                return_messages=True
            )
        return self.conversation_memories[conversation_id]
    
    async def ask(self, query, user_id, conversation_id=None, prefs=None):
        try:
            if not conversation_id:
                conversation_id = f"user_{user_id}_default"

            memory = self.get_memory(conversation_id)
            system_prompt = build_system_prompt(prefs)

            messages = [SystemMessage(content=system_prompt)]
            messages.extend(memory.chat_memory.messages)
            messages.append(HumanMessage(content=query))

            response = await self.llm.ainvoke(messages)
            response_text = response.content

            memory.chat_memory.add_user_message(query)
            memory.chat_memory.add_ai_message(response_text)

            return response_text, conversation_id

        except Exception as e:
            print(f"[ERROR] Langchain DeepSeek request failed: {e}")
            return "Sorry, I'm having trouble processing your request.", conversation_id
    
    def clear_conversation(self, conversation_id):
        if conversation_id in self.conversation_memories:
            del self.conversation_memories[conversation_id]
            return True
        return False

_client_instance = None

def get_langchain_client():
    global _client_instance
    if _client_instance is None:
        _client_instance = LangchainDeepSeekClient()
    return _client_instance

async def ask_langchain(query, user_id, conversation_id=None, prefs=None):
    client = get_langchain_client()
    return await client.ask(query, user_id, conversation_id, prefs=prefs)


async def analyze_image_url(image_url, prompt):
    client = get_langchain_client()
    return await client.analyze_image(image_url, prompt)
