"""Model calls made by Flakebait itself (bug writing, issue writing, the LLM judge), not by the agent.

Every call goes through the same meter as agent runs (docker/meter.py), started for the session with its port
published on 127.0.0.1 only. Its log is runs/llm-<purpose>-<timestamp>/meter/meter_log.jsonl, so
harness.study_spend() counts it. A session refuses to start once the study total plus its own cap would pass the
stop (caps.study_stop_usd), and the meter refuses calls beyond the session's cap.

Usage:
    with Session("bugs", usd_cap=1.0) as s:
        text = s.ask(system, user, schema=...)      # schema: JSON schema for structured output (optional)
"""
import json
import os
import time
import urllib.error
import urllib.request

from . import paths
from .harness import CAPS, METER_PORT, PLACEHOLDER_KEY, STUDY, load_api_key, sh, study_spend


class Session:
    def __init__(self, purpose: str, usd_cap: float = 1.0, max_calls: int = 1000,
                 model: str | None = None, effort: str | None = None):
        self.purpose, self.usd_cap, self.max_calls = purpose, usd_cap, max_calls
        self.model = model or STUDY["model"]
        self.effort = effort or STUDY["reasoning_effort"]
        self.dir = paths.RUNS / f"llm-{purpose}-{time.strftime('%Y%m%d-%H%M%S')}"
        self.name = f"fb-llm-meter-{os.getpid()}-{int(time.time())}"
        self.port = 0

    def __enter__(self) -> "Session":
        if not load_api_key():
            raise SystemExit("OPENAI_API_KEY is not set (environment or .env)")
        spent = study_spend()
        if spent + self.usd_cap > CAPS["study_stop_usd"]:
            raise SystemExit(f"study budget: ${spent:.2f} spent, session cap ${self.usd_cap} would pass the stop")
        (self.dir / "meter").mkdir(parents=True, exist_ok=True)
        pr = STUDY["prices"]
        sh(["docker", "run", "-d", "--rm", "--name", self.name, "-p", f"127.0.0.1::{METER_PORT}",
            "-v", f"{paths.ROOT / 'docker' / 'meter.py'}:/meter.py:ro",
            "--mount", f"type=bind,source={self.dir / 'meter'},target=/meter",
            "-e", "OPENAI_API_KEY", "-e", f"TURN_CAP={self.max_calls}", "-e", f"RUN_CAP_USD={self.usd_cap}",
            "-e", f"PRICE_INPUT={pr['input']}", "-e", f"PRICE_CACHED={pr['cached_input']}",
            "-e", f"PRICE_CACHE_WRITE={pr['cache_write']}", "-e", f"PRICE_OUTPUT={pr['output']}",
            "-e", f"LONG_CONTEXT_TOKENS={pr['long_context_tokens']}",
            "-e", f"LONG_CONTEXT_FACTOR_INPUT={pr['long_context_factor_input']}",
            "-e", f"LONG_CONTEXT_FACTOR_OUTPUT={pr['long_context_factor_output']}",
            "fb-base:8", "python3", "-u", "/meter.py", str(METER_PORT)]).check_returncode()
        out = sh(["docker", "port", self.name, str(METER_PORT)]).stdout.strip().splitlines()[0]
        self.port = int(out.rsplit(":", 1)[1])
        log = self.dir / "meter" / "meter_log.jsonl"
        for _ in range(60):     # the meter logs "start" once it listens (Docker's port proxy accepts earlier)
            if log.exists() and '"start"' in log.read_text():
                time.sleep(0.5)
                return self
            time.sleep(0.5)
        sh(["docker", "rm", "-f", self.name])
        raise RuntimeError("meter did not start")

    def __exit__(self, *exc) -> None:
        sh(["docker", "rm", "-f", self.name])

    def ask(self, system: str, user: str, schema: dict | None = None, retries: int = 2) -> str:
        """One Responses API call; returns the output text (JSON text when a schema is given)."""
        body = {"model": self.model, "instructions": system, "input": user,
                "reasoning": {"effort": self.effort}, "store": False}
        if schema:
            body["text"] = {"format": {"type": "json_schema", "name": "out", "schema": schema, "strict": True}}
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/responses", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {PLACEHOLDER_KEY}", "Content-Type": "application/json"})
        for attempt in range(retries + 1):
            try:
                resp = json.loads(urllib.request.urlopen(req, timeout=600).read())
                break
            except urllib.error.HTTPError as e:
                err = e.read().decode(errors="replace")[:300]
                if "flakebait_cap" in err or attempt == retries or e.code < 500:
                    raise RuntimeError(f"model call failed: HTTP {e.code} {err}") from None
                time.sleep(5 * (attempt + 1))
        texts = [c.get("text", "") for item in resp.get("output", []) if item.get("type") == "message"
                 for c in item.get("content", []) if c.get("type") == "output_text"]
        return "".join(texts)

    def ask_json(self, system: str, user: str, schema: dict) -> dict:
        return json.loads(self.ask(system, user, schema))
