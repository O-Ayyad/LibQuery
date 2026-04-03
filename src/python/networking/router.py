"""
Validates the JSON payload from main.c and routes to query engine or ingestion 

Example payload format from c:
{
    "cmd":           "query" | "download" | "ping" | etc.,
    "library":       "bible",
    "book":          "mark",
    "start_chapter": 4,
    "start_verse":   3,    // -1 = NO_VERSE
    "end_chapter":   4,
    "end_verse":     -1,   // -1 = NO_VERSE
    "lang":          "en"
    "flags": {
        This call hold quiet ping, alias, reader mode, etc.
    }
}
"""

from __future__ import annotations
import os
import sys
import signal
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _format_results(rows: list[dict]) -> str:
    if not rows:
        return "Not found."
    lines = []
    for r in rows:
        lines.append(f"{r['chapter']}:{r['verse']:<3} {r['text']}")
    return "\n\n".join(lines)


def handle(payload: dict) -> str:
    cmd = payload.get("cmd","query")
    flags = payload.get("flags",[])
    match cmd:
        case "close": 
            print("Server is closing")
            threading.Timer(1, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
            return "Server shutdown."
        case "ping":
            if("quiet" in flags):
                print("Server has been pinged silently")
                return ""
            
            from config.settings import PORT
            print("Server has been pinged")
            return f"Server is online on port: {PORT}"

        case "query":
            from query.engine import execute
            try:
                rows = execute(payload)
                return _format_results(rows)
            except FileNotFoundError as e:
                return f"ERROR: {e}"
            except Exception as e:
                return f"ERROR: query failed : {e}"

        case "download":
            from ingestion.fetch import fetch
            from ingestion.ingest import ingest
            library = payload.get("library")
            book = payload.get("book")
            try:
                fetch(library, book)
                ingest(library, book)
                return f"OK: downloaded and ingested {library}/{book or 'all'}"
            except Exception as e:
                return f"ERROR: {e}"
    return f"""ERROR: unknown command '{cmd}' 
            Use Libquery --help for commands"""
