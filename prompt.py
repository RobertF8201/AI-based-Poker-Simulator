import json


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


def get_report(jsonl_path: str = "hand_logs.jsonl") -> str:
    """
    Generate an expert-level poker hand review prompt.
    It reads the most recent hand record from a JSONL file
    and injects it into the prompt template.

    Args:
        jsonl_path (str): Path to the JSONL file storing all hands.

    Returns:
        str: The formatted prompt ready to send to an AI agent.
    """
    # --- Step 1: Read the latest line (latest hand record) ---
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            last_line = None
            for line in f:
                if line.strip():
                    last_line = line.strip()
        if last_line is None:
            raise ValueError("No valid hand records found in JSONL file.")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {jsonl_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to read last hand from {jsonl_path}: {e}")

    # --- Step 2: Validate that it’s valid JSON ---
    try:
        json_obj = json.loads(last_line)
        formatted_json = json.dumps(json_obj, ensure_ascii=False)
    except json.JSONDecodeError:
        raise ValueError("Last line in JSONL is not valid JSON.")

    # --- Step 3: Inject into prompt template ---
    prompt = f"""You are a professional No-Limit Texas Hold’em coach and solver operator. 
Please provide a full expert-level hand review based on the following hand record.

🎯 Objectives:
1. Review each street (Preflop, Flop, Turn, River) and evaluate every decision for optimality—both from a GTO and exploitative standpoint.  
2. Quantify key metrics: SPR, pot odds, required equity, minimum defense frequency (MDF, if applicable), bet sizing, and range coverage.  
3. Estimate the equity (win probability) for the hero at each critical decision point using public cards and hole cards (Monte Carlo or approximate calculation if needed).  
4. Identify alternative actions or better lines with reasoning based on range advantage, blockers, board texture, stack-to-pot ratio, position, and opponent tendencies.  
5. Give an overall score for the Hero’s play (0–100), and street-by-street sub-scores.  
6. Point out any inconsistencies or missing data in the hand log, and clearly state assumptions.

🧠 Context:
- This is a standard No-Limit Texas Hold’em game with integer chip units.
- At showdown, all remaining players reveal their cards.
- Use GTO theory as a baseline but discuss practical adjustments for multiway pots (e.g., lower bluff frequencies, tighter ranges).
- For each call decision, compute pot odds and required equity:  
  Required Equity = ToCall / (Pot + ToCall) × 100%  
  Then evaluate if calling meets or fails profitability thresholds.

📥 Input (JSON Hand Record):
{formatted_json}

📤 Expected Output Format:
1. **Overview**
   - Hand ID  
   - Overall Score (0–100)  
   - One-sentence summary of Hero’s performance  

2. **Quantitative Table (Markdown)**  
   | Street | Player | Action | Pot Size | Effective Stack | SPR | To Call | Pot Odds | Required Equity (%) | Estimated Equity (%) | Recommended Line / Frequency |
   |---------|---------|--------|-----------|------------------|-----|----------|-----------|----------------------|----------------------|-------------------------------|

3. **Street-by-Street Analysis**
   - **Preflop**  
   - **Flop**  
   - **Turn**  
   - **River**

4. **Equity & Probabilities**

5. **Strategic Recommendations**

6. **Notes / Assumptions**
"""
    return prompt
