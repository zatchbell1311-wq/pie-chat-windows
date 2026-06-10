# Pie Chat — Windows

A Windows-native chat UI for the [Pie](https://github.com/pie-project/pie) inference engine with live token budget monitoring, conversation history, profiles, and engine management.

Built as part of a research collaboration with Prof. Lin Zhong's Efficient Computing Lab at Yale.

## Features

- **Conversation history** — Messages accumulate context across turns with per-turn and total token tracking
- **Profiles** — Four built-in profiles (Balanced, Precise, Creative, Compact) each bundling a system prompt, temperature, and max_tokens preset
- **Live token budget bar** — Real-time token usage per turn and across the full conversation
- **Engine management** — Engine tab showing server status, active model, running processes with terminate controls, and profile configurations

## Stack

- FastAPI + WebSocket backend
- Vanilla HTML/JS frontend
- Pie Python client (`pie_client`)
- Inferlet: token-budget inferlet (Rust → WASM)

## Run

**Terminal 1 — start Pie server:**
```bash
cd ~/pie
pie serve --no-auth --debug
```

Copy the `internal token:` from the output and paste it into `main.py` as `PIE_TOKEN`.

**Terminal 2 — start chat app:**
```bash
cd ~/pie-chat-windows
python -m uvicorn main:app --host 0.0.0.0 --port 3000
```

Open http://localhost:3000

## Profiles

| Profile | Max Tokens | Temperature | System Prompt |
|---------|-----------|-------------|---------------|
| Balanced | 128 | 0.6 | Helpful assistant |
| Precise | 256 | 0.1 | Factual, concise |
| Creative | 512 | 1.2 | Think outside the box |
| Compact | 64 | 0.7 | Under 3 sentences |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Chat UI |
| `/chat` | WebSocket | Chat with conversation history |
| `/engine/status` | GET | Engine status, model, active processes |
| `/engine/terminate/{id}` | POST | Terminate a process by ID |
| `/profiles` | GET | List all profiles |



Results:
<img width="1919" height="977" alt="Screenshot 2026-06-10 154203" src="https://github.com/user-attachments/assets/d4d49574-c5de-44be-83df-f3280bc3f817" />
<img width="1919" height="843" alt="Screenshot 2026-06-10 154129" src="https://github.com/user-attachments/assets/2c64a7bf-27b4-4336-b111-58defbe63dfa" />
<img width="1919" height="979" alt="Screenshot 2026-06-10 153933" src="https://github.com/user-attachments/assets/459b9a0e-5c4e-47b3-8432-c16a8c23a2c5" />




## Notes

- `chat-apc` inferlet from RatioThink uses POSIX shared memory which is not available on Windows. Conversation context is managed at the application layer instead.
- The internal token changes every time `pie serve` restarts — update `PIE_TOKEN` in `main.py` accordingly.

## Author

Dhruv Dubey — [github.com/zatchbell1311-wq](https://github.com/zatchbell1311-wq)
