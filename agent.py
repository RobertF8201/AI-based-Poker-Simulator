from typing import Dict, List

from entities import Card, fmt_cards
from prompt import get_single_player, get_report
from pipeline import parse_agent_action, normalize_action_ctx


def build_single_player_prompt(
    agent_name: str,
    street: str,
    holes: Dict[str, List["Card"]],
    board: List["Card"],
    stacks: Dict[str, int],
    pot: int,
    all_player_order: List[str],
    *,
    to_call_for_me: int,
    opened: bool,
    last_raise: int,
    min_bet: int,
) -> str:
    hole_txt_me = (
        fmt_cards(holes.get(agent_name, [])) if holes.get(agent_name) else "(unknown)"
    )
    board_txt = fmt_cards(board) if board else "(no board)"

    lines = []
    for name in all_player_order:
        chips = stacks.get(name, 0)
        if name == agent_name:
            lines.append(f"  - {name}: {chips} chips, hole: {hole_txt_me}")
        else:
            lines.append(f"  - {name}: {chips} chips, hole: ??")

    others_txt = "\n".join(lines) if lines else "(no opponents)"

    prompt = get_single_player(
        agent_name,
        street,
        pot,
        board_txt,
        others_txt,
        to_call_for_me,
        opened,
        last_raise,
        min_bet,
        stacks,
        hole_txt_me,
    )
    return prompt


def player_agent(
    agent_name: str,
    street: str,
    holes: Dict[str, List["Card"]],
    board: List["Card"],
    stacks: Dict[str, int],
    pot: int,
    order: List[str],
    *,
    to_call_for_me: int,
    opened: bool,
    last_raise: int,
    min_bet: int,
    agent_complete,
) -> Dict:

    prompt = build_single_player_prompt(
        agent_name=agent_name,
        street=street,
        holes=holes,
        board=board,
        stacks=stacks,
        pot=pot,
        all_player_order=order,
        to_call_for_me=to_call_for_me,
        opened=opened,
        last_raise=last_raise,
        min_bet=min_bet,
    )

    raw = agent_complete(prompt)
    decision = parse_agent_action(raw)

    action, desired_amt, _ = normalize_action_ctx(
        decision["action"],
        int(decision.get("amount", 0)),
        to_call=to_call_for_me,
        opened=opened,
        last_raise=last_raise,
        min_bet=min_bet,
        stack=stacks.get(agent_name, 0),
    )
    return {"action": action, "amount": desired_amt}

def _extract_text(resp):    # stream return
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        for k in ("text", "content"):
            if k in resp and isinstance(resp[k], str):
                return resp[k]
        if "content" in resp and isinstance(resp["content"], list):
            return "".join(
                (blk.get("text") or "") for blk in resp["content"]
                if isinstance(blk, dict)
            )
        return str(resp)
    if isinstance(resp, (list, tuple)):
        parts = []
        for x in resp:
            if isinstance(x, str):
                parts.append(x)
            elif isinstance(x, dict):
                if "text" in x:
                    parts.append(x["text"])
                elif "delta" in x and isinstance(x["delta"], dict):
                    parts.append(x["delta"].get("text",""))
        return "".join(parts)
    return str(resp)


def expert_agent(agent_complete, jsonl_path="hand_logs.jsonl", stream=False, max_tokens=1800):
    prompt = get_report(jsonl_path)

    prompt += (
        "\n\n---\n"
        "Instructions: Produce the FULL report now. Do not preface with intentions. "
        "Start directly with the required sections and complete all subsections in detail. "
        "Avoid truncation. If necessary, be concise but complete.\n"
    )

    if stream:
        chunks = []
        for chunk in agent_complete(prompt, stream=True, max_tokens=max_tokens):
            text = _extract_text(chunk)
            if text:
                print(text, end="", flush=True)
                chunks.append(text)
        return "".join(chunks)
    else:
        resp = agent_complete(prompt, max_tokens=max_tokens, stream=False)
        return _extract_text(resp)
