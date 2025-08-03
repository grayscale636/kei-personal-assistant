import os
import httpx
from dotenv import load_dotenv

load_dotenv()

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
API_URL = "http://192.168.100.220:5713/v1/chat-messages"

async def ask_dify(query, user_id, conversation_id=None):
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "streaming",
        "user": user_id
    }

    if conversation_id:
        payload["conversation_id"] = conversation_id
        print(f"[DEBUG] Using existing conversation_id: {conversation_id}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", API_URL, json=payload, headers=headers) as response:
                
                if response.status_code != 200:
                    print(f"[ERROR] Status {response.status_code}: {await response.aread()}")
                    return "Request failed - API returned error", None

                answer_text = ""
                final_conversation_id = conversation_id  # Default to existing
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            import json
                            chunk_data = json.loads(line[6:])  # Remove "data: " prefix
                            
                            # Handle different event types
                            event = chunk_data.get("event", "")
                            print(f"[DEBUG] Event: {event}")
                            
                            if event == "agent_message":
                                # Append message content
                                answer_chunk = chunk_data.get("answer", "")
                                answer_text += answer_chunk
                                print(f"[DEBUG] Answer chunk: {answer_chunk}")
                            
                            elif event == "message_end":
                                # Get conversation ID from final event
                                final_conversation_id = chunk_data.get("conversation_id")
                                print(f"[DEBUG] Conversation ended with ID: {final_conversation_id}")
                                break
                                
                        except json.JSONDecodeError as e:
                            print(f"[DEBUG] JSON decode error: {e}")
                            continue
                
                return answer_text.strip() or "No answer received.", final_conversation_id

    except Exception as err:
        print("[ERROR REQUEST FAILED]", err)
        return "Sorry, I'm having trouble connecting to the AI service.", None
