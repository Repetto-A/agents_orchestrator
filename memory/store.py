import uuid
from datetime import datetime
from config.settings import supabase


def get_or_create_conversation(store_id: str, conversation_id: str = None) -> str:
    """Get existing conversation or create a new one. Returns conversation_id."""
    if conversation_id:
        result = supabase.table("conversations").select("id").eq("id", conversation_id).execute()
        if result.data:
            return conversation_id

    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    supabase.table("conversations").insert({
        "id": new_id,
        "store_id": store_id,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }).execute()
    return new_id


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    intent: str = None,
    agent: str = None,
) -> str:
    """Save a message to the conversation. Returns message_id."""
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    supabase.table("messages").insert({
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "intent": intent,
        "agent": agent,
        "created_at": now,
    }).execute()

    # Update conversation timestamp
    supabase.table("conversations").update({"updated_at": now}).eq("id", conversation_id).execute()
    return msg_id


def get_recent_messages(conversation_id: str, limit: int = 10) -> list[dict]:
    """Get the last N messages for a conversation."""
    result = (
        supabase.table("messages")
        .select("role, content, intent, agent, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    # Return in chronological order
    return list(reversed(result.data))


def format_history_for_prompt(messages: list[dict]) -> str:
    """Format message history as a string for inclusion in LLM prompts."""
    if not messages:
        return "No previous conversation."

    lines = []
    for msg in messages:
        role_label = "Customer" if msg["role"] == "user" else "You (Sales Agent)"
        lines.append(f"{role_label}: {msg['content']}")
    return "\n".join(lines)
