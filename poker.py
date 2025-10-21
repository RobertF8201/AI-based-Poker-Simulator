#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Texas Hold'em (Simplified) — Command-Line Demo with Betting Actions
------------------------------------------------------------------
Features
- Pre-Flop, Flop, Turn, River reveal with user pauses
- Player actions: fold, check, call, raise, all-in
- Chip accounting with blinds and (basic) side-pot handling
- Modular classes (Deck, Player, PotManager, BettingRound, Game)

Notes
- This is a learning/demo implementation: betting flow and side pots are handled
  in a practical, readable way. Hand-ranking is intentionally omitted; at
  showdown we simply list contributions and end the hand (you can plug in a
  hand-evaluator later).
- Single human player vs a simple bot. You can extend to more players easily.
"""
from __future__ import annotations
import random
import os
from typing import List, Dict, Set, Optional

# ----------------------------
# Helpers / UI
# ----------------------------


def pause(msg: str = "\n按下 Enter 继续..."):
    input(msg)


def chips_fmt(x: int) -> str:
    return f"💰{x}"


# ----------------------------
# Cards & Deck
# ----------------------------
class Deck:
    SUITS = ['♠', '♥', '♦', '♣']
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

    def __init__(self):
        self.cards: List[str] = [f"{r}{s}" for s in Deck.SUITS for r in Deck.RANKS]
        random.shuffle(self.cards)

    def deal(self, n: int) -> List[str]:
        return [self.cards.pop() for _ in range(n)]


# ----------------------------
# Player
# ----------------------------
class Player:
    def __init__(self, name: str, chips: int, is_human: bool = False):
        self.name = name
        self.chips = chips
        self.is_human = is_human
        self.hand: List[str] = []
        self.in_hand = True
        self.all_in = False
        self.curr_bet = 0

    def reset_for_new_round(self):
        self.curr_bet = 0
        if self.chips == 0 and self.in_hand:
            self.all_in = True

    def __repr__(self):
        state = []
        if not self.in_hand:
            state.append("FOLDED")
        if self.all_in:
            state.append("ALL-IN")
        sflag = (" (" + ", ".join(state) + ")") if state else ""
        return f"{self.name}{sflag} {chips_fmt(self.chips)}"


# ----------------------------
# Pot Manager
# ----------------------------
class PotManager:
    def __init__(self, players: List[Player]):
        self.players = players
        self.contribs: Dict[Player, int] = {p: 0 for p in players}
        self.pots: List[Dict] = []

    def add_contrib(self, p: Player, amount: int):
        assert amount >= 0
        self.contribs[p] += amount

    def rebuild_pots(self, active_players: Set[Player]):
        contrib_values = sorted(set(v for v in self.contribs.values() if v > 0))
        self.pots = []
        prev = 0
        for tier in contrib_values:
            elig = {p for p, v in self.contribs.items() if v >= tier and p in active_players}
            if not elig:
                prev = tier
                continue
            width = tier - prev
            if width <= 0:
                prev = tier
                continue
            amount = width * len(elig)
            if amount > 0:
                self.pots.append({"amount": amount, "eligible": set(elig)})
            prev = tier

    def debug_pots(self) -> str:
        if not self.pots:
            return f"(总池：{chips_fmt(sum(self.contribs.values()))})"
        parts = []
        running = 0
        for i, pot in enumerate(self.pots, 1):
            running += pot['amount']
            names = ', '.join(p.name for p in pot['eligible'])
            parts.append(f"SidePot#{i}: {chips_fmt(pot['amount'])} (eligible: {names})")
        parts.append(f"Total: {chips_fmt(running)})")
        return ' | '.join(parts)


# ----------------------------
# Betting Round
# ----------------------------
class BettingRound:
    def __init__(self, players: List[Player], pot: PotManager, min_raise: int):
        self.players = players
        self.pot = pot
        self.min_raise = min_raise
        self.current_bet = 0
        self.last_raiser: Optional[Player] = None

    def run(self, start_idx: int) -> int:
        for p in self.players:
            p.reset_for_new_round()
        self.current_bet = 0
        self.last_raiser = None
        idx = start_idx

        def active_non_allin():
            return [p for p in self.players if p.in_hand and not p.all_in]

        while True:
            if len(active_non_allin()) <= 1:
                break
            p = self.players[idx]
            if p.in_hand and not p.all_in:
                self._act(p)
                if self._all_matched_or_folded():
                    break
            idx = (idx + 1) % len(self.players)

        active = {pl for pl in self.players if pl.in_hand}
        self.pot.rebuild_pots(active)
        return idx

    def _all_matched_or_folded(self) -> bool:
        for p in self.players:
            if not p.in_hand or p.all_in:
                continue
            if p.curr_bet < self.current_bet:
                return False
        return True

    def _commit(self, p: Player, amount: int):
        commit = min(amount, p.chips)
        p.chips -= commit
        p.curr_bet += commit
        self.pot.add_contrib(p, commit)
        if p.chips == 0:
            p.all_in = True

    # --- actions ---
    def _act(self, p: Player):
        to_call = self.current_bet - p.curr_bet
        if p.is_human:
            self._human_action(p, to_call)
        else:
            self._bot_action(p, to_call)

    def _human_action(self, p: Player, to_call: int):
        print(f"\n👉 {p.name} 行动 | 筹码 {chips_fmt(p.chips)} | 本轮已下 {chips_fmt(p.curr_bet)} | 需跟注 {chips_fmt(max(0, to_call))}")
        while True:
            cmd = input("输入动作(check/call/raise/all-in/fold): ").strip().lower()
            if cmd == "fold":
                p.in_hand = False
                print(f"{p.name} 弃牌。")
                break
            if cmd == "check":
                if to_call > 0:
                    print("当前有下注，不能check。")
                    continue
                print("过牌。")
                break
            if cmd == "call":
                self._commit(p, to_call)
                print(f"跟注 {chips_fmt(to_call)}")
                break
            if cmd == "raise":
                amt = self._ask_amount(p, self.current_bet + self.min_raise, "加注到(总投入)")
                add = amt - p.curr_bet
                self._commit(p, add)
                self.current_bet = p.curr_bet
                print(f"加注到 {chips_fmt(self.current_bet)}")
                break
            if cmd == "all-in":
                add = p.chips
                self._commit(p, add)
                if p.curr_bet > self.current_bet:
                    self.current_bet = p.curr_bet
                print("全下！")
                break

    def _ask_amount(self, p: Player, minimum: int, label: str) -> int:
        while True:
            try:
                raw = input(f"{label}（至少 {chips_fmt(minimum)}）: ").strip()
                amt = int(raw)
                if amt < minimum or amt > p.curr_bet + p.chips:
                    print("输入无效。")
                    continue
                return amt
            except ValueError:
                print("请输入整数金额。")

    def _bot_action(self, p: Player, to_call: int):
        if to_call <= 0:
            print(f"🤖 {p.name} 过牌")
        else:
            if random.random() < 0.8:
                self._commit(p, to_call)
                print(f"🤖 {p.name} 跟注 {chips_fmt(to_call)}")
            else:
                p.in_hand = False
                print(f"🤖 {p.name} 弃牌")


# ----------------------------
# Game
# ----------------------------
class Game:
    def __init__(self, players: List[Player], sb: int = 10, bb: int = 20):
        self.players = players
        self.deck = Deck()
        self.community: List[str] = []
        self.button_idx = 0
        self.sb = sb
        self.bb = bb
        self.pot_mgr = PotManager(players)

    def deal_new_hand(self):
        self.deck = Deck()
        self.community = []
        for p in self.players:
            p.hand = self.deck.deal(2)
            p.in_hand = True
            p.all_in = (p.chips == 0)
            p.curr_bet = 0
        print("🎲 新一手开始！")
        print(self.seat_info())

    def post_blinds(self):
        sb_i = (self.button_idx + 1) % len(self.players)
        bb_i = (self.button_idx + 2) % len(self.players)
        sb, bb = self.players[sb_i], self.players[bb_i]
        print(f"小盲 {sb.name} {chips_fmt(self.sb)}，大盲 {bb.name} {chips_fmt(self.bb)}")
        self._commit(sb, self.sb)
        self._commit(bb, self.bb)

    def _commit(self, p: Player, amount: int):
        commit = min(amount, p.chips)
        p.chips -= commit
        p.curr_bet += commit
        self.pot_mgr.add_contrib(p, commit)
        if p.chips == 0:
            p.all_in = True

    def betting_round(self, start_idx: int) -> int:
        br = BettingRound(self.players, self.pot_mgr, self.bb)
        nxt = br.run(start_idx)
        self._round_summary()
        return nxt

    def reveal(self, street: str):
        if street == "flop":
            self.community += self.deck.deal(3)
        else:
            self.community += self.deck.deal(1)
        print(f"{street.upper()} 公共牌：{'  '.join(self.community)}")

    def seat_info(self) -> str:
        return " | ".join(f"{p.name}{' (BTN)' if i==self.button_idx else ''}:{chips_fmt(p.chips)}"
                          for i, p in enumerate(self.players))

    def show_holecards(self):
        for p in self.players:
            if p.is_human:
                print(f"你的手牌：{p.hand[0]}  {p.hand[1]}")
            else:
                print(f"{p.name} 的手牌：[?? ??]")

    def _round_summary(self):
        print("\n—— 本轮下注汇总 ——")
        for p in self.players:
            tag = "FOLDED" if not p.in_hand else ("ALL-IN" if p.all_in else "")
            print(f"{p.name} {tag} 投入: {chips_fmt(p.curr_bet)} 剩余: {chips_fmt(p.chips)}")
        self.pot_mgr.rebuild_pots({pl for pl in self.players if pl.in_hand})
        print("彩池：", self.pot_mgr.debug_pots())
        pause()

    def play_hand(self):
        self.deal_new_hand()
        pause()
        self.show_holecards()
        pause()

        self.post_blinds()
        pause()

        start_idx = (self.button_idx + 3) % len(self.players)
        start_idx = self.betting_round(start_idx)

        if self._one_left(): return self._award_uncontested()

        for street in ["flop", "turn", "river"]:
            self.reveal(street)
            start_idx = self.betting_round((self.button_idx + 1) % len(self.players))
            if self._one_left(): return self._award_uncontested()

        self._showdown_placeholder()

    def _one_left(self): return sum(p.in_hand for p in self.players) == 1

    def _award_uncontested(self):
        winner = next(p for p in self.players if p.in_hand)
        total = sum(self.pot_mgr.contribs.values())
        winner.chips += total
        print(f"{winner.name} 获得底池 {chips_fmt(total)}")
        pause()

    def _showdown_placeholder(self):
        print("\n🧾 摊牌（演示版，无牌力比较）")
        print("公共牌：", '  '.join(self.community))
        for p in self.players:
            hole = '  '.join(p.hand) if p.is_human else '[?? ??]'
            print(f"{p.name}: {hole} 状态: {'FOLDED' if not p.in_hand else 'IN'} 投入: {chips_fmt(self.pot_mgr.contribs[p])}")
        total = sum(self.pot_mgr.contribs.values())
        print(f"总底池：{chips_fmt(total)}")
        pause()


# ----------------------------
# Main entry
# ----------------------------
def main():
    random.seed()
    human = Player("你", 1000, True)
    bot = Player("机器人", 1000)
    game = Game([human, bot])

    while True:
        game.play_hand()
        print("座位与筹码：", game.seat_info())
        cont = input("继续下一手? (y/n): ").strip().lower()
        if cont != 'y':
            print("游戏结束，感谢体验！")
            break


if __name__ == '__main__':
    main()
