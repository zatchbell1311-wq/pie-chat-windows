import asyncio
import json
import subprocess
import sys
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pie_client import PieClient, Event

app = FastAPI()

PIE_URL = "ws://127.0.0.1:8080"
PIE_TOKEN = "MWxD-cjwKYXsWhTcTSBGYiNngfcpW-vjy8lHAShNZXuPVFA9kcVPdhZMbjBpHtLy"
INFERLET = "my-first-inferlet@0.1.0"
WASM_PATH = Path.home() / "my-first-inferlet/target/wasm32-wasip2/release/my_first_inferlet.wasm"
TOML_PATH = Path.home() / "my-first-inferlet/Pie.toml"

PROFILES = {
    "balanced": {"max_tokens": 128, "temperature": 0.6, "system": "You are a helpful assistant."},
    "precise":  {"max_tokens": 256, "temperature": 0.1, "system": "You are a precise, factual assistant. Be concise and accurate."},
    "creative": {"max_tokens": 512, "temperature": 1.2, "system": "You are a creative assistant. Think outside the box."},
    "compact":  {"max_tokens": 64,  "temperature": 0.7, "system": "You are a brief assistant. Keep all answers under 3 sentences."},
}

def build_prompt(history, new_user_msg, system_prompt):
    lines = [f"System: {system_prompt}"]
    for turn in history:
        lines.append(f"User: {turn['user']}")
        lines.append(f"Assistant: {turn['assistant']}")
    lines.append(f"User: {new_user_msg}")
    lines.append("Assistant:")
    return "\n".join(lines)

@app.get("/")
async def index():
    html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)

@app.get("/engine/status")
async def engine_status():
    try:
        async with PieClient(PIE_URL) as client:
            await client.auth_by_token(PIE_TOKEN)
            procs = await asyncio.wait_for(client.list_processes(), timeout=5)
            return JSONResponse({
                "status": "online",
                "server": PIE_URL,
                "model": "Qwen/Qwen3-0.6B",
                "inferlet": INFERLET,
                "active_processes": len(procs) if procs else 0,
                "processes": procs if procs else [],
            })
    except Exception as e:
        return JSONResponse({"status": "offline", "error": str(e)}, status_code=503)

@app.post("/engine/terminate/{process_id}")
async def terminate_process(process_id: str):
    try:
        async with PieClient(PIE_URL) as client:
            await client.auth_by_token(PIE_TOKEN)
            await client.terminate_process(process_id)
            return JSONResponse({"terminated": process_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

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

            while True:
                data = await ws.receive_json()

                if data.get("type") == "clear_history":
                    history = []
                    total_tokens_used = 0
                    await ws.send_json({"type": "history_cleared"})
                    continue

                user_msg = data.get("prompt", "")
                max_tokens = int(data.get("max_tokens", 128))
                temperature = float(data.get("temperature", 0.6))
                system_prompt = data.get("system_prompt", "You are a helpful assistant.")

                full_prompt = build_prompt(history, user_msg, system_prompt)
                await ws.send_json({"type": "start"})

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

                            tokens_this_turn = result.get("tokens_used", 0)
                            total_tokens_used += tokens_this_turn

                            import re
                            clean_reply = re.sub(r"<think>.*?</think>", "", assistant_reply, flags=re.DOTALL).strip()
                            if clean_reply:
                                history.append({"user": user_msg, "assistant": clean_reply})

                            await ws.send_json({
                                "type": "done",
                                "tokens_used": tokens_this_turn,
                                "token_budget": result.get("token_budget", max_tokens),
                                "utilization_pct": result.get("utilization_pct", 0.0),
                                "budget_exhausted": result.get("budget_exhausted", False),
                                "total_tokens": total_tokens_used,
                                "history_turns": len(history),
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
