"""
main.c connects over TCP and sends a JSON payload, receives
a plain-text result

Start with:
    libquery host
    this calls":
    python -m networking.server
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import HOST, PORT, MAX_CONCURRENT_QUERIES
from networking.router import handle

log_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs", "server.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("libquery")

_semaphore: asyncio.Semaphore | None = None


async def _handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    async with _semaphore:
        addr = writer.get_extra_info("peername")
        try:
            # Read until the client closes the write
            raw = await reader.read(65536)
            if not raw:
                return

            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as e:
                result = f"ERROR: malformed JSON : {e}"
            else:
                # handle() is synchronous
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, handle, payload)

            writer.write(result.encode("utf-8"))
            await writer.drain()

        except Exception as e:
            writer.write(f"ERROR: server exception : {e}".encode("utf-8"))
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def _run() -> None:
    global _semaphore
    _semaphore = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)

    server = await asyncio.start_server(_handle_connection, HOST, PORT)
    addrs  = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"LibQuery server listening on {addrs}")
    print(f"Max concurrent queries: {MAX_CONCURRENT_QUERIES}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(_run())
