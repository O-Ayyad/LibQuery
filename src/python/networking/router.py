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
from itertools import groupby
import networking.registry as registry

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

def handle(payload: dict,  send: Callable[[str], None], ip : str) -> str: #Route the payload to the appropriate function
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
                
            print(f"From {ip}: Server is closing")
            threading.Timer(1, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
            
            return "Server shutdown."
        
        case "ls":
            library = payload.get("library", "").lower().strip()
            registry.scan_downloaded_books()
            
            if not library:
                # No library specified
                lines = []
                for lib, books in registry.LIBRARY_BOOKS.items():
                    done = len(registry.downloaded_books(lib))
                    total = len(books)
                    lines.append(f"{lib}: {done}/{total} downloaded")
                return "\n".join(lines)
            
            elif library not in registry.LIBRARY_BOOKS:
                libs = ", ".join(registry.known_libraries())
                return f"Unknown library '{library}'. Available: {libs}"
            
            else:
                # Known library list all books
                lines = [f"{library}: {len(registry.downloaded_books(library))}/{len(registry.LIBRARY_BOOKS[library])} downloaded", "-" * 40]
                for book in registry.LIBRARY_BOOKS[library]:
                    status = "YES" if registry.is_downloaded(library, book) else "NO "
                    lines.append(f"  {status}  {book}")
                return "\n".join(lines)

        case "ping":
            if("quiet" in flags):
                print(f"From {ip}: Server has been pinged silently")
                return ""
            from config.settings import PORT
            print(f"From {ip}: Server has been pinged")
            return f"Server is online on port: {PORT}"

        case "query":
            from query.engine import execute
            try:
                registry.scan_downloaded_books()
                rows = execute(payload)
                return _format_results(rows)
            except FileNotFoundError as e:
                library = payload.get("library", "").lower().strip()
                if library not in registry.LIBRARY_BOOKS:
                    libs = ", ".join(registry.known_libraries())
                    return f"ERROR: {e}\n\nAvailable libraries: {libs}"
                else:
                    lines = [f"ERROR: {e}", "", 
                             f"{library}: {len(registry.downloaded_books(library))}/{len(registry.LIBRARY_BOOKS[library])} books downloaded", 
                             "-" * 40]
                    for book in registry.LIBRARY_BOOKS[library]:
                        status = "YES" if registry.is_downloaded(library, book) else "NO "
                        lines.append(f"  {status}  {book}")
                    return "\n".join(lines)
            except Exception as e:
                return f"ERROR: query failed : {e}"

        case "download":
            from ingestion.fetch import fetch
            library = payload.get("library")
            book = payload.get("book")
            try:
                saved = fetch(library, book, send)
                if not saved:
                    return f"ERROR: nothing downloaded for {library}/{book or 'all'}\n Library or book may not exist"
                            
                return f"OK: downloaded and ingested {library}/{book or 'all'}"
            except Exception as e:
                return f"ERROR: {e}"
    return f"""ERROR: unknown command '{cmd}' 
            Use Libquery help for commands"""
