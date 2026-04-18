#This handles libquery host command and other networking commands

import json
import os
import sys
import ipaddress

def is_ipv4(s: str) -> bool:
    try:
        ipaddress.IPv4Address(s)
        return True
    except ipaddress.AddressValueError:
        return False
    
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "data", "userdata", "networking_config.json")

def load() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save(configs: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(configs, f, indent=2)

# 1 is successful 0 is not
def main():
    args = sys.argv[1:]
    if not args:

        print("[network_handler] Error: no command provided.", file=sys.stderr)
        return 
    if len(args) > 2:
        print("[network_handler] Error: too many arguments.", file=sys.stderr)
        return
    cmd = args[0].lower()
    if cmd == "target":
        if len(args) == 1:
            config = load()
            current = config.get("target_ip", "127.0.0.1")
            print(f"Current target IP is {current}",file=sys.stderr)
            print(current)
            return 
        ip = args[1].lower()

        if ip in ("rm", "remove"):
            config = load()
            if "target_ip" in config:
                del config["target_ip"]
                save(config)
                print("Target IP removed. Defaulting to 127.0.0.1",file=sys.stderr)
            else:
                print("No target IP was set.")
            return

        elif ip in ("local", "localhost"):
            ip = "127.0.0.1"

        elif not is_ipv4(ip):
            print(
                f"[network_handler] Error: '{ip}' is not a valid IPv4 address. "
                "(format w.x.y.z where w,x,y,z are integers 0–255)",file=sys.stderr)
            return
        
        config = load()
        config["target_ip"] = ip
        save(config)

        print(f"Target IP updated to {ip}",file=sys.stderr)
        return
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return
if __name__ == "__main__":
    main()

