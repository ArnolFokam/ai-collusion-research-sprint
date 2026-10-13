import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from harness.config import Config
from harness.runner import run_one


def _cfg(tmp_path, **kw):
    kw = {"n_rounds": 12, "final_window": 6} | kw
    return Config(name="t", out_dir=str(tmp_path), n_runs=1, **kw)


@pytest.mark.parametrize("scenario,expected", [("NASH", 0.0), ("HALF", 0.5), ("MONO", 1.0)])
def test_dry_run_recovers_known_index(tmp_path, scenario, expected):
    cfg = _cfg(tmp_path, dry_run=True, prompts=[scenario])
    run_one(cfg, 0, 0)
    m = json.loads((cfg.run_dir(cfg.conditions()[0], 0) / "metrics.json").read_text())
    assert m["final_price_index"] == pytest.approx(expected, abs=1e-3)
    assert m["n_rounds_completed"] == 12
    from harness.transcript import read
    assert len(list(read(cfg.run_dir(cfg.conditions()[0], 0) / "transcript.jsonl.gz"))) == 24


class _FakeOpenRouter(BaseHTTPRequestHandler):
    calls = 0
    prompts = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).calls += 1
        type(self).prompts.append(body["messages"][-1]["content"])
        if type(self).calls == 7:                      # one HTTP error: must be visible, not hidden by the SDK
            self.send_response(500); self.end_headers(); self.wfile.write(b'{"error":"upstream down"}'); return
        content = json.dumps({"observations": "o", "plans": "hold the price", "insights": "i",
                              "chosen_price": 1.8})
        if type(self).calls == 3:                      # one unparseable reply to exercise our retry
            content = "Sorry, I cannot help with that."
        if type(self).calls == 5:                      # one fenced reply to exercise parsing
            content = "```json\n" + content + "\n```"
        out = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                          "choices": [{"index": 0, "finish_reason": "stop",
                                       "message": {"role": "assistant", "content": content}}],
                          "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(out.encode())

    def log_message(self, *a):
        pass


def test_llm_path_against_mock_openrouter(tmp_path, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _FakeOpenRouter)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    import harness.agent as agent
    monkeypatch.setattr(agent, "OPENROUTER_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setattr(agent.asyncio, "sleep", lambda s: _noop())   # skip backoff waits
    cfg = _cfg(tmp_path, model="test/model", prompts=["P1"], n_rounds=4, final_window=2)
    run_one(cfg, 0, 0)
    srv.shutdown()
    d = cfg.run_dir(cfg.conditions()[0], 0)
    m = json.loads((d / "metrics.json").read_text())
    assert m["n_rounds_completed"] == 4
    assert m["usage"]["Firm A"]["retries"] + m["usage"]["Firm B"]["retries"] == 2
    rounds = [json.loads(l) for l in (d / "rounds.jsonl").read_text().splitlines()]
    assert rounds[0]["agents"]["Firm A"]["plans"] == "hold the price"
    assert any("hold the price" in p for p in _FakeOpenRouter.prompts)   # plans fed back next round
    from harness.transcript import read
    tr = list(read(d / "transcript.jsonl.gz"))
    assert len(tr) == 8 + 2                                  # 4 rounds x 2 agents + 2 failed attempts
    failed = [e for e in tr if e["outcome"] == "error"]
    assert len(failed) == 2
    assert any("Sorry" in json.dumps(e.get("response", "")) for e in failed)        # unparseable reply, raw text kept
    assert any("InternalServerError" in e["error"] for e in failed)                  # HTTP 500 seen, not retried by the SDK
    assert _FakeOpenRouter.calls == 10                                                # server saw exactly our attempts
    first = tr[0]
    assert first["request"]["messages"][0]["role"] == "system" and first["request"]["model"] == "test/model"
    assert first["response"]["usage"]["total_tokens"] == 15 and "Authorization" not in json.dumps(first)
    prov = json.loads((d / "metadata.json").read_text())["provenance"]
    assert prov["python"] and prov["openai"]


async def _noop():
    return None


def test_api_key_loading(tmp_path, monkeypatch):
    from harness.agent import load_api_key
    for n in ("OPENROUTER_API_KEY", "OPEN_ROUTER_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    env = tmp_path / ".env"
    with pytest.raises(RuntimeError):
        load_api_key(env)                                           # nothing anywhere
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-shell")
    assert load_api_key(env) == ("from-shell", "environment:OPENROUTER_API_KEY")
    env.write_text('# comment\nexport OPEN_ROUTER_API_KEY="from-dotenv"\n')
    assert load_api_key(env) == ("from-dotenv", ".env:OPEN_ROUTER_API_KEY")   # .env wins, both spellings work
