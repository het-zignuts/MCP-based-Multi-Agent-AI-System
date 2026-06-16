import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(".env")

api_key = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

try:
    response = client.chat.completions.create(
        model="models/gemini-3.1-flash-lite",
        messages=[{"role": "user", "content": "Hello, is this working?"}]
    )
    print("Response:", response.choices[0].message.content)
except Exception as e:
    print("Error:", e)
