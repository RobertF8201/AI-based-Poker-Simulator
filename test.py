#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Texas Hold'em CLI（支持多次加注 / re-raise + all-in + 多机器人）
No-Limit（最小下注与最小加注规则）

新增：
- 你的操作多了 all-in（直接把剩余筹码押上）。若面对他人下注时 all-in 但加注幅度 < 最小加注，则按“跟注”处理（不重开行动）。
- 开局可选择机器人数量（你 + N 机器人），多人轮流行动的完整下注循环。

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
        # A 作为最小（A-5 顺）
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
        # 同花顺里把最大的 A 高顺视为“弱于”最小顺（保持与原实现一致）
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
    pid: str
    name: str
    money: int

CAT_NAMES = {
    Score.NO_PAIR:"高牌", Score.PAIR:"一对", Score.TWO_PAIR:"两对", Score.TRIPS:"三条",
    Score.STRAIGHT:"顺子", Score.FULL_HOUSE:"葫芦", Score.FLUSH:"同花",
    Score.QUADS:"四条", Score.STRAIGHT_FLUSH:"同花顺",
}

def fmt_card(c: Card): return f"{Card.RANKS[c.rank]}{Card.SUITS[c.suit]}"
def fmt_cards(cs: List[Card]): return " ".join(fmt_card(c) for c in sorted(cs, key=int, reverse=True))

def print_table_state(players: List[SimplePlayer], pot: int, street: str):
    chip_line = " | ".join([f"{p.name}:{p.money}" for p in players])
    print(f"[{street}] {chip_line} | 彩池: {pot}")

# -------------------------
# 机器人简单策略（支持触发 all-in）
# -------------------------

MIN_BET = 5
ANTE = 1

def bot_decide_action(to_call: int, last_raise: int, bot: SimplePlayer, score: Score) -> Tuple[str, int]:
    """
    返回 (action, amount)
    action: 'check' | 'bet' | 'call' | 'raise' | 'all-in' | 'fold'
    amount: bet 是下注额；call 是补齐额；raise 是加注幅度（不含跟注）；all-in 忽略数值；check/fold 为 0
    """
    stack = bot.money
    if to_call == 0:
        if score.category >= Score.TRIPS:
            # 偶尔直接 all-in
            if stack >= MIN_BET and random.random() < 0.15:
                return "all-in", 0
            bet_amt = min(stack, MIN_BET * 2)
            return ("bet", bet_amt) if bet_amt >= MIN_BET else ("check", 0)
        if score.category >= Score.PAIR:
            bet_amt = min(stack, MIN_BET)
            return ("bet", bet_amt) if bet_amt >= MIN_BET else ("check", 0)
        return "check", 0
    else:
        if score.category >= Score.TRIPS:
            min_raise = max(last_raise, MIN_BET)
            # 有时直接 all-in
            if stack > to_call + min_raise and random.random() < 0.20:
                return "all-in", 0
            if stack > to_call + min_raise:
                raise_size = min(stack - to_call, min_raise * 2)
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

# -------------------------
# 多人下注轮（支持多次加注 / re-raise + all-in）
# -------------------------

def betting_round(players: List[SimplePlayer],
                  detector: TraditionalPokerScoreDetector,
                  holes: Dict[str, List[Card]],
                  board: List[Card],
                  pot: int,
                  street: str) -> Tuple[int, Optional[str], List[str]]:
    """
    返回:
      pot: 更新后的彩池
      winner_pid: 若有人弃牌至仅剩 1 人，则返回该玩家 pid；否则 None
      alive_pids: 剩余未弃牌玩家的 pid（包含 all-in 的）
    规则：
      - 最小下注 MIN_BET；
      - 最小加注幅度 >= 上一次加注幅度 last_raise；
      - 面对下注 all-in 若 raise_size < 最小加注，视为 call。
    """
    # 仍在本轮的玩家（未弃牌）
    alive: List[str] = [p.pid for p in players if p.money > 0] + [p.pid for p in players if p.money == 0]
    alive = list(dict.fromkeys(alive))  # 保序去重
    folded: set = set()
    contrib: Dict[str, int] = {p.pid: 0 for p in players}
    opened = False
    last_raise = 0
    last_aggressor: Optional[str] = None
    idx = 0
    since_raise = 0  # 距离上次加注经过了多少连续行动（用于判断“跟注到位”结束轮次）

    def to_call_of(pid: str) -> int:
        me = contrib[pid]
        maxc = max(contrib.values()) if contrib else 0
        return max(maxc - me, 0)

    def find_player(pid: str) -> SimplePlayer:
        return next(p for p in players if p.pid == pid)

    def active_count() -> int:
        # 仍未弃牌的玩家数量（all-in 也算在内，用于结束条件）
        return len([pid for pid in alive if pid not in folded])

    # 开始循环
    full_orbit_start = alive[0] if alive else None
    first_round_no_bet_checks = 0

    while True:
        # 若只剩 1 人未弃牌 -> 直接结束
        if active_count() <= 1:
            winner_pid = next(pid for pid in alive if pid not in folded)
            return pot, winner_pid, [pid for pid in alive if pid not in folded]

        pid = alive[idx % len(alive)]
        idx += 1
        if pid in folded:
            continue
        actor = find_player(pid)

        # 已全下的玩家跳过行动
        if actor.money == 0 and to_call_of(pid) == 0:
            since_raise += 1
            # 若所有人都已匹配最高投入且无人能再行动 -> 结束
            if since_raise >= active_count():
                return pot, None, [x for x in alive if x not in folded]
            continue

        print_table_state(players, pot, street)
        print("公共牌：", fmt_cards(board) if board else "（当前为翻牌前）")

        need = to_call_of(pid)
        stack = actor.money

        # 计算手牌强度（机器人用）
        my_score = detector.get_score(holes[pid] + board) if board else detector.get_score(holes[pid])

        # 玩家/机器人不同交互
        if actor.name == "你":
            # 提示
            if need == 0 and not opened:
                if stack < MIN_BET:
                    # 筹码不足以下注，只能 check 或 all-in（实际 all-in < MIN_BET 不开启新行动，视作 check）
                    choice = input("你的操作 [check/c, all-in/a]: ").strip().lower()
                    if choice in ("all-in","a"):
                        # all-in 但 < MIN_BET -> 视作 check
                        print("你 all-in 金额不足以开局下注，按 check 处理。")
                        first_round_no_bet_checks += 1
                        since_raise += 1
                        if first_round_no_bet_checks >= len([pid for pid in alive if pid not in folded]):
                            return pot, None, [x for x in alive if x not in folded]
                        continue
                    else:
                        print("你过牌。")
                        first_round_no_bet_checks += 1
                        since_raise += 1
                        if first_round_no_bet_checks >= len([pid for pid in alive if pid not in folded]):
                            return pot, None, [x for x in alive if x not in folded]
                        continue
                else:
                    choice = input(f"你的操作 [check/c, bet/b, all-in/a] (最小下注 {MIN_BET}): ").strip().lower()
                    if choice in ("check","c",""):
                        print("你过牌。")
                        first_round_no_bet_checks += 1
                        since_raise += 1
                        if first_round_no_bet_checks >= len([pid for pid in alive if pid not in folded]):
                            return pot, None, [x for x in alive if x not in folded]
                        continue
                    elif choice in ("all-in","a"):
                        amt = stack
                        actor.money -= amt; contrib[pid] += amt; pot += amt
                        print(f"你全下 all-in {amt}。")
                        if not opened:
                            # all-in 开局下注是否生效：若 < MIN_BET 则相当于未开局（按 check 处理）
                            if amt < MIN_BET:
                                print("all-in 金额 < 最小下注，视为 check，不开启下注。")
                                first_round_no_bet_checks += 1
                                since_raise += 1
                                continue
                            opened = True
                            last_raise = amt
                            last_aggressor = pid
                            since_raise = 0
                        else:
                            # 面对下注的 all-in，是否构成有效加注
                            rsize = max(contrib.values()) - (contrib[pid]-amt)  # 实际等价于 need + raise_size
                            add_size = amt - need if need <= amt else 0
                            min_raise = max(last_raise, MIN_BET)
                            if add_size >= min_raise:
                                last_raise = add_size
                                last_aggressor = pid
                                since_raise = 0
                            else:
                                since_raise += 1
                        continue
                    elif choice in ("bet","b"):
                        # 正常下注
                        while True:
                            try:
                                v = int(input(f"请输入下注额（{MIN_BET} ~ {stack}）：").strip())
                            except:
                                print("请输入整数金额。"); continue
                            if v < MIN_BET: print(f"不能低于最小下注额 {MIN_BET}。"); continue
                            if v > stack: print("不能超过你剩余筹码。"); continue
                            break
                        actor.money -= v; contrib[pid] += v; pot += v
                        opened = True
                        last_raise = v
                        last_aggressor = pid
                        first_round_no_bet_checks = 0
                        since_raise = 0
                        continue
                    else:
                        print("无效输入，按 check 处理。")
                        first_round_no_bet_checks += 1
                        since_raise += 1
                        if first_round_no_bet_checks >= len([pid for pid in alive if pid not in folded]):
                            return pot, None, [x for x in alive if x not in folded]
                        continue
            else:
                # 面对下注：fold / call / raise / all-in
                print(f"当前需跟注：{need}。你的筹码：{stack}。")
                choice = input("你的操作 [call, raise/r, all-in/a, fold/f]: ").strip().lower()
                if choice in ("fold","f"):
                    print("你弃牌。"); folded.add(pid); since_raise += 1
                    continue
                elif choice == "call" or choice == "":
                    pay = min(need, stack)
                    actor.money -= pay; contrib[pid] += pay; pot += pay
                    print(f"你跟注 {pay}。")
                    since_raise += 1
                    # 若所有人匹配至相同投入 -> 结束本轮
                if since_raise >= active_count():
                    return pot, None, [x for x in alive if x not in folded]
                    continue
                elif choice in ("all-in","a"):
                    amt = stack
                    pay = min(need, amt)
                    actor.money -= amt; contrib[pid] += amt; pot += amt
                    print(f"你全下 all-in {amt}。")
                    add_size = amt - pay
                    if add_size >= max(last_raise, MIN_BET):
                        last_raise = add_size
                        last_aggressor = pid
                        since_raise = 0
                    else:
                        since_raise += 1
                    if since_raise >= active_count():
                        return pot, None, [x for x in alive if x not in folded]
                    continue
                elif choice in ("raise","r"):
                    min_raise = max(last_raise, MIN_BET)
                    max_raise = max(0, stack - need)
                    if max_raise <= 0:
                        print("你没有足够筹码进行加注，自动 call（或 all-in）。")
                        pay = min(need, stack)
                        actor.money -= pay; contrib[pid] += pay; pot += pay
                        since_raise += 1
                        if since_raise >= active_count():
                            return pot, None, [x for x in alive if x not in folded]
                        continue
                    while True:
                        try:
                            rsize = int(input(f"请输入加注幅度（不含跟注），至少 {min_raise}，最多 {max_raise}：").strip())
                        except:
                            print("请输入整数金额。"); continue
                        if rsize < min_raise: print(f"加注幅度不能小于 {min_raise}。"); continue
                        if rsize > max_raise: print("超过可用筹码。"); continue
                        break
                    pay = need + rsize
                    actor.money -= pay; contrib[pid] += pay; pot += pay
                    last_raise = rsize; last_aggressor = pid; since_raise = 0
                    continue
                else:
                    print("无效输入，按跟注处理。")
                    pay = min(need, stack)
                    actor.money -= pay; contrib[pid] += pay; pot += pay
                    since_raise += 1
                    if since_raise >= active_count():
                        return pot, None, [x for x in alive if x not in folded]
                    continue
        else:
            # 机器人
            act, val = bot_decide_action(need, last_raise, actor, my_score)
            if need == 0 and not opened:
                if act == "all-in":
                    amt = actor.money
                    if amt < MIN_BET:
                        print(f"{actor.name} 过牌。")
                        first_round_no_bet_checks += 1
                        since_raise += 1
                        if first_round_no_bet_checks >= len([pid for pid in alive if pid not in folded]):
                            return pot, None, [x for x in alive if x not in folded]
                        continue
                    actor.money -= amt; contrib[pid] += amt; pot += amt
                    opened = True; last_raise = amt; last_aggressor = pid
                    print(f"{actor.name} 全下 all-in {amt}。")
                    since_raise = 0; first_round_no_bet_checks = 0; continue
                elif act == "bet":
                    amt = min(actor.money, max(val, MIN_BET))
                    if amt < MIN_BET:
                        print(f"{actor.name} 过牌。"); first_round_no_bet_checks += 1; since_raise += 1
                        if first_round_no_bet_checks >= len([pid for pid in alive if pid not in folded]):
                            return pot, None, [x for x in alive if x not in folded]
                        continue
                    actor.money -= amt; contrib[pid] += amt; pot += amt
                    opened = True; last_raise = amt; last_aggressor = pid
                    print(f"{actor.name} 下注 {amt}。")
                    since_raise = 0; first_round_no_bet_checks = 0; continue
                else:
                    print(f"{actor.name} 过牌。")
                    first_round_no_bet_checks += 1
                    since_raise += 1
                    if first_round_no_bet_checks >= len([pid for pid in alive if pid not in folded]):
                        return pot, None, [x for x in alive if x not in folded]
                    continue
            else:
                if act == "fold":
                    print(f"{actor.name} 弃牌。"); folded.add(pid); since_raise += 1; continue
                elif act == "call":
                    pay = min(need, actor.money)
                    actor.money -= pay; contrib[pid] += pay; pot += pay
                    print(f"{actor.name} 跟注 {pay}。")
                    since_raise += 1
                    if since_raise >= active_count():
                        return pot, None, [x for x in alive if x not in folded]
                    continue
                elif act == "all-in":
                    amt = actor.money
                    pay = min(need, amt)
                    actor.money -= amt; contrib[pid] += amt; pot += amt
                    print(f"{actor.name} 全下 all-in {amt}。")
                    add_size = amt - pay
                    if add_size >= max(last_raise, MIN_BET):
                        last_raise = add_size; last_aggressor = pid; since_raise = 0
                    else:
                        since_raise += 1
                    if since_raise >= active_count():
                        return pot, None, [x for x in alive if x not in folded]
                    continue
                elif act == "raise":
                    min_raise = max(last_raise, MIN_BET)
                    max_rsize = max(0, actor.money - need)
                    if max_rsize < min_raise:
                        pay = min(need, actor.money)
                        actor.money -= pay; contrib[pid] += pay; pot += pay
                        print(f"{actor.name} 筹码不足有效加注，改为跟注 {pay}。")
                        since_raise += 1
                    if since_raise >= active_count():
                        return pot, None, [x for x in alive if x not in folded]
                        continue
                    rsize = min(val, max_rsize)
                    rsize = max(rsize, min_raise)
                    pay = need + rsize
                    actor.money -= pay; contrib[pid] += pay; pot += pay
                    last_raise = rsize; last_aggressor = pid; print(f"{actor.name} 加注 {rsize}（总投入 +{pay}）。")
                    since_raise = 0; continue

# -------------------------
# 局面推进与摊牌（多人）
# -------------------------

def showdown(detector, holes: Dict[str, List[Card]], board: List[Card], alive_pids: List[str]) -> Tuple[List[str], Dict[str, Score]]:
    scores: Dict[str, Score] = {}
    for pid in alive_pids:
        scores[pid] = detector.get_score(holes[pid] + board)
    # 找最大
    best_pids = [alive_pids[0]]
    for pid in alive_pids[1:]:
        if scores[pid].cmp(scores[best_pids[0]]) > 0:
            best_pids = [pid]
        elif scores[pid].cmp(scores[best_pids[0]]) == 0:
            best_pids.append(pid)
    return best_pids, scores

def fmt_board(board: List[Card]) -> str:
    return fmt_cards(board) if board else "(无)"

def play_hand(players: List[SimplePlayer], lowest_rank: int = 2) -> bool:
    pot = 0
    # 收取前注
    active = [p for p in players if p.money > 0]
    if len(active) < 2:
        for p in players:
            if p.money <= 0:
                print(f"{p.name} 已无筹码。")
        return False
    for p in players:
        if p.money <= 0: continue
        ante_amt = min(ANTE, p.money); p.money -= ante_amt; pot += ante_amt

    deck = Deck(lowest_rank=lowest_rank)
    detector = TraditionalPokerScoreDetector(lowest_rank)

    # 发手牌（每人 2 张）
    holes: Dict[str, List[Card]] = {p.pid: deck.pop_cards(2) for p in players}
    board: List[Card] = []

    print("===== 新手开始 =====")
    print_table_state(players, pot, "Preflop")
    print("你的手牌：", fmt_cards(holes[players[0].pid]))  # 假设 players[0] 是“你”

    # Preflop
    pot, winner_pid, alive_pids = betting_round(players, detector, holes, board, pot, "Preflop")
    if winner_pid:
        winner = next(p for p in players if p.pid == winner_pid)
        print(f"{winner.name} 直接获胜，收入彩池 {pot}。"); winner.money += pot; return True

    # Flop
    board += deck.pop_cards(3)
    print_table_state(players, pot, "Flop")
    print("公共牌：", fmt_cards(board))
    pot, winner_pid, alive_pids = betting_round(players, detector, holes, board, pot, "Flop")
    if winner_pid:
        winner = next(p for p in players if p.pid == winner_pid)
        print(f"{winner.name} 直接获胜，收入彩池 {pot}。"); winner.money += pot; return True

    # Turn
    board += deck.pop_cards(1)
    print_table_state(players, pot, "Turn")
    print("公共牌：", fmt_cards(board))
    pot, winner_pid, alive_pids = betting_round(players, detector, holes, board, pot, "Turn")
    if winner_pid:
        winner = next(p for p in players if p.pid == winner_pid)
        print(f"{winner.name} 直接获胜，收入彩池 {pot}。"); winner.money += pot; return True

    # River
    board += deck.pop_cards(1)
    print_table_state(players, pot, "River")
    print("公共牌：", fmt_cards(board))
    pot, winner_pid, alive_pids = betting_round(players, detector, holes, board, pot, "River")
    if winner_pid:
        winner = next(p for p in players if p.pid == winner_pid)
        print(f"{winner.name} 直接获胜，收入彩池 {pot}。"); winner.money += pot; return True

    # 摊牌
    print("—— 摊牌 ——")
    print("公共牌：", fmt_cards(board))
    for p in players:
        print(f"{p.name} 手牌：{fmt_cards(holes[p.pid])}")

    best_pids, scores = showdown(detector, holes, board, alive_pids)
    for pid, sc in scores.items():
        print(f"{next(p for p in players if p.pid==pid).name} 牌型：{CAT_NAMES[sc.category]}")

    if len(best_pids) == 1:
        winner = next(p for p in players if p.pid == best_pids[0])
        print(f"{winner.name} 赢了！获得彩池 {pot}。"); winner.money += pot
    else:
        split = pot // len(best_pids)
        names = ", ".join(next(p for p in players if p.pid==pid).name for pid in best_pids)
        print(f"平局（{names}），彩池平分：每人 {split}。")
        for pid in best_pids:
            next(p for p in players if p.pid==pid).money += split
        remainder = pot - split * len(best_pids)
        if remainder:
            # 把余数给座位顺序中最靠前的赢家
            next(p for p in players if p.pid==best_pids[0]).money += remainder

    return True

# -------------------------
# 主程序
# -------------------------

def main():
    print("===== Texas Hold'em（多次加注 / re-raise + all-in + 多机器人） =====")
    # 选择机器人数量
    while True:
        try:
            n_bots = int(input("请输入机器人数量（1 ~ 5）：").strip() or "1")
            if not (1 <= n_bots <= 5):
                print("请输入 1~5 的整数。"); continue
            break
        except:
            print("请输入合法整数。")

    # 初始筹码
    init_stack = 100
    lowest_rank = 2

    # 座位顺序：你在第一个
    players: List[SimplePlayer] = [SimplePlayer(pid="you", name="你", money=init_stack)]
    for i in range(1, n_bots+1):
        players.append(SimplePlayer(pid=f"bot{i}", name=f"机器人{i}", money=init_stack))

    while True:
        # 检查至少两人有筹码
        actives = [p for p in players if p.money > 0]
        if len(actives) < 2:
            if len(actives) == 1:
                print(f"{actives[0].name} 成为桌上最后的赢家！")
            else:
                print("所有人都没钱了，打和。")
            break

        ok = play_hand(players, lowest_rank=lowest_rank)
        if not ok: break

        # 显示筹码
        print("当前筹码：", " | ".join([f"{p.name}:{p.money}" for p in players]))
        cont = input("继续下一手？[Y/n]: ").strip().lower()
        if cont == "n":
            print("感谢游玩！")
            break
        print("\n" + "-"*60 + "\n")

if __name__ == "__main__":
    main()
