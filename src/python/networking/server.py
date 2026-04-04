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
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import HOST, PORT, MAX_CONCURRENT_QUERIES
from networking.router import handle


_semaphore: asyncio.Semaphore | None = None

async def _async_write(writer: asyncio.StreamWriter, msg: str) -> None:
    writer.write(msg.encode("utf-8"))
    await writer.drain()

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
                loop = asyncio.get_running_loop()

                def send(msg) -> None: # Sends a message while C send_and_print functions is in while loop
                    print(msg)
                    future = asyncio.run_coroutine_threadsafe(
                        _async_write(writer, msg+"\n"), loop
                    )
                    future.result()
                result = await loop.run_in_executor(None, lambda: handle(payload, send))

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
            
def _configure_hadoop():
    if sys.platform != "win32":
        return
    
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )

    hadoop_bin = os.path.join(project_root, "hadoop", "bin")
    winutils   = os.path.join(hadoop_bin, "winutils.exe")

    if not os.path.exists(winutils):
        print(f"WARNING: winutils.exe not found at {winutils}", flush=True)
        return

    os.environ["HADOOP_HOME"] = os.path.join(project_root, "hadoop")
    os.environ["PATH"]= hadoop_bin + os.pathsep + os.environ["PATH"]
    print(f"Hadoop configured: {project_root}\\hadoop", flush=True)

async def _run() -> None:
    global _semaphore
    _semaphore = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)

    server = await asyncio.start_server(_handle_connection, HOST, PORT)
    addrs  = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"LibQuery server listening on {addrs}")
    print(f"Max concurrent queries: {MAX_CONCURRENT_QUERIES}")

    print("Initialising Spark...", flush=True)
    _configure_hadoop()
    print("Hadoop ready.", flush=True)
    from query.engine import _get_spark
    _get_spark() #init
    print("Spark ready.", flush=True)


    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"\nFatal error: {e}")
    finally:
        input("\nPress Enter to exit...")
