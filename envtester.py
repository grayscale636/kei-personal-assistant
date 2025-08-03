from dotenv import load_dotenv
import os

load_dotenv()

def check_env():
    token = os.getenv("DISCORD_TOKEN")
    dify_api_url = os.getenv("DIFY_API_URL")
    dify_api_key = os.getenv("DIFY_API_KEY")
    if not token:
        print("Error: DISCORD_TOKEN is not set in .env")
    if not dify_api_url:
        print("Error: DIFY_API_URL is not set in .env")
    if not dify_api_key:
        print("Error: DIFY_API_KEY is not set in .env")
    if token and dify_api_url and dify_api_key:
        print("All environment variables are set correctly.")

if __name__ == "__main__":
    check_env()