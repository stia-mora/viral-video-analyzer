import json, sys, time, urllib.request, websocket, subprocess, os, signal

CHROME_EXE = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
PROFILE = r"C:/Users/Administrator/AppData/Local/Google/Chrome/User Data"
PORT = 9222
OUT = r"E:/Group-projects/douyin-video-to-txt/chrome_youtube_cookies.txt"
TARGETS = ["youtube.com", "google.com", "googlevideo.com", "youtu.be"]

def launch_chrome():
    cmd = [CHROME_EXE, f"--remote-debugging-port={PORT}",
           f'--user-data-dir={PROFILE}', "--no-first-run", "--no-default-browser-check",
           f"--profile-directory=Default", "about:blank"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p

def get_ws():
    for _ in range(30):
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2)
            tabs = json.loads(req.read())
            for t in tabs:
                if t.get("type") == "page" and "webSocketDebuggerUrl" in t:
                    return t["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    return None

def main():
    proc = launch_chrome()
    try:
        ws_url = get_ws()
        if not ws_url:
            print("FAIL: no ws"); sys.exit(1)
        ws = websocket.create_connection(ws_url, timeout=10)
        # Enable network + use Network.getCookies via CDP on a target
        msg_id = 1
        ws.send(json.dumps({"id": msg_id, "method": "Network.enable"}))
        # We need cookies for youtube.com. Use Storage.getCookies (Network domain)
        ws.send(json.dumps({"id": msg_id+1, "method": "Network.getCookies",
                            "params": {"urls": [f"https://{d}" for d in TARGETS]}}))
        cookies = None
        while True:
            raw = ws.recv()
            obj = json.loads(raw)
            if obj.get("id") == msg_id+1:
                cookies = obj.get("result", {}).get("cookies", [])
                break
        ws.close()
        if not cookies:
            print("FAIL: no cookies"); sys.exit(1)
        # Write Netscape format
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in cookies:
                domain = c.get("domain", "")
                # Netscape needs leading dot for host-only vs domain cookies
                if domain.startswith("."):
                    host = "TRUE"
                    dom = domain
                else:
                    host = "FALSE"
                    dom = domain
                path = c.get("path", "/")
                secure = "TRUE" if c.get("secure") else "FALSE"
                expires = c.get("expires", 0)
                if expires is None or expires == 0:
                    expires = 0
                name = c.get("name", "")
                value = c.get("value", "")
                f.write(f"{dom}\t{host}\t{path}\t{secure}\t{int(expires)}\t{name}\t{value}\n")
        print(f"OK: wrote {len(cookies)} cookies to {OUT}")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    main()
