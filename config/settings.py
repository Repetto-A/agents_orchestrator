import os
from dotenv import load_dotenv
import anthropic
from supabase import create_client

load_dotenv()

# Supabase client (REST API)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Anthropic client singleton
_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY environment variable is not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def get_llm():
    def call_llm(prompt: str, system_prompt: str = None) -> str:
        try:
            client = get_client()
            kwargs = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            response = client.messages.create(**kwargs)
            return (response.content[0].text or "").strip()
        except Exception as exc:
            return f"An error occurred during the LLM call: {type(exc).__name__}: {exc}"

    return call_llm
