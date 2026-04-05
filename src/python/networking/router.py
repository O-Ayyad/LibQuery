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
from typing import Callable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _format_results(rows: list[dict]) -> str:
    if not rows:
        return "Not found."

    lines = []

    is_quran = any(r.get("lang") == "ar" for r in rows)

    if is_quran:
        key = lambda r: (r["chapter"], r["verse"])
        for (chapter, verse), group in groupby(rows, key=key):
            verse_rows = list(group)
            for r in verse_rows:
                if r["lang"] == "ar":
                    lines.append(f"{chapter}:{verse:<3} {r['text']}")
            for r in verse_rows:
                if r["lang"] == "en":
                    lines.append(f"{chapter}:{verse:<3} {r['text']}")
            lines.append("")
    else:
        for r in rows:
            lines.append(f"{r['chapter']}:{r['verse']:<3} {r['text']}")

    return "\n\n".join(lines) if not is_quran else "\n".join(lines)

def handle(payload: dict,  send: Callable[[str], None]) -> str:
    cmd = payload.get("cmd","query")
    flags = payload.get("flags",[])
    match cmd:
        case "close": 
            from networking.server import valid_token, TOKEN_FILE
            good_token = valid_token(payload.get("token",""))
            if(not good_token):
                return (
                    "ERROR: permission denied\n"
                    "       The token sent does not match the one generated at server startup.\n"
                    "       This can happen if:\n"
                    "         - The server was restarted and a new token was generated\n"
                    "         - The token file path does not match between client and server\n"
                    "         - Close command was sent to a non-local server. Fix with <libquery target local>\n"
                    "       Try restarting the client, targeting localhost, or check that admin.token exists."
                )
            try:
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
                    print("Admin token destroyed.", flush=True)
            except Exception as e:
                print(f"WARNING: could not destroy token file: {e}", flush=True)\
                
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
            library = payload.get("library")
            book = payload.get("book")
            try:
                fetch(library, book,send)
                return f"OK: downloaded and ingested {library}/{book or 'all'}"
            except Exception as e:
                return f"ERROR: {e}"
    return f"""ERROR: unknown command '{cmd}' 
            Use Libquery help for commands"""
