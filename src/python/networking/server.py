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
import hashlib
import time
import signal
import networking.registry as registry
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config.settings import HOST, PORT, MAX_CONCURRENT_QUERIES
from networking.router import handle


_semaphore: asyncio.Semaphore | None = None

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TOKEN_FILE = os.path.join(PROJECT_ROOT, "data", "serverdata", "admin.token")

def generate_admin_token() -> str:
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    start_time = time.time()
    raw = f"{start_time}".encode() + os.urandom(32)
    token = hashlib.sha256(raw).hexdigest()

    with open(TOKEN_FILE, "w") as f:
        f.write(token)

    if sys.platform != "win32":
        os.chmod(TOKEN_FILE, 0o600)

    print(f"Admin token created.", flush=True)
    return token

def destroy_admin_token() -> None:
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            print("Admin token destroyed.", flush=True)
    except Exception as e:
        print(f"WARNING: could not destroy token file: {e}", flush=True)
        
def valid_token(token: str) -> bool:
    try:
        with open(TOKEN_FILE, "r") as f:
            saved_token = f.read().strip()
        return token == saved_token
    except OSError:
        return False

def _handle_signal(sig, frame) -> None:
    print(f"\nSignal {sig} received, shutting down...", flush=True)
    destroy_admin_token()
    sys.exit(0)
async def _async_write(writer: asyncio.StreamWriter, msg: str) -> None:
    writer.write(msg.encode("utf-8"))
    await writer.drain()

async def _handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    async with _semaphore:
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
import subprocess

def configure_java() -> bool:
    import pyspark
    spark_version = tuple(int(x) for x in pyspark.__version__.split(".")[:2])
    java_version = "17" if spark_version >= (3, 3) else "11"
    print(f"PySpark {pyspark.__version__} detected, looking for Java {java_version}...", flush=True)

    is_windows = sys.platform == "win32"

    if is_windows:
        candidates = [
            r"C:\Program Files\Eclipse Adoptium",
            r"C:\Program Files\Microsoft",
            r"C:\Program Files\Java",
            r"C:\Program Files\Amazon Corretto",
        ]
        java_exe = "java.exe"
    else:
        candidates = [
            "/usr/lib/jvm",
            "/usr/java",
            "/opt/java",
            "/opt/jdk"]
        java_exe = "java"

    for base in candidates:
        if not os.path.exists(base):
            continue
        for entry in os.listdir(base):
            if java_version in entry:
                java_home = os.path.join(base, entry)
                java_bin = os.path.join(java_home, "bin", java_exe)
                if os.path.exists(java_bin):
                    os.environ["JAVA_HOME"] = java_home
                    os.environ["PATH"] = os.path.join(java_home, "bin") + os.pathsep + os.environ["PATH"]
                    print(f"Java {java_version} found: {java_home}", flush=True)
                    return True

    
    try:
        which_cmd = ["where", "java"] if is_windows else ["which", "-a", "java"]
        result = subprocess.run(which_cmd, capture_output=True, text=True)
        for path in result.stdout.strip().splitlines():
            path = path.strip()
            if not path:
                continue
            try:
                version_out = subprocess.run(
                    [path, "-version"], capture_output=True, text=True
                )
                if java_version in version_out.stderr:
                    java_home = os.path.dirname(os.path.dirname(path))
                    os.environ["JAVA_HOME"] = java_home
                    os.environ["PATH"] = os.path.dirname(path) + os.pathsep + os.environ["PATH"]
                    print(f"Java {java_version} found: {java_home}", flush=True)
                    return True
            except Exception:
                continue
    except Exception:
        pass

    if not is_windows:
        try:
            result = subprocess.run(
                ["update-alternatives", "--list", "java"],
                capture_output=True, text=True
            )
            for path in result.stdout.strip().splitlines():
                if java_version in path and os.path.exists(path):
                    java_home = os.path.dirname(os.path.dirname(path))
                    os.environ["JAVA_HOME"] = java_home
                    os.environ["PATH"] = os.path.dirname(path) + os.pathsep + os.environ["PATH"]
                    print(f"Java {java_version} found via update-alternatives: {java_home}", flush=True)
                    return True
        except Exception:
            pass

    return False
async def _run() -> None:
    global _semaphore
    _semaphore = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)

    generate_admin_token()

    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGHUP,  _handle_signal)

    if not configure_java():
        import pyspark
        spark_version = tuple(int(x) for x in pyspark.__version__.split(".")[:2])
        java_version = "17" if spark_version >= (3, 3) else "11"
        install_url = f"https://adoptium.net/temurin/releases/?version={java_version}"

        print(f"ERROR: Java {java_version} not found.", flush=True)
        print(f"       Download it from: {install_url}", flush=True)
        if sys.platform != "win32":
            print(f"       Or install via package manager.", flush=True)
        print(f"       Then restart the server.", flush=True)
        sys.exit(1)

    print("Initialising Spark...", flush=True)
    _configure_hadoop()
    print("Hadoop ready.", flush=True)
    from query.engine import _get_spark
    _get_spark() #init
    print("Spark ready.", flush=True)

    registry.scan_downloaded_books()
    print("Registry initialized")   
    server = await asyncio.start_server(_handle_connection, HOST, PORT)
    addrs  = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"LibQuery server listening on {addrs}")
    print(f"Max concurrent queries: {MAX_CONCURRENT_QUERIES}")

    print(f"Server is ready and running!")

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
