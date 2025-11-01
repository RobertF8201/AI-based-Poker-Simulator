import json
import requests
from state import JSON_RE
from typing import Dict, Tuple, Optional


class ChatAnthropic:
    def __init__(
        self,
        model="claude-3-5-sonnet-20241022",
        api_key="sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI",
        base_url="https://yinli.one",
        temperature=0,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    import requests
from typing import Optional

class ChatAnthropic:
    def __init__(self, model: str, api_key: str, base_url: str, temperature: float = 0):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = float(temperature)

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 1500,
        temperature: Optional[float] = None,
        stream: bool = False,
        timeout: int = 120,
    ) -> str:
        """
        Call Anthropic Messages API and return the FULL text (not just first line).
        Accepts optional max_tokens/temperature/stream/timeout to match caller.
        """
        url = f"{self.base_url}/v1/messages"
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = {
            "model": self.model,
            "max_tokens": int(max_tokens),
            "temperature": float(self.temperature if temperature is None else temperature),
            "messages": [{"role": "user", "content": prompt}],
        }

        if stream:
            data["stream"] = True
            with requests.post(url, headers=headers, json=data, timeout=timeout, stream=True) as resp:
                resp.raise_for_status()
                parts = []
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    if raw.startswith("data:"):
                        try:
                            payload = raw[len("data:"):].strip()
                            if payload == "[DONE]":
                                break
                            js = requests.utils.json.loads(payload)
                            if "delta" in js and isinstance(js["delta"], dict):
                                parts.append(js["delta"].get("text", ""))
                            elif "content" in js and isinstance(js["content"], list):
                                parts.append("".join(seg.get("text", "") for seg in js["content"] if isinstance(seg, dict)))
                        except Exception:
                            pass
                return "".join(parts).strip()

        try:
            resp = requests.post(url, headers=headers, json=data, timeout=timeout)
            resp.raise_for_status()
            js = resp.json()

            content = js.get("content", [])
            if isinstance(content, list) and content:
                text = "".join(
                    seg.get("text", "")
                    for seg in content
                    if isinstance(seg, dict)
                )
                return text.strip()

            if "text" in js and isinstance(js["text"], str):
                return js["text"].strip()

            return str(js)

        except Exception as e:
            print(f"API invoke failure: {e}")
            return ""


def parse_agent_action(raw: str) -> Dict:
    if not raw:
        return {"action": "check", "amount": 0}
    raw = raw.strip()
    if raw.startswith("```"):
        parts = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
        raw = " ".join(parts).strip()
    m = JSON_RE.search(raw)
    if m:
        raw = m.group(0)
    try:
        obj = json.loads(raw)
    except Exception:
        return {"action": "check", "amount": 0}
    action = str(obj.get("action", "")).lower().strip()
    try:
        amount = int(obj.get("amount", 0))
    except Exception:
        amount = 0
    return {"action": action, "amount": amount}


def normalize_action_ctx(
    action: str,
    amount: int,
    *,
    to_call: int,
    opened: bool,
    last_raise: int,
    min_bet: int,
    stack: int,
) -> Tuple[str, int, Optional[str]]:
    a = (action or "").lower()
    reason = None

    legal = {"check", "bet", "call", "raise", "fold", "allin", "all-in", "all in"}
    if a not in legal:
        if to_call == 0 and not opened:
            return "check", 0, "illegal->check"
        else:
            if stack >= to_call and to_call > 0:
                return "call", 0, "illegal->call"
            return "fold", 0, "illegal->fold"

    if a in ("allin", "all-in", "all in"):
        return "all-in", stack, None

    if to_call == 0 and not opened:
        if a == "check":
            return "check", 0, None
        if a == "bet":
            amt = max(min_bet, min(amount, stack))
            if amt < min_bet or amt > stack:
                return "check", 0, "bad-bet->check"
            return "bet", amt, None
        return "check", 0, "bad-preflop-action->check"

    if a == "check":
        if stack >= to_call and to_call > 0:
            return "call", 0, "check->call"
        return "fold", 0, "check->fold"

    if a == "bet":
        a = "raise"
        reason = "bet->raise"

    if a == "call":
        return "call", 0, None

    if a == "fold":
        return "fold", 0, None

    if a == "raise":
        max_cap = max(0, stack - to_call)
        raise_amt = amount - to_call
        if raise_amt < last_raise or raise_amt > max_cap:
            if stack >= to_call and to_call > 0:
                return "call", 0, "illegal-raise->call"
            return "fold", 0, "illegal-raise->fold"
        return "raise", amount, reason

    if stack >= to_call and to_call > 0:
        return "call", 0, "fallback->call"
    return "check", 0, "fallback->check"
