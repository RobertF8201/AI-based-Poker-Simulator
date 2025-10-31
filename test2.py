import os, json, requests
from typing import List, Dict, Callable, Tuple, Optional
from holdem import fmt_card, Card, fmt_cards,Player,ask_bet_amount,ask_raise_size,Deck,PokerScoreDetector,fmt_board,showdown,CAT_NAMES_HOLDEM

MIN_BET = 5  # 你的项目里已有就复用

# ============= 你已有的依赖（此处只列名，实际从你项目导入） =============
# from your_project import Deck, Card, Player, PokerScoreDetector, showdown
# from your_project import fmt_cards, fmt_board, CAT_NAMES_HOLDEM
# from your_project import ask_bet_amount, ask_raise_size
# ================================================================


# ------------------ 1) LLM 客户端最小封装（Anthropic 兼容） ------------------
class AnthropicClient:
    """
    极简调用封装。你也可以直接用你现有的 ChatAnthropic 对象：
        llm = ChatAnthropic(model=..., api_key=..., base_url=..., temperature=0)
    然后把 llm.complete(prompt) 作为回调传进来即可。
    """
    def __init__(self, api_key=None, base_url="https://yinli.one", model="claude-3-5-sonnet-20241022", temperature=0):
        self.api_key = "sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI"
        self.model = model
        self.temperature = temperature
        self.base_url = "https://yinli.one"

    def complete(self, prompt: str) -> str:
        """
        返回模型的纯文本输出（期望是一行 JSON）。如果你用自己代理（如 https://yinli.one），
        请改造为那个网关的messages/complete接口即可。
        """
        # 下面是伪/示例实现，你需要根据你的网关契约调整：
        url = f"{self.base_url}/v1/messages"
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        data = {
            "model": self.model,
            "max_tokens": 64,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            js = resp.json()
            # 取第一段文本
            content = js.get("content", [])
            if content and isinstance(content, list):
                txt = "".join([seg.get("text", "") for seg in content if isinstance(seg, dict)])
                return txt.strip()
            return ""
        except Exception as e:
            # 出错返回安全兜底
            return '{"action":"check","amount":0}'


# ------------------ 2) 为“单个 AI”构造安全提示词（只见自家底牌） ------------------
def build_agent_prompt_multi(
    agent_name: str,
    street: str,
    holes: Dict[str, List['Card']],
    board: List['Card'],
    stacks: Dict[str, int],
    pot: int,
    all_player_order: List[str],
    *,
    to_call_for_me: int,
    opened: bool,
    last_raise: int,
    min_bet: int,
) -> str:
    hole_txt_me = fmt_cards(holes.get(agent_name, [])) if holes.get(agent_name) else "(unknown)"
    board_txt = fmt_cards(board) if board else "(no board)"

    lines = []
    for name in all_player_order:
        chips = stacks.get(name, 0)
        if name == agent_name:
            lines.append(f"  - {name}: {chips} chips, hole: {hole_txt_me}")
        else:
            lines.append(f"  - {name}: {chips} chips, hole: ??")

    others_txt = "\n".join(lines) if lines else "(no opponents)"

    prompt = f"""You are a poker decision agent for player: {agent_name}.
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
    return prompt


# ------------------ 3) 解析/调用 LLM ------------------
import re, json
from typing import Dict, Tuple, Optional

_JSON_RE = re.compile(r'\{[^{}]+\}')

def parse_agent_action(raw: str) -> Dict:
    if not raw:
        return {"action": "check", "amount": 0}
    raw = raw.strip()
    if raw.startswith("```"):
        parts = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
        raw = " ".join(parts).strip()
    m = _JSON_RE.search(raw)
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
    stack: int
) -> Tuple[str, int, Optional[str]]:
    a = (action or "").lower()
    reason = None

    legal = {"check","bet","call","raise","fold","allin","all-in","all in"}
    if a not in legal:
        if to_call == 0 and not opened:
            return "check", 0, "illegal->check"
        else:
            if stack >= to_call and to_call > 0:
                return "call", 0, "illegal->call"
            return "fold", 0, "illegal->fold"

    if a in ("allin","all-in","all in"):
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

def agent_policy_multi(
    agent_name: str,
    street: str,
    holes: Dict[str, List['Card']],
    board: List['Card'],
    stacks: Dict[str, int],
    pot: int,
    order: List[str],
    *,
    to_call_for_me: int,
    opened: bool,
    last_raise: int,
    min_bet: int,
    agent_complete,  # Callable[[str], str]
) -> Dict:
    """
    统一：构造带上下文 prompt -> 调 LLM -> 解析 -> 规范化（永不返回非法动作）
    返回 {"action": str, "amount": int}
    """
    prompt = build_agent_prompt_multi(
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

    action, desired_amt, _why = normalize_action_ctx(
        decision["action"], int(decision.get("amount", 0)),
        to_call=to_call_for_me, opened=opened, last_raise=last_raise,
        min_bet=min_bet, stack=stacks.get(agent_name, 0)
    )
    return {"action": action, "amount": desired_amt}

# ------------------ 4) 下注轮：1 人类 + N AI ------------------
def betting_round_human_vs_multi_agents(
    active_players: List['Player'],
    pot: int,
    holes: Dict[str, List['Card']],
    board: List['Card'],
    street: str,
    human_name: str,
    agent_names: List[str],
    agent_complete
):
    contrib = {p.name: 0 for p in active_players}
    opened = False
    last_raise = MIN_BET
    actor = 0
    pending = set(p.name for p in active_players)
    name_order = [p.name for p in active_players]

    MAX_ITER = 600
    loops = 0

    def reset_pending_after_raise(raiser_name: str):
        nonlocal pending
        pending = set(p.name for p in active_players if p.name != raiser_name)

    def stacks_snapshot() -> Dict[str, int]:
        return {p.name: p.money for p in active_players}

    def print_stacks_and_pot():
        items = [f"{p.name}:{p.money}" for p in active_players]
        print("Stacks → " + " | ".join(items) + f" | Pot:{pot}")

    while len(active_players) > 1:
        loops += 1
        if loops > MAX_ITER:
            print("🛑 Safety break: too many iterations, forcing round end.")
            break
        if not pending:
            break
        if actor >= len(active_players):
            actor = 0

        player = active_players[actor]
        name = player.name

        max_in_round = max(contrib[nm] for nm in name_order) if active_players else 0
        to_call = max_in_round - contrib[name]
        stack = player.money

        # ✅ 只在人类回合打印含底牌的提示；Bot 不打印“turn/hold/stack/to_call”
        if name == human_name:
            hole_view = fmt_cards(holes[name])
            print(f"{name} turn, hold[{hole_view}]. To call: {to_call}. Stack: {stack}")

        # 无人可下注 + 未开池 + 无需跟注 → 结束本轮
        if sum(1 for p in active_players if p.money > 0) < 2 and to_call == 0 and not opened:
            print('-----------------------------------------------------------')
            return pot, None

        # ===== 决策（人/机） =====
        if name == human_name:
            if to_call == 0:
                action = input("[check/bet/all-in]: ").strip().lower()
                desired_amt = 0
            else:
                action = input(f"[fold/call/raise/all-in] (must call {to_call} to stay): ").strip().lower()
                desired_amt = 0
        else:
            # —— AI：带上下文 prompt，仅看自己底牌 —— #
            stacks_now = stacks_snapshot()
            decision = agent_policy_multi(
                agent_name=name,
                street=street,
                holes=holes,
                board=board,
                stacks=stacks_now,
                pot=pot,
                order=name_order,
                to_call_for_me=to_call,
                opened=opened,
                last_raise=last_raise,
                min_bet=MIN_BET,
                agent_complete=agent_complete,
            )
            action = decision["action"]
            desired_amt = int(decision.get("amount", 0))

        # ===== 执行动作（Bot 执行后才打印“动作摘要 + 全桌快照”） =====
        if to_call == 0 and not opened:
            if action == "check":
                if name == human_name:
                    print(f"{name} checks.")
                else:
                    print(f"{name} checks.")
                    print_stacks_and_pot()
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

            elif action == "bet":
                amt = desired_amt if name in agent_names else ask_bet_amount(max_amt=stack, min_amt=MIN_BET)
                if amt < MIN_BET or amt > stack:
                    # 人类：提示后重试；Bot：兜底为 check
                    if name == human_name:
                        print("Invalid bet size.")
                        continue
                    else:
                        print(f"{name} Invalid bet size. (auto fallback to check)")
                        print_stacks_and_pot()
                        pending.discard(name)
                        actor = (actor + 1) % len(active_players)
                        continue
                player.money -= amt
                contrib[name] += amt
                pot += amt
                opened = True
                last_raise = amt
                reset_pending_after_raise(name)
                # 摘要输出
                print(f"{name} bets {amt}.")
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            elif action in ("all-in", "allin", "all in"):
                if stack <= 0:
                    if name == human_name:
                        print("You have no chips.")
                    else:
                        print(f"{name} has no chips.")
                        print_stacks_and_pot()
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue
                amt = stack
                player.money = 0
                contrib[name] += amt
                pot += amt
                opened = True
                last_raise = max(last_raise, amt)
                reset_pending_after_raise(name)
                print(f"{name} all-in for {amt}.")
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            else:
                # 任意无效输入 → 兜底 check 并推进
                if name == human_name:
                    print("Invalid input.")
                else:
                    print(f"{name} Invalid input. (auto fallback to check)")
                    print_stacks_and_pot()
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

        else:
            # —— 已开池 —— #
            if action == "fold":
                print(f"{name} folds.")
                if name != human_name:
                    print_stacks_and_pot()
                pending.discard(name)
                del contrib[name]
                active_players.remove(player)
                name_order.remove(name)
                if len(active_players) == 1:
                    return pot, active_players[0]
                if actor >= len(active_players):
                    actor = 0
                continue

            elif action == "call":
                pay = min(to_call, stack)
                player.money -= pay
                contrib[name] += pay
                pot += pay
                print(f"{name} calls {pay}.")
                if name != human_name:
                    print_stacks_and_pot()
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

            elif action == "raise":
                max_raise_cap = max(0, stack - to_call)
                raise_amt = desired_amt - to_call if name in agent_names else ask_raise_size(max_amt=stack - to_call, min_raise=last_raise)
                if raise_amt < last_raise or raise_amt > max_raise_cap:
                    # 兜底 call/fold
                    if stack >= to_call and to_call > 0:
                        pay = to_call
                        player.money -= pay
                        contrib[name] += pay
                        pot += pay
                        print(f"{name} invalid raise -> fallback to call {pay}.")
                        if name != human_name:
                            print_stacks_and_pot()
                        pending.discard(name)
                        actor = (actor + 1) % len(active_players)
                        continue
                    else:
                        print(f"{name} invalid raise -> fallback to fold.")
                        if name != human_name:
                            print_stacks_and_pot()
                        pending.discard(name)
                        del contrib[name]
                        active_players.remove(player)
                        name_order.remove(name)
                        if len(active_players) == 1:
                            return pot, active_players[0]
                        if actor >= len(active_players):
                            actor = 0
                        continue

                pay = to_call + raise_amt
                player.money -= pay
                contrib[name] += pay
                pot += pay
                last_raise = raise_amt
                opened = True
                reset_pending_after_raise(name)
                # “raises to” 打印该玩家当街总投入
                print(f"{name} raises to {contrib[name]}.")
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            elif action in ("all-in", "allin", "all in"):
                if stack <= 0:
                    if name == human_name:
                        print("You have no chips.")
                    else:
                        print(f"{name} has no chips.")
                        print_stacks_and_pot()
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue
                pay = stack
                raise_amt = max(0, pay - to_call)
                player.money = 0
                contrib[name] += pay
                pot += pay
                print(f"{name} all-in for {pay}.")
                if raise_amt >= last_raise and to_call > 0:
                    last_raise = raise_amt
                    opened = True
                    reset_pending_after_raise(name)
                else:
                    pending.discard(name)
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            else:
                # 任意其它无效 → 兜底 call / fold
                if stack >= to_call and to_call > 0:
                    pay = to_call
                    player.money -= pay
                    contrib[name] += pay
                    pot += pay
                    if name == human_name:
                        print(f"{name} Invalid input. (auto fallback to call {pay}).")
                    else:
                        print(f"{name} Invalid input. (auto fallback to call {pay}).")
                        print_stacks_and_pot()
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                else:
                    if name == human_name:
                        print(f"{name} Invalid input. (auto fallback to fold).")
                    else:
                        print(f"{name} Invalid input. (auto fallback to fold).")
                        print_stacks_and_pot()
                    pending.discard(name)
                    del contrib[name]
                    active_players.remove(player)
                    name_order.remove(name)
                    if len(active_players) == 1:
                        return pot, active_players[0]
                    if actor >= len(active_players):
                        actor = 0
                continue

    print('-----------------------------------------------------------')
    return pot, None

from typing import Tuple, Optional


# ------------------ 5) 整手：1 人类 + N AI ------------------
def play_hand_human_vs_multi_agents(
    human_name: str,
    agent_names: List[str],
    players: List['Player'],
    agent_complete,   # Callable[[str], str]
    lowest_rank: int = 2,
    reveal_bots_at_showdown: bool = False,   # 👈 默认不展示 AI 底牌
) -> bool:

    def settle_early(winner, pot) -> bool:
        if winner:
            print(f"{winner.name} win the pot {pot}.")
            winner.money += pot
            return True
        return False

    allow = set([human_name] + list(agent_names))
    active_players = [p for p in players if p.name in allow and p.money > 0]
    if len(active_players) < 2:
        print("player not enough")
        return False

    pot = 0
    for p in list(active_players):
        if p.money > 0:
            ante_amt = min(1, p.money)
            p.money -= ante_amt
            pot += ante_amt

    deck = Deck(lowest_rank=lowest_rank)
    detector = PokerScoreDetector()

    holes: Dict[str, List[Card]] = {p.name: deck.pop_cards(2) for p in active_players}
    board: List[Card] = []

    print(f"Player: {', '.join(p.name for p in active_players)}  | pot: {pot}")
    # ✅ 只展示人类底牌，AI 显示 ?? ??
    for p in active_players:
        if p.name == human_name:
            print(f"{p.name} holes: {fmt_cards(holes[p.name])}")
        else:
            print(f"{p.name} holes: ?? ??")

    # Preflop
    pot, winner = betting_round_human_vs_multi_agents(
        active_players, pot, holes, board, "Preflop",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # Flop
    board += deck.pop_cards(3)
    print("Phase: Flop"); print("Borad: ", fmt_board(board))
    pot, winner = betting_round_human_vs_multi_agents(
        active_players, pot, holes, board, "Flop",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # Turn
    board += deck.pop_cards(1)
    print("Phase: Turn"); print("Borad: ", fmt_board(board))
    pot, winner = betting_round_human_vs_multi_agents(
        active_players, pot, holes, board, "Turn",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # River
    board += deck.pop_cards(1)
    print("Phase: River"); print("Borad: ", fmt_board(board))
    pot, winner = betting_round_human_vs_multi_agents(
        active_players, pot, holes, board, "River",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # —— showdown ——（不泄露 AI 底牌）
    print("—— showdown ——")
    for p in active_players:
        if p.name == human_name or reveal_bots_at_showdown:
            print(f"{p.name} holes: {fmt_cards(holes[p.name])}")
        else:
            print(f"{p.name} holes: ?? ??")
    print("Board: ", fmt_board(board))

    winners, scores = showdown(detector, active_players, holes, board)
    for p in active_players:
        s = scores[p.name]
        print(f"{p.name} category: {CAT_NAMES_HOLDEM[s.category]}")

    if len(winners) == 1:
        w = winners[0]
        print(f"{w.name} win, get pot {pot}.")
        w.money += pot
    else:
        split = pot // len(winners)
        remainder = pot - split * len(winners)
        names = ", ".join(p.name for p in winners)
        print(f"Share pot: {names} get {split}" + (f", reminder {remainder} to first {winners[0].name}" if remainder else ""))
        for i, w in enumerate(winners):
            w.money += split + (remainder if i == 0 else 0)

    return True
