#!/usr/bin/env python
"""Dev tool: a tiny mock of JarvYZ's /ws mode broadcast.

Stands up a WebSocket server on :8765 that serves /ws and pushes the same
`{"event_type": "mode", "state": ...}` frames JarvYZ emits, cycling through the
five states. Lets you test the ring daemon's JarvYZ bridge without running JarvYZ.

    uv run python tools/mock_jarvyz_ws.py
    # then, in another shell:
    uv run yz-pixel-ring

Needs `websockets` (dev-only; not a daemon dependency).
"""

import asyncio
import json

import websockets

MODES = ["boot", "idle", "listening", "thinking", "speaking"]
PERIOD_S = 2.0


async def handler(ws):
    # JarvYZ serves the bus at /ws; ignore anything else.
    if ws.request.path != "/ws":
        await ws.close()
        return
    print(f"client connected on {ws.request.path}")
    i = 0
    try:
        while True:
            state = MODES[i % len(MODES)]
            await ws.send(json.dumps({"event_type": "mode", "ts": 0, "state": state}))
            print(f"  -> mode {state}")
            i += 1
            await asyncio.sleep(PERIOD_S)
    except websockets.ConnectionClosed:
        print("client disconnected")


async def main():
    async with websockets.serve(handler, "127.0.0.1", 8765):
        print("mock JarvYZ ws on ws://127.0.0.1:8765/ws (Ctrl+C to stop)")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
