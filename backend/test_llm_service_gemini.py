import asyncio
import os
from dotenv import load_dotenv

# Set the environment variables before importing app modules
load_dotenv(".env")
os.environ["MODEL"] = "gemini-3.1-flash-lite"
os.environ["MAINTENANCE_MODEL"] = "gemini-3.1-flash-lite"

from app.services.llm.llm_service import get_llm_response

def main():
    messages = [{"role": "user", "content": "Hello, is this working?"}]
    response = get_llm_response(messages, purpose="test")
    print("Response:", response)

if __name__ == "__main__":
    main()
