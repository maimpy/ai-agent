import threading
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from ai_engine import execute_ai_with_fallback
from config import load_system_rules

app_api = FastAPI()
server_ref = {"instance": None, "running": False, "token": "sk-local-agent-2026"}

class ChatMessage(BaseModel):
    model: str = "gpt-4o"
    messages: list

@app_api.post("/v1/chat/completions")
async def proxy_chat_completions(payload: ChatMessage, authorization: str = Header(None)):
    # Перевірка локального токена
    expected_token = f"Bearer {server_ref['token']}"
    if authorization != expected_token:
        raise HTTPException(status_code=401, detail="Невірний локальний API токен!")

    system_rules = load_system_rules()
    full_messages = [{"role": "system", "content": f"Правила:\n{system_rules}"}] + payload.messages

    def api_logger(msg):
        if server_ref["instance"] and hasattr(server_ref["instance"], "log"):
            server_ref["instance"].log(f"[API Server] {msg}")

    try:
        app_inst = server_ref["instance"]
        getter = lambda: app_inst.provider_entries if app_inst else None
        
        answer = execute_ai_with_fallback(full_messages, provider_entries_getter=getter, logger=api_logger)
        
        return {
            "id": "chatcmpl-local",
            "object": "chat.completion",
            "created": 1234567890,
            "model": payload.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start_server_in_background(app_instance, token):
    server_ref["instance"] = app_instance
    server_ref["token"] = token
    server_ref["running"] = True
    
    def run():
        uvicorn.run(app_api, host="127.0.0.1", port=8000, log_level="warning")
        
    t = threading.Thread(target=run, daemon=True)
    t.start()