#This handles libquery alias command


import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ALIAS_FILE = os.path.join(PROJECT_ROOT, "data", "userdata", "aliases.json")

RESERVED = {"all", "host", "close", "help", "h", "alias", "ping", "download", "add","","restart","target",}


def load() -> dict:
    if not os.path.exists(ALIAS_FILE):
        return {}
    with open(ALIAS_FILE, "r") as f:
        return json.load(f)


def save(aliases: dict) -> None:
    os.makedirs(os.path.dirname(ALIAS_FILE), exist_ok=True)
    with open(ALIAS_FILE, "w") as f:
        json.dump(aliases, f, indent=2)



def cmd_ls() -> str:
    aliases = load()
    if not aliases:
        return "No aliases set."
    return "\n".join(f"{k} -> {v}" for k, v in aliases.items())


def cmd_add(target: str, alias_name: str) -> str:
    if alias_name in RESERVED:
        return f"Error: '{alias_name}' is a reserved name."

    aliases = load()

    if alias_name in aliases:
        return f"Alias '{alias_name}' already exists for '{aliases[alias_name]}'."

    aliases[alias_name] = target
    save(aliases)
    return f"Added alias '{alias_name}' for '{target}'."


def cmd_rm(target: str) -> str:
    aliases = load()

    if target == "all":
        save({})
        return "Removed all aliases."

    if target not in aliases:
        return f"Alias '{target}' not found."

    del aliases[target]
    save(aliases)
    return f"Alias '{target}' removed."


def cmd_resolve(alias_name: str) -> str:
    aliases = load()
    return aliases.get(alias_name, alias_name)  # falls back to original if no alias


# 1 is successful 0 is not
def main() -> int:
    args = sys.argv[1:]

    if not args:
        print("Error: no command provided.", file=sys.stderr)
        return 1

    cmd = args[0].lower()

    if cmd == "ls":
        print(cmd_ls())

    elif cmd == "add":
        if len(args) != 3:
            print("Usage: add <target> <alias>", file=sys.stderr)
            sys.exit(1)
        print(cmd_add(target=args[1], alias_name=args[2]))

    elif cmd == "rm":
        if len(args) != 2:
            print("Usage: rm <alias|all>", file=sys.stderr)
            sys.exit(1)
        print(cmd_rm(args[1]))

    else:
        print(f"Error: unknown command '{cmd}'.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
