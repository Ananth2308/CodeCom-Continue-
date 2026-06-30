import json
import time
import uuid
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.agent_loop import AgentLoop


app = FastAPI(title="Dev Agent Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Suspended sessions waiting for approval
suspended_sessions: dict[str, dict] = {}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "agent"
    messages: list[ChatMessage]
    stream: bool = True
    temperature: float | None = None
    max_tokens: int | None = None


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Check if this is a response to a suspended session
    conv_key = _conversation_key(messages)
    suspended = suspended_sessions.pop(conv_key, None)

    if suspended:
        user_response = messages[-1]["content"].strip().lower()
        approved = user_response in ("yes", "y", "approve", "ok", "sure", "go", "do it")

        if not approved:
            # User didn't approve — treat their message as a new prompt instead
            suspended_sessions.pop(conv_key, None)
            if request.stream:
                return StreamingResponse(
                    _stream_agent(messages),
                    media_type="text/event-stream",
                )
            else:
                full = ""
                async for chunk in _run_agent(messages):
                    full += chunk
                return _non_stream_response(full)

        if request.stream:
            return StreamingResponse(
                _stream_resumed(suspended, approved, messages),
                media_type="text/event-stream",
            )
        else:
            full = ""
            async for chunk in _run_resumed(suspended, approved, messages):
                full += chunk
            return _non_stream_response(full)

    # New conversation
    if request.stream:
        return StreamingResponse(
            _stream_agent(messages),
            media_type="text/event-stream",
        )
    else:
        full = ""
        async for chunk in _run_agent(messages):
            full += chunk
        return _non_stream_response(full)


async def _run_agent(messages: list[dict]) -> AsyncGenerator[str, None]:
    agent = AgentLoop()
    try:
        async for event in agent.run(messages):
            if isinstance(event, dict) and event.get("type") == "approval_needed":
                conv_key = _conversation_key(messages)
                suspended_sessions[conv_key] = {
                    "messages_so_far": event["messages_so_far"],
                    "tool_call": event["tool_call"],
                    "original_messages": messages,
                }
                return
            else:
                yield event
    finally:
        await agent.close()


async def _run_resumed(suspended: dict, approved: bool, messages: list[dict]) -> AsyncGenerator[str, None]:
    agent = AgentLoop()
    try:
        async for event in agent.resume(
            suspended["messages_so_far"],
            suspended["tool_call"],
            approved,
        ):
            if isinstance(event, dict) and event.get("type") == "approval_needed":
                conv_key = _conversation_key(messages)
                suspended_sessions[conv_key] = {
                    "messages_so_far": event["messages_so_far"],
                    "tool_call": event["tool_call"],
                    "original_messages": messages,
                }
                return
            else:
                yield event
    finally:
        await agent.close()


async def _stream_agent(messages: list[dict]) -> AsyncGenerator[str, None]:
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    created = int(time.time())

    async for chunk in _run_agent(messages):
        data = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": "dev-agent",
            "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(data)}\n\n"

    yield f"data: {json.dumps({'id': chat_id, 'object': 'chat.completion.chunk', 'created': created, 'model': 'dev-agent', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"


async def _stream_resumed(suspended: dict, approved: bool, messages: list[dict]) -> AsyncGenerator[str, None]:
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    created = int(time.time())

    async for chunk in _run_resumed(suspended, approved, messages):
        data = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": "dev-agent",
            "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(data)}\n\n"

    yield f"data: {json.dumps({'id': chat_id, 'object': 'chat.completion.chunk', 'created': created, 'model': 'dev-agent', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"


def _non_stream_response(content: str) -> JSONResponse:
    return JSONResponse({
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "dev-agent",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })


def _conversation_key(messages: list[dict]) -> str:
    for msg in messages:
        if msg["role"] == "user":
            return str(hash(msg["content"]))
    return "default"


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "dev-agent", "object": "model", "created": int(time.time()), "owned_by": "dev-agent-proxy"}],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "workspace": settings.workspace_dir}
