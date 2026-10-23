"""Metering reverse proxy between the agent and the OpenAI API (one per run; stdlib only).

The agent's Codex CLI uses http://fb-meter:8080/v1 as its OpenAI base URL. The meter
  - forwards each request to https://api.openai.com, replacing the agent's placeholder key with the real one
    (so the real key never enters the agent's container);
  - refuses a model call once the run has made TURN_CAP model calls or spent RUN_CAP_USD (the turn and dollar
    caps; Codex has no turn limit of its own);
  - reads token usage from every response (streamed or not), prices it, and appends one line per request to
    /meter/meter_log.jsonl, which is outside the agent's container.

Environment: OPENAI_API_KEY, TURN_CAP, RUN_CAP_USD, PRICE_INPUT, PRICE_CACHED, PRICE_OUTPUT (USD per 1M tokens),
LONG_CONTEXT_TOKENS, LONG_CONTEXT_FACTOR_INPUT, LONG_CONTEXT_FACTOR_OUTPUT.
Usage: python3 -u meter.py 8080
"""
import http.client
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "api.openai.com"
LOG = "/meter/meter_log.jsonl"
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "authorization", "accept-encoding", "content-length"}

KEY = os.environ["OPENAI_API_KEY"]
TURN_CAP = int(os.environ.get("TURN_CAP", "30"))
RUN_CAP_USD = float(os.environ.get("RUN_CAP_USD", "1.0"))
P_IN = float(os.environ["PRICE_INPUT"]) / 1e6
P_CACHED = float(os.environ["PRICE_CACHED"]) / 1e6
P_WRITE = float(os.environ.get("PRICE_CACHE_WRITE", os.environ["PRICE_INPUT"])) / 1e6
P_OUT = float(os.environ["PRICE_OUTPUT"]) / 1e6
LONG = int(os.environ.get("LONG_CONTEXT_TOKENS", "272000"))
LONG_IN = float(os.environ.get("LONG_CONTEXT_FACTOR_INPUT", "2.0"))
LONG_OUT = float(os.environ.get("LONG_CONTEXT_FACTOR_OUTPUT", "1.5"))

state = {"calls": 0, "usd": 0.0, "refused": 0}
lock = threading.Lock()


def cost(u: dict) -> float:
    inp = int(u.get("input_tokens") or 0)
    det = u.get("input_tokens_details") or {}
    cached = int(det.get("cached_tokens") or 0)
    write = int(det.get("cache_write_tokens") or 0)
    out = int(u.get("output_tokens") or 0)    # includes reasoning tokens
    fi, fo = (LONG_IN, LONG_OUT) if inp > LONG else (1.0, 1.0)
    plain = max(inp - cached - write, 0)
    return (plain * P_IN + write * P_WRITE + cached * P_CACHED) * fi + out * P_OUT * fo


def log(rec: dict) -> None:
    with lock, open(LOG, "a") as f:
        f.write(json.dumps({"t": round(time.time(), 3), **rec}) + "\n")


def find_usage(obj):
    """The usage object of a Responses (or Chat Completions) payload, wherever it sits."""
    if isinstance(obj, dict):
        if isinstance(obj.get("usage"), dict) and "input_tokens" in obj["usage"]:
            return obj["usage"]
        if isinstance(obj.get("usage"), dict) and "prompt_tokens" in obj["usage"]:
            u = obj["usage"]
            return {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0),
                    "input_tokens_details": {"cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)}}
        for v in obj.values():
            r = find_usage(v)
            if r:
                return r
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _refuse(self, why: str) -> None:
        body = json.dumps({"error": {"message": f"Request refused: {why}.", "type": "invalid_request_error",
                                     "code": "flakebait_cap"}}).encode()
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forward(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        model_call = self.command == "POST" and self.path.rstrip("/").endswith(("/responses", "/chat/completions"))
        if model_call:
            with lock:
                over = ("turn cap" if state["calls"] >= TURN_CAP else
                        "spending cap" if state["usd"] >= RUN_CAP_USD else None)
                if over:
                    state["refused"] += 1
                else:
                    state["calls"] += 1
                call = state["calls"]
            if over:
                log({"path": self.path, "refused": over, "calls": call})
                self._refuse(over)
                return
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        headers.update({"Host": UPSTREAM, "Authorization": f"Bearer {KEY}", "Accept-Encoding": "identity"})
        if body is not None:
            headers["Content-Length"] = str(len(body))
        start = time.time()
        conn = http.client.HTTPSConnection(UPSTREAM, timeout=600)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
        except Exception as e:
            log({"path": self.path, "error": f"{type(e).__name__}: {e}"})
            self.send_error(502)
            return
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        usage, buf, tail = None, b"", b""
        while True:
            chunk = resp.read1(65536)
            if not chunk:
                break
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
            buf += chunk
            # SSE: look at complete "data:" lines as they arrive; a non-streamed JSON body is parsed at the end.
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.startswith(b"data:") and b'"usage"' in line:
                    try:
                        usage = find_usage(json.loads(line[5:].strip())) or usage
                    except ValueError:
                        pass
                elif not line.startswith(b"data:") and not line.startswith(b"event:"):
                    tail += line + b"\n"
        tail += buf
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        if usage is None and tail.strip():
            try:
                usage = find_usage(json.loads(tail))
            except ValueError:
                pass
        usd = cost(usage) if usage else 0.0
        with lock:
            state["usd"] += usd
            total = state["usd"]
        log({"path": self.path, "method": self.command, "status": resp.status, "model_call": model_call,
             "call": call if model_call else None, "usage": usage, "usd": round(usd, 6),
             "run_usd": round(total, 6), "seconds": round(time.time() - start, 2)})

    do_POST = do_GET = do_DELETE = do_PUT = _forward


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    log({"event": "start", "turn_cap": TURN_CAP, "run_cap_usd": RUN_CAP_USD,
         "prices_per_1m": [P_IN * 1e6, P_CACHED * 1e6, P_OUT * 1e6]})
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
