
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Texas Hold'em CLI（支持多次加注 / re-raise）
Heads-up 对战机器人 | No-Limit（带最小下注与最小加注规则）

关键特性：
- 你可在任一街发起 bet/raise，并在对手 raise 后继续 re-raise（多次加注）。
- 规则（简化 No-Limit）：
  * 最小下注额 MIN_BET = 5；
  * 发起下注（bet）时，金额 >= MIN_BET；
  * 最小加注（raise_size）必须 >= 上一次加注幅度（last_raise），若全下但不足最小加注，按**跟注**处理（不重开行动）。
- 单挑、四个街次：Preflop / Flop / Turn / River；7选5判定胜负。

运行：
    python cli_texas_holdem_reraise.py
"""

import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

# -------------------------
# 基础牌面
# -------------------------

class Card:
    RANKS = {2:"2",3:"3",4:"4",5:"5",6:"6",7:"7",8:"8",9:"9",10:"10",11:"J",12:"Q",13:"K",14:"A"}
    SUITS = {0:"♠",1:"♣",2:"♦",3:"♥"}
    def __init__(self, rank: int, suit: int):
        if rank not in Card.RANKS or suit not in Card.SUITS:
            raise ValueError("Invalid card")
        self._value = (rank << 2) + suit
    @property
    def rank(self): return self._value >> 2
    @property
    def suit(self): return self._value & 3
    def __int__(self): return self._value
    def __lt__(self, other): return int(self) < int(other)
    def __repr__(self): return f"{Card.RANKS[self.rank]}{Card.SUITS[self.suit]}"

class Deck:
    def __init__(self, lowest_rank: int = 2):
        self._cards = [Card(r,s) for r in range(lowest_rank,15) for s in range(4)]
        self._discard = []
        random.shuffle(self._cards)
    def pop_cards(self, n=1):
        out = []
        while n>0:
            if not self._cards:
                self._cards, self._discard = self._discard, []
                random.shuffle(self._cards)
            out.append(self._cards.pop())
            n -= 1
        return out
    def push_cards(self, disc: List[Card]):
        self._discard += disc

# -------------------------
# 牌力评估（传统 7 选 5）
# -------------------------

class CardsHelper:
    def __init__(self, cards: List[Card], lowest_rank=2):
        self._sorted = sorted(cards, key=int, reverse=True)
        self._lowest_rank = lowest_rank
    def _group_by_ranks(self):
        d: Dict[int, List[Card]] = {}
        for c in self._sorted: d.setdefault(c.rank, []).append(c)
        return d
    def _x_sorted_list(self, x: int):
        groups = [lst for lst in self._group_by_ranks().values() if len(lst)==x]
        groups.sort(key=lambda g: g[0].rank, reverse=True)
        return groups
    def _get_straight(self, sorted_cards: List[Card]):
        if len(sorted_cards)<5: return None
        uniq, seen = [], set()
        for c in sorted_cards:
            if c.rank not in seen:
                uniq.append(c); seen.add(c.rank)
        if not uniq: return None
        straight = [uniq[0]]
        for i in range(1,len(uniq)):
            if uniq[i].rank == uniq[i-1].rank-1:
                straight.append(uniq[i])
                if len(straight)==5: return straight
            else:
                straight = [uniq[i]]
        ranks = [c.rank for c in uniq]
        if 14 in ranks and {2,3,4,5}.issubset(ranks):
            seq, need = [], {5,4,3,2}
            for c in uniq:
                if c.rank in need:
                    seq.append(c); need.remove(c.rank)
                    if not need: break
            a = next((c for c in uniq if c.rank==14), None)
            if a: seq.append(a); return seq
        return None
    def _merge(self, score_cards: List[Card]):
        return score_cards + [c for c in self._sorted if c not in score_cards]
    def straight_flush(self):
        suits: Dict[int, List[Card]] = {}
        for c in self._sorted: suits.setdefault(c.suit, []).append(c)
        for s_cards in suits.values():
            if len(s_cards)>=5:
                st = self._get_straight(s_cards)
                if st: return st
        return None
    def quads(self):
        q = self._x_sorted_list(4); return (self._merge(q[0])[:5]) if q else None
    def flush(self):
        suits: Dict[int, List[Card]] = {}
        for c in self._sorted: suits.setdefault(c.suit, []).append(c)
        for s_cards in suits.values():
            if len(s_cards)>=5: return s_cards[:5]
        return None
    def full_house(self):
        trips = self._x_sorted_list(3); pairs = self._x_sorted_list(2)
        if trips and (len(trips)>=2 or pairs):
            if len(trips)>=2: return (self._merge(trips[0]+trips[1][:2])[:5])
            return (self._merge(trips[0]+pairs[0])[:5])
        return None
    def straight(self): return self._get_straight(self._sorted)
    def trips(self):
        t = self._x_sorted_list(3); return (self._merge(t[0])[:5]) if t else None
    def two_pair(self):
        p = self._x_sorted_list(2); return (self._merge(p[0]+p[1])[:5]) if len(p)>=2 else None
    def pair(self):
        p = self._x_sorted_list(2); return (self._merge(p[0])[:5]) if p else None
    def no_pair(self): return self._sorted[:5]

class Score:
    NO_PAIR, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FULL_HOUSE, FLUSH, QUADS, STRAIGHT_FLUSH = range(9)
    def __init__(self, category: int, cards: List[Card]): self.category, self.cards = category, cards
    @property
    def strength(self):
        s = self.category
        for i in range(5):
            s <<= 4; s += self.cards[i].rank if i < len(self.cards) else 0
        for i in range(5):
            s <<= 2; s += self.cards[i].suit if i < len(self.cards) else 0
        return s
    def cmp(self, other:"Score"):
        if self.category==Score.STRAIGHT_FLUSH:
            if self.cards[0].rank==14 and other.cards[-1].rank==14: return -1
            if self.cards[-1].rank==14 and other.cards[0].rank==14: return 1
        return (self.strength>other.strength) - (self.strength<other.strength)

class TraditionalPokerScoreDetector:
    def __init__(self, lowest_rank=2): self._lowest_rank=lowest_rank
    def get_score(self, cards: List[Card]) -> Score:
        ch = CardsHelper(cards, self._lowest_rank)
        for cat, fn in [(Score.STRAIGHT_FLUSH,ch.straight_flush),
                        (Score.QUADS,ch.quads),
                        (Score.FLUSH,ch.flush),
                        (Score.FULL_HOUSE,ch.full_house),
                        (Score.STRAIGHT,ch.straight),
                        (Score.TRIPS,ch.trips),
                        (Score.TWO_PAIR,ch.two_pair),
                        (Score.PAIR,ch.pair),
                        (Score.NO_PAIR,ch.no_pair)]:
            res = fn()
            if res: return Score(cat,res)
        raise RuntimeError("score fail")

# -------------------------
# 显示/实体
# -------------------------

@dataclass
class SimplePlayer:
    name: str
    money: int

CAT_NAMES = {
    Score.NO_PAIR:"高牌", Score.PAIR:"一对", Score.TWO_PAIR:"两对", Score.TRIPS:"三条",
    Score.STRAIGHT:"顺子", Score.FULL_HOUSE:"葫芦", Score.FLUSH:"同花",
    Score.QUADS:"四条", Score.STRAIGHT_FLUSH:"同花顺",
}

def fmt_card(c: Card): return f"{Card.RANKS[c.rank]}{Card.SUITS[c.suit]}"
def fmt_cards(cs: List[Card]): return " ".join(fmt_card(c) for c in sorted(cs, key=int, reverse=True))

def print_state(p_you: SimplePlayer, p_bot: SimplePlayer, pot: int, street: str):
    print(f"[{street}] 你的筹码: {p_you.money} | 机器人: {p_bot.money} | 彩池: {pot}")

# -------------------------
# 下注与加注（支持多次加注）
# -------------------------

MIN_BET = 5
ANTE = 1

def ask_int(prompt: str) -> Optional[int]:
    s = input(prompt).strip()
    if s == "": return None
    if s.isdigit(): return int(s)
    try: return int(s)
    except: return None

def ask_bet_amount(max_amt: int, min_amt: int = MIN_BET) -> int:
    while True:
        v = ask_int(f"请输入下注额（{min_amt} ~ {max_amt}）：")
        if v is None: print("请输入整数金额。"); continue
        if v < min_amt: print(f"不能低于最小下注额 {min_amt}。"); continue
        if v > max_amt: print(f"不能超过你剩余筹码 {max_amt}。"); continue
        return v

def ask_raise_size(max_amt: int, min_raise: int) -> int:
    while True:
        v = ask_int(f"请输入加注幅度（不含跟注部分），至少 {min_raise}，最多 {max_amt}：")
        if v is None: print("请输入整数金额。"); continue
        if v < min_raise: print(f"加注幅度不能小于 {min_raise}。"); continue
        if v > max_amt: print(f"不能超过你剩余筹码 {max_amt}。"); continue
        return v

def bot_decide_action(to_call: int, last_raise: int, bot: SimplePlayer, score: Score) -> Tuple[str, int]:
    """
    返回 (action, amount)
    action: 'check' | 'bet' | 'call' | 'raise' | 'fold'
    amount: 对于 bet 是下注额；对于 call 是补齐额；对于 raise 是加注幅度（不含跟注）；check/fold 为 0
    简单策略：
      - 若 to_call==0：
           * TRIPS+ -> bet 2*MIN_BET（若可）
           * PAIR   -> bet MIN_BET（若可）
           * 否则 check
      - 若 to_call>0：
           * TRIPS+ -> 若资金允许，raise（幅度=max(last_raise, MIN_BET)）；否则 call
           * PAIR   -> 若 to_call <= 2*MIN_BET 则 call，否则 fold
           * 否则   -> 若 to_call <= MIN_BET 则勉强 call，否则 fold
    """
    stack = bot.money
    if to_call == 0:
        if score.category >= Score.TRIPS:
            bet_amt = min(stack, MIN_BET * 2)
            return ("bet", bet_amt) if bet_amt >= MIN_BET else ("check", 0)
        if score.category >= Score.PAIR:
            bet_amt = min(stack, MIN_BET)
            return ("bet", bet_amt) if bet_amt >= MIN_BET else ("check", 0)
        return "check", 0
    else:
        if score.category >= Score.TRIPS:
            min_raise = max(last_raise, MIN_BET)
            if stack > to_call + min_raise:
                raise_size = min(stack - to_call, min_raise * 2)  # 保守再加注
                return "raise", max(min_raise, raise_size)
            if stack >= to_call:
                return "call", to_call
            return "fold", 0
        if score.category >= Score.PAIR:
            if to_call <= 2 * MIN_BET and stack >= to_call:
                return "call", to_call
            return "fold", 0
        else:
            if to_call <= MIN_BET and stack >= to_call:
                return "call", to_call
            return "fold", 0

def betting_round(p_you: SimplePlayer, p_bot: SimplePlayer, detector, your_hole: List[Card], bot_hole: List[Card], board: List[Card], pot: int, street: str) -> Tuple[int, Optional[str]]:
    """
    多次加注循环直至：
      - 有人弃牌；或
      - 最近一次进攻被跟注（所有人金额持平）。
    行动顺序：你先行动。
    """
    contrib = {"you": 0, "bot": 0}
    opened = False
    last_raise = 0  # 最近一次“加注幅度”
    last_aggressor: Optional[str] = None
    last_action = None
    consecutive_checks = 0
    actor = "you"

    def to_call_of(who: str) -> int:
        me = contrib[who]
        opp = contrib["bot" if who=="you" else "you"]
        return max(opp - me, 0)

    def stack_of(who: str) -> int:
        return p_you.money if who=="you" else p_bot.money

    while True:
        print_state(p_you, p_bot, pot, street)
        print(f"公共牌：{fmt_cards(board)}" if board else "（当前为翻牌前）")
        if actor == "you":
            need = to_call_of("you")
            stack = stack_of("you")
            if need == 0 and not opened:
                # 你可 check 或 bet
                s = input("你的操作 [check/c, bet/b]: ").strip().lower()
                if s in ("check","c"):
                    print("你过牌。")
                    consecutive_checks += 1
                    if consecutive_checks >= 2:
                        # 两人连续 check，轮结束
                        return pot, None
                    actor = "bot"
                    last_action = "check"
                    continue
                elif s in ("bet","b"):
                    if stack < MIN_BET:
                        print("你筹码不足以下注，自动 check。")
                        consecutive_checks += 1
                        actor = "bot"
                        last_action = "check"
                        continue
                    amt = ask_bet_amount(max_amt=stack, min_amt=MIN_BET)
                    p_you.money -= amt; contrib["you"] += amt; pot += amt
                    opened = True
                    last_raise = amt  # 开局下注的“加注幅度” = 下注额
                    last_aggressor = "you"
                    last_action = "bet"
                    consecutive_checks = 0
                    actor = "bot"
                    continue
                else:
                    print("无效输入，请重试。")
                    continue
            else:
                # 你需要面对下注：可 fold / call / raise
                need = to_call_of("you")
                stack = stack_of("you")
                print(f"当前需跟注：{need}。你的筹码：{stack}。")
                s = input("你的操作 [call, raise/r, fold/f]: ").strip().lower()
                if s in ("fold","f"):
                    print("你弃牌。"); return pot, "bot"
                elif s == "call":
                    pay = min(need, stack)
                    p_you.money -= pay; contrib["you"] += pay; pot += pay
                    print(f"你跟注 {pay}。")
                    if contrib["you"] == contrib["bot"]:
                        # 被跟注，轮结束
                        return pot, None
                    actor = "bot"
                    last_action = "call"
                    continue
                elif s in ("raise","r"):
                    min_raise = max(last_raise, MIN_BET)
                    max_raise = max(0, stack - need)
                    if max_raise <= 0:
                        print("你没有足够筹码进行加注，自动 call（或 all-in）。")
                        pay = min(need, stack)
                        p_you.money -= pay; contrib["you"] += pay; pot += pay
                        if contrib["you"] == contrib["bot"]: return pot, None
                        actor = "bot"; last_action = "call"; continue
                    raise_size = ask_raise_size(max_amt=max_raise, min_raise=min_raise)
                    pay = need + raise_size
                    p_you.money -= pay; contrib["you"] += pay; pot += pay
                    last_raise = raise_size
                    last_aggressor = "you"
                    last_action = "raise"
                    actor = "bot"
                    continue
                else:
                    print("无效输入，请重试。")
                    continue
        else:
            # 机器人行动
            need = to_call_of("bot")
            stack = stack_of("bot")
            bot_score = detector.get_score(bot_hole + board) if board else detector.get_score(bot_hole)
            act, val = bot_decide_action(need, last_raise, p_bot, bot_score)
            if need == 0 and not opened:
                if act == "bet":
                    amt = min(stack, max(val, MIN_BET))
                    p_bot.money -= amt; contrib["bot"] += amt; pot += amt
                    opened = True; last_raise = amt; last_aggressor = "bot"
                    print(f"机器人下注 {amt}。")
                    consecutive_checks = 0; last_action = "bet"; actor = "you"; continue
                else:
                    print("机器人过牌。")
                    consecutive_checks += 1
                    if consecutive_checks >= 2:
                        return pot, None
                    last_action = "check"; actor = "you"; continue
            else:
                if act == "fold":
                    print("机器人弃牌。"); return pot, "you"
                elif act == "call":
                    pay = min(need, stack)
                    p_bot.money -= pay; contrib["bot"] += pay; pot += pay
                    print(f"机器人跟注 {pay}。")
                    if contrib["you"] == contrib["bot"]:
                        return pot, None
                    last_action = "call"; actor = "you"; continue
                elif act == "raise":
                    min_raise = max(last_raise, MIN_BET)
                    max_rsize = max(0, stack - need)
                    if max_rsize < min_raise:
                        # 资金不足，按 call 处理
                        pay = min(need, stack)
                        p_bot.money -= pay; contrib["bot"] += pay; pot += pay
                        print(f"机器人筹码不足以有效加注，改为跟注 {pay}。")
                        if contrib["you"] == contrib["bot"]:
                            return pot, None
                        last_action = "call"; actor = "you"; continue
                    raise_size = min(val, max_rsize)
                    raise_size = max(raise_size, min_raise)
                    pay = need + raise_size
                    p_bot.money -= pay; contrib["bot"] += pay; pot += pay
                    last_raise = raise_size; last_aggressor = "bot"
                    print(f"机器人加注，幅度 {raise_size}（总投入增加 {pay}）。")
                    last_action = "raise"; actor = "you"; continue

# -------------------------
# 局面推进与摊牌
# -------------------------

def showdown(detector, your_hole, bot_hole, board):
    your_score = detector.get_score(your_hole + board)
    bot_score = detector.get_score(bot_hole + board)
    cmp_res = your_score.cmp(bot_score)
    if cmp_res>0: return 1, "you", your_score, bot_score
    if cmp_res<0: return -1, "bot", your_score, bot_score
    return 0, "split", your_score, bot_score

def fmt_board(board: List[Card]) -> str:
    return fmt_cards(board) if board else "(无)"

def play_hand(p_you: SimplePlayer, p_bot: SimplePlayer, lowest_rank: int = 2) -> bool:
    pot = 0
    for p in (p_you, p_bot):
        if p.money <= 0:
            print(f"{p.name} 已无筹码。"); return False
        ante_amt = min(1, p.money); p.money -= ante_amt; pot += ante_amt

    deck = Deck(lowest_rank=lowest_rank)
    detector = TraditionalPokerScoreDetector(lowest_rank)
    your_hole = deck.pop_cards(2)
    bot_hole = deck.pop_cards(2)
    board: List[Card] = []

    print("===== 新手开始 =====")
    print_state(p_you, p_bot, pot, "Preflop")
    print("你的手牌：", fmt_cards(your_hole))

    # Preflop
    pot, winner = betting_round(p_you, p_bot, detector, your_hole, bot_hole, board, pot, "Preflop")
    if winner:
        if winner=="you": print(f"机器人弃牌。你获胜，收入彩池 {pot}。"); p_you.money += pot
        else: print(f"你弃牌。机器获胜，收入彩池 {pot}。"); p_bot.money += pot
        return True

    # Flop
    board += deck.pop_cards(3)
    print_state(p_you, p_bot, pot, "Flop")
    print("公共牌：", fmt_cards(board))
    pot, winner = betting_round(p_you, p_bot, detector, your_hole, bot_hole, board, pot, "Flop")
    if winner:
        if winner=="you": print(f"机器人弃牌。你获胜，收入彩池 {pot}。"); p_you.money += pot
        else: print(f"你弃牌。机器获胜，收入彩池 {pot}。"); p_bot.money += pot
        return True

    # Turn
    board += deck.pop_cards(1)
    print_state(p_you, p_bot, pot, "Turn")
    print("公共牌：", fmt_cards(board))
    pot, winner = betting_round(p_you, p_bot, detector, your_hole, bot_hole, board, pot, "Turn")
    if winner:
        if winner=="you": print(f"机器人弃牌。你获胜，收入彩池 {pot}。"); p_you.money += pot
        else: print(f"你弃牌。机器获胜，收入彩池 {pot}。"); p_bot.money += pot
        return True

    # River
    board += deck.pop_cards(1)
    print_state(p_you, p_bot, pot, "River")
    print("公共牌：", fmt_cards(board))
    pot, winner = betting_round(p_you, p_bot, detector, your_hole, bot_hole, board, pot, "River")
    if winner:
        if winner=="you": print(f"机器人弃牌。你获胜，收入彩池 {pot}。"); p_you.money += pot
        else: print(f"你弃牌。机器获胜，收入彩池 {pot}。"); p_bot.money += pot
        return True

    # 摊牌
    print("—— 摊牌 ——")
    print("你的手牌：", fmt_cards(your_hole))
    print("机器人的手牌：", fmt_cards(bot_hole))
    print("公共牌：", fmt_cards(board))

    _, who, your_score, bot_score = showdown(detector, your_hole, bot_hole, board)
    print(f"你的牌型：{CAT_NAMES[your_score.category]}")
    print(f"机器人的牌型：{CAT_NAMES[bot_score.category]}")

    if who == "you":
        print(f"你赢了！获得彩池 {pot}。"); p_you.money += pot
    elif who == "bot":
        print(f"机器人赢了！获得彩池 {pot}。"); p_bot.money += pot
    else:
        split = round(pot / 2)
        print(f"平局，彩池平分：各 {split}。")
        p_you.money += split; p_bot.money += pot - split

    return True

# -------------------------
# 主程序
# -------------------------

def main():
    print("===== Texas Hold'em（支持多次加注 / re-raise）命令行对战 =====")
    p_you = SimplePlayer(name="你", money=100)
    p_bot = SimplePlayer(name="机器人", money=100)
    lowest_rank = 2

    while p_you.money>0 and p_bot.money>0:
        ok = play_hand(p_you, p_bot, lowest_rank=lowest_rank)
        if not ok: break
        print(f"当前筹码 -> 你: {p_you.money} | 机器人: {p_bot.money}")
        cont = input("继续下一手？[Y/n]: ").strip().lower()
        if cont == "n": break
        print("\\n" + "-"*60 + "\\n")

    if p_you.money<=0 and p_bot.money<=0:
        print("双方都没钱了，打和。")
    elif p_you.money<=0:
        print("你的筹码耗尽，游戏结束。")
    elif p_bot.money<=0:
        print("机器人筹码耗尽，你获胜！")
    else:
        print("感谢游玩！")

if __name__ == "__main__":
    main()
