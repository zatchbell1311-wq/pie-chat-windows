import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pie_client import PieClient, Event

app = FastAPI()

HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

PIE_URL = "ws://127.0.0.1:8080"
PIE_TOKEN = "N8uouLRG3G0CZ_c_XG_-cmncZab6-FOOun4cUkx0e9-CBpcjxGwwwc8AXKeqpN4u"
INFERLET = "my-first-inferlet@0.1.0"
WASM_PATH = Path.home() / "my-first-inferlet/target/wasm32-wasip2/release/my_first_inferlet.wasm"
TOML_PATH = Path.home() / "my-first-inferlet/Pie.toml"

@app.get("/")
async def index():
    return HTMLResponse(HTML)

@app.websocket("/chat")
async def chat(ws: WebSocket):
    await ws.accept()
    try:
        async with PieClient(PIE_URL) as client:
            await client.auth_by_token(PIE_TOKEN)
            await client.install_program(WASM_PATH, TOML_PATH, force_overwrite=True)

            while True:
                data = await ws.receive_json()
                prompt = data.get("prompt", "")
                max_tokens = int(data.get("max_tokens", 128))
                temperature = float(data.get("temperature", 0.6))

                await ws.send_json({"type": "start"})

                try:
                    proc = await client.launch_process(
                        INFERLET,
                        input={
                            "prompt": prompt,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                    )

                    output = ""
                    while True:
                        event, value = await asyncio.wait_for(proc.recv(), timeout=120)
                        if event == Event.Stdout:
                            output += value
                            await ws.send_json({"type": "token", "text": value})
                        elif event == Event.Return:
                            try:
                                result = json.loads(value)
                            except Exception:
                                result = {"text": value}
                            await ws.send_json({
                                "type": "done",
                                "tokens_used": result.get("tokens_used", 0),
                                "token_budget": result.get("token_budget", max_tokens),
                                "utilization_pct": result.get("utilization_pct", 0.0),
                                "budget_exhausted": result.get("budget_exhausted", False),
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
        await ws.send_json({"type": "error", "msg": f"Server error: {str(e)}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
