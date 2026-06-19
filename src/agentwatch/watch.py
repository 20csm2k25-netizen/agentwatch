import json
import time
import urllib.request
import urllib.error
from typing import Any


class WatchWrapper:
    def __init__(self, agent: Any, collector_url: str = "http://127.0.0.1:9000/traces"):
        self._agent = agent
        self._collector_url = collector_url

    def _send_trace(self, trace: dict) -> None:
        try:
            data = json.dumps(trace).encode("utf-8")
            req = urllib.request.Request(self._collector_url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
        except Exception:
            # Collector is best-effort; do not raise from tracer
            return

    def invoke(self, payload: Any, *args, **kwargs) -> Any:
        start = time.time()
        trace = {"event": "invoke", "input": payload, "start": start}
        try:
            if hasattr(self._agent, "invoke"):
                result = self._agent.invoke(payload, *args, **kwargs)
            elif callable(self._agent):
                result = self._agent(payload, *args, **kwargs)
            else:
                # Try common run/run_async names
                if hasattr(self._agent, "run"):
                    result = self._agent.run(payload, *args, **kwargs)
                else:
                    raise AttributeError("Wrapped agent has no callable entrypoint")
            trace.update({"end": time.time(), "duration": time.time() - start, "output": result})
            self._send_trace(trace)
            return result
        except Exception as exc:
            trace.update({"end": time.time(), "duration": time.time() - start, "error": str(exc)})
            self._send_trace(trace)
            raise


def watch(agent: Any, collector_url: str = "http://127.0.0.1:9000/traces") -> WatchWrapper:
    """Wrap an agent-like object to capture simple traces and send to a collector.

    The returned object mirrors the original by exposing an `invoke` method
    (or delegating to a callable/`run`). This is intentionally minimal —
    expand with richer trace formats and integrations later.
    """

    return WatchWrapper(agent, collector_url=collector_url)
