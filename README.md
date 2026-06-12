# Pie Chat — Windows

A Windows-native chat UI for the [Pie](https://github.com/pie-project/pie) inference engine with live token budget monitoring, conversation history, profiles, engine management, and Tree-of-Thought reasoning.

Built as part of a research collaboration with Prof. Lin Zhong's Efficient Computing Lab at Yale.

## Features

- **Conversation history** — Messages accumulate context across turns with per-turn and total token tracking
- **Profiles** — Four built-in profiles (Balanced, Precise, Creative, Compact) each bundling a system prompt, temperature, and max_tokens preset
- **Two-tier token limits** — Per-request limit (max_tokens) controls single response length; context length limit (MAX_CONTEXT_TOKENS = 2048) tracks total conversation tokens with a sliding window that drops oldest turns when the context limit approaches
- **Live token budget bar** — Real-time token usage per turn and across the full conversation
- **Clean response rendering** — Reasoning traces (<think> blocks) are stripped from the UI while preserved in history context
- **Tree-of-Thought inferlet** — Second inference mode running a 3-level parallel tree search (Propose -> Execute -> Reflect) across multiple branches with labeled streaming output
- **Engine management** — Engine tab showing server status, active model, running processes with terminate controls, and profile configurations

## Inferlets

Two inferlets are integrated:

**1. Token Budget Inferlet** (`my-first-inferlet`) — default chat mode. Tracks tokens consumed per turn and enforces a hard budget. Used for all normal conversation.

**2. Tree-of-Thought Inferlet** (`tree-of-thought`) — available via the Tree of Thought panel. Runs a 3-level parallel tree search (Propose -> Execute -> Reflect) across multiple branches. Each branch streams labeled output ([1] PROPOSE, [1.1] EXECUTE, [1.1.1] REFLECT). Note: meaningful ToT output requires an 8B+ model; smaller models produce degenerate text.

## Stack

- FastAPI + WebSocket backend
- Vanilla HTML/JS frontend
- Pie Python client (`pie_client`)
- Inferlets: token-budget + tree-of-thought (Rust -> WASM)

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
| / | GET | Chat UI |
| /chat | WebSocket | Chat with conversation history |
| /engine/status | GET | Engine status, model, active processes |
| /engine/terminate/{id} | POST | Terminate a process by ID |
| /profiles | GET | List all profiles |

## Notes

- `chat-apc` inferlet from RatioThink uses POSIX shared memory (`shm_open`/`shm_unlink`) which is not available on Windows. Conversation context is managed at the application layer instead. See [issue #412](https://github.com/pie-project/pie/issues/412) for the tracked Windows daemon compatibility problem.
- The internal token changes every time `pie serve` restarts — update `PIE_TOKEN` in `main.py` accordingly.
- Tree-of-Thought uses `launch_process` (not `launch_daemon`) so it works on Windows without the shared memory limitation.

## Author

Dhruv Dubey — [github.com/zatchbell1311-wq](https://github.com/zatchbell1311-wq)
