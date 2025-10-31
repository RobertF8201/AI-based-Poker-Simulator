from typing import Dict, List

from entities import Card, fmt_cards
from prompt import get_single_player
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


def agent_policy(
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
