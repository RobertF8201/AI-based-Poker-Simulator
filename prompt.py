def get_single_player(
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
):
    return f"""You are a poker decision agent for player: {agent_name}.
Game: No-Limit Texas Hold'em (multiway). Opponents' hole cards are unknown and must be treated as ??.

Current state:
- Street: {street}
- Pot: {pot}
- Community board: {board_txt}
- Table (order & stacks; only YOUR hole is shown):
{others_txt}

Action constraints (VERY IMPORTANT):
- to_call_for_you: {to_call_for_me}
- opened (has bet in this round): {str(opened).lower()}
- last_raise_size (if opened): {last_raise}
- MIN_BET (if no one opened): {min_bet}
- Your stack: {stacks.get(agent_name, 0)}

Output exactly ONE LINE JSON, schema:
{{"action":"check|bet|call|raise|fold","amount":<integer>}}

Rules you MUST follow:
- If to_call_for_you == 0 and not opened: you may "check" or "bet".
* For "bet", amount >= MIN_BET and <= your stack.
- If to_call_for_you > 0 (someone opened): you may "call" / "raise" / "fold".
* Do NOT output "bet" or "check" here.
* For "raise", amount MUST equal your TOTAL chips to put in THIS TURN = to_call_for_you + raise_size,
    where raise_size >= last_raise_size and raise_size <= (your stack - to_call_for_you).
- For "check"/"fold"/"call": set amount = 0.
- No explanations, no extra text. JSON ONLY on one line.

Your hole cards (for YOU only): {hole_txt_me}
Now output your decision JSON:
    """
