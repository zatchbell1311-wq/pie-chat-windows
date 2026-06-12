import asyncio
import json
import re
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pie_client import PieClient, Event

app = FastAPI()
HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

PIE_URL = "ws://127.0.0.1:8080"
PIE_TOKEN = "tTrrNpxPUp1E4bfMOULy0xFOk0k0WJz7iZAqDT0Q-EJZdAzuC9VEvYa9dgfqhCgq"
INFERLET = "my-first-inferlet@0.1.0"
WASM_PATH = Path.home() / "my-first-inferlet/target/wasm32-wasip2/release/my_first_inferlet.wasm"
TOML_PATH = Path.home() / "my-first-inferlet/Pie.toml"

TOT_INFERLET = "tree-of-thought@0.1.0"
TOT_WASM_PATH = Path(__file__).parent / "tree-of-thought-inferlet" / "tree_of_thought.wasm"
TOT_TOML_PATH = Path(__file__).parent / "tree-of-thought-inferlet" / "Pie.toml"

MAX_CONTEXT_TOKENS = 2048

PROFILES = {
    "balanced": {"max_tokens": 128, "temperature": 0.6, "system": "You are a helpful assistant."},
    "precise":  {"max_tokens": 256, "temperature": 0.1, "system": "You are a precise, factual assistant. Be concise and accurate."},
    "creative": {"max_tokens": 512, "temperature": 1.2, "system": "You are a creative assistant. Think outside the box."},
    "compact":  {"max_tokens": 64,  "temperature": 0.7, "system": "You are a brief assistant. Keep all answers under 3 sentences."},
}

def estimate_tokens(text):
    return max(1, len(text) // 4)

def build_prompt(history, new_user_msg, system_prompt, max_tokens_this_turn):
    available = MAX_CONTEXT_TOKENS - max_tokens_this_turn
    system_line = "System: " + system_prompt + "\n"
    current_turn = "User: " + new_user_msg + "\nAssistant:"
    base_tokens = estimate_tokens(system_line + current_turn)
    if base_tokens >= available:
        return system_line + current_turn
    history_lines = []
    used = base_tokens
    for turn in reversed(history):
        block = "User: " + turn["user"] + "\nAssistant: " + turn["assistant"] + "\n"
        cost = estimate_tokens(block)
        if used + cost > available:
            break
        history_lines.insert(0, block)
        used += cost
    return system_line + "".join(history_lines) + current_turn

@app.get("/")
async def index():
    return HTMLResponse(HTML)

@app.get("/profiles")
async def get_profiles():
    return JSONResponse(PROFILES)

@app.websocket("/chat")
async def chat(ws: WebSocket):
    await ws.accept()
    history = []
    total_tokens_used = 0
    try:
        async with PieClient(PIE_URL) as client:
            await client.auth_by_token(PIE_TOKEN)
            await client.install_program(WASM_PATH, TOML_PATH, force_overwrite=True)
            await client.install_program(TOT_WASM_PATH, TOT_TOML_PATH, force_overwrite=True)
            while True:
                data = await ws.receive_json()

                if data.get("type") == "clear_history":
                    history = []
                    total_tokens_used = 0
                    await ws.send_json({"type": "history_cleared"})
                    continue

                if data.get("type") == "tot":
                    question = data.get("question", "")
                    num_branches = int(data.get("num_branches", 2))
                    tot_max_tokens = int(data.get("max_tokens", 256))

                    await ws.send_json({"type": "tot_start"})
                    try:
                        proc = await client.launch_process(
                            TOT_INFERLET,
                            input={
                                "question": question,
                                "num_branches": num_branches,
                                "max_tokens": tot_max_tokens,
                            },
                        )
                        while True:
                            event, value = await asyncio.wait_for(proc.recv(), timeout=300)
                            if event == Event.Stdout:
                                await ws.send_json({"type": "tot_token", "text": value})
                            elif event == Event.Return:
                                await ws.send_json({"type": "tot_done"})
                                break
                            elif event == Event.Error:
                                await ws.send_json({"type": "error", "msg": str(value)})
                                break
                    except Exception as e:
                        await ws.send_json({"type": "error", "msg": str(e)})
                    continue

                user_msg = data.get("prompt", "")
                max_tokens = int(data.get("max_tokens", 128))
                temperature = float(data.get("temperature", 0.6))
                system_prompt = data.get("system_prompt", "You are a helpful assistant.")

                full_prompt = build_prompt(history, user_msg, system_prompt, max_tokens)
                prompt_tokens = estimate_tokens(full_prompt)

                await ws.send_json({
                    "type": "start",
                    "prompt_tokens": prompt_tokens,
                    "context_limit": MAX_CONTEXT_TOKENS,
                    "history_turns_included": len(history),
                })

                try:
                    proc = await client.launch_process(
                        INFERLET,
                        input={
                            "prompt": full_prompt,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                    )
                    assistant_reply = ""
                    while True:
                        event, value = await asyncio.wait_for(proc.recv(), timeout=120)
                        if event == Event.Stdout:
                            assistant_reply += value
                            await ws.send_json({"type": "token", "text": value})
                        elif event == Event.Return:
                            try:
                                result = json.loads(value)
                            except Exception:
                                result = {"text": value}

                            clean_reply = re.sub(r"<think>.*?</think>", "", assistant_reply, flags=re.DOTALL).strip()
                            if clean_reply:
                                history.append({"user": user_msg, "assistant": clean_reply})

                            tokens_this_turn = result.get("tokens_used", estimate_tokens(assistant_reply))
                            total_tokens_used += tokens_this_turn

                            await ws.send_json({
                                "type": "done",
                                "tokens_used": tokens_this_turn,
                                "token_budget": result.get("token_budget", max_tokens),
                                "utilization_pct": result.get("utilization_pct", 0.0),
                                "budget_exhausted": result.get("budget_exhausted", False),
                                "total_tokens": total_tokens_used,
                                "history_turns": len(history),
                                "context_used_pct": round(prompt_tokens / MAX_CONTEXT_TOKENS * 100, 1),
                            })
                            break
                        elif event == Event.Error:
                            await ws.send_json({"type": "error", "msg": str(value)})
                            break
                except Exception as e:
                    await ws.send_json({"type": "error", "msg": str(e)})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "msg": f"Server error: {str(e)}"})
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
