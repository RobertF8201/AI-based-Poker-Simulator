import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022", 
    api_key="sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI",
    base_url="https://yinli.one",
    temperature=0
)

### Card Face
class Card:
    RANKS = {2:"2",3:"3",4:"4",5:"5",6:"6",7:"7",8:"8",9:"9",10:"10",11:"J",12:"Q",13:"K",14:"A"}
    SUITS = {0:"♠",1:"♣",2:"♦",3:"♥"}
    def __init__(self, rank: int, suit: int):
        if rank not in Card.RANKS or suit not in Card.SUITS:
            raise ValueError("Invalid card")
        self._value = (rank<<2)+suit

    @property
    def rank(self): return self._value >> 2

    @property
    def suit(self): return self._value & 3

    def __int__(self): return self._value    # int(card)

    def __lt__(self, other): return int(self) < int(other)  # card1 < card2

    def __repr__(self): return f"{Card.RANKS[self.rank]}{Card.SUITS[self.suit]}"    # print(card)

class Deck:
    def __init__(self, lowest_rank: int = 2):
        self.cards = [Card(r, s) for r in range(lowest_rank, 15) for s in range(4)]
        self.discard = []
        random.shuffle(self.cards)

    # deal card
    def pop_cards(self, n=1):
        out = []
        while n > 0:
            if not self.cards:
                self.cards, self.discard = self.discard, []
                random.shuffile(self.cards)
            out.append(self.cards.pop())
            n-=1
        return out
    
    # fold card > 1
    def push_cards(self, disc):
        self.discard += disc

class CardsHelper:
    def __init__(self, cards, lowest_rank=2):
        # only sort by rank, neglect suit
        self._sorted = sorted(cards, key=lambda c: c.rank, reverse=True)
        self._lowest_rank = lowest_rank

    # sort the card to assess the cards
    def _group_by_ranks(self):
        d = {}
        for c in self._sorted:
            # if d does not contains key c.rank, then create a empty list or append directly
            d.setdefault(c.rank, []).append(c)
        return d

    def _x_sorted_list(self, x: int):
        # groups = [lst for lst in self._group_by_ranks().values() if len(lst) == x]
        groups = []  # to keep deck
        # get lists divided by rank
        for lst in self._group_by_ranks().values():
            if len(lst) == x:
                groups.append(lst)
        # neglect suits, rank by DESC
        groups.sort(key=lambda g: g[0].rank, reverse=True)
        return groups

    def _get_straight(self, sorted_cards):
        # straight needs to be at least 5
        if len(sorted_cards) < 5:
            return None

        # Deduplication by rank(neglect suit)
        uniq, seen = [], set()
        for c in sorted_cards:
            if c.rank not in seen:
                uniq.append(c)
                seen.add(c.rank)
        if not uniq:    # no cards
            return None

        # Use a sliding window to find the longest segment in uniq with a difference of 1 
        # between adjacent points return directly when the length reaches 5
        straight = [uniq[0]]
        for i in range(1, len(uniq)):
            if uniq[i].rank == uniq[i - 1].rank - 1:    # cur rank equals pre rank minus 1
                straight.append(uniq[i])
                if len(straight) == 5:  # directly return when find straight
                    return straight
            else:
                straight = [uniq[i]]    # rank interrupted inital straight list

        # special consideration for {1,2,3,4,5}
        ranks = [c.rank for c in uniq]
        if 14 in ranks and {2, 3, 4, 5}.issubset(ranks):
            seq, need = [], {5, 4, 3, 2}
            # collect 5,4,3,2
            for c in uniq:
                if c.rank in need:
                    seq.append(c)
                    need.remove(c.rank)
                    if not need:    # find all
                        break
            a = next((c for c in uniq if c.rank == 14), None)   # find 'A' 
            if a:
                seq.append(a)
                return seq
        return None

    # rank by kicks, besides score cards bucket, negelect suit
    def _merge(self, score_cards):
        return score_cards + [c for c in self._sorted if c not in score_cards]

    def _check_suits(self):
        # seperate cards by suits
        suits = {}  # suits bucket
        for c in self._sorted:
            suits.setdefault(c.suit, []).append(c)
        return suits

    def straight_flush(self):
        suits = self._check_suits()
        for s_cards in suits.values():
            if len(s_cards) >= 5:   # if one suit is more than 5 card
                s_cards.sort(key=lambda c: c.rank, reverse=True)    # sort card in bucket for checking straight
                st = self._get_straight(s_cards)
                if st:
                    return st
        return None

    def quads(self):
        q = self._x_sorted_list(4)
        # return quads and kicks
        return (self._merge(q[0])[:5]) if q else None

    def flush(self):
        suits = self._check_suits()
        for s_cards in suits.values():
            if len(s_cards) >= 5:
                s_cards.sort(key=lambda c: c.rank, reverse=True)
                return s_cards[:5]
        return None

    def full_house(self):
        trips = self._x_sorted_list(3)
        pairs = self._x_sorted_list(2)
        # 3+2 or 3+3 or 3 + 4
        if trips and (len(trips) >= 2 or pairs):
            if len(trips) >= 2:
                # big trip + 2 of small trip
                return (self._merge(trips[0] + trips[1][:2])[:5])
            # return full house
            return (self._merge(trips[0] + pairs[0])[:5])
        return None

    def straight(self):
        return self._get_straight(self._sorted)

    def trips(self):
        t = self._x_sorted_list(3)
        return (self._merge(t[0])[:5]) if t else None

    def two_pair(self):
        p = self._x_sorted_list(2)
        return (self._merge(p[0] + p[1])[:5]) if len(p) >= 2 else None

    def pair(self):
        p = self._x_sorted_list(2)
        return (self._merge(p[0])[:5]) if p else None

    def no_pair(self):
        return self._sorted[:5]

class Score:
    # 0-8 rank the card category
    NO_PAIR, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FULL_HOUSE, FLUSH, QUADS, STRAIGHT_FLUSH = range(9)
    def __init__(self, category, cards): 
        self.category = category
        self.cards = cards

    @property
    def strength(self):
        s = self.category   # category above
        for i in range(5):  # after will be [category][rank1][rank2][rank3][rank4][rank5]
            s <<= 4 # 2-14 need 2^4=16 t represent each card
            s += self.cards[i].rank if i < len(self.cards) else 0   # fold before 5 card
        return s    # do not consider suit, they do not provide weight
    
    def cmp(self, other):
        # compare categoty
        if self.category != other.category:
            return -1 if self.category < other.category else 1
        # compare rank
        for i in range(5):
            r1 = self.cards[i].rank if i < len(self.cards) else 0
            r2 = other.cards[i].rank if i < len(other.cards) else 0
            if r1 != r2:
                return -1 if r1 < r2 else 1
        # same score
        return 0

class PokerScoreCalculator:
    def __init__(self, lowest_rank=2): 
        self._lowest_rank=lowest_rank

    def get_score(self, cards) -> Score:
        ch = CardsHelper(cards, self._lowest_rank)
        # get score for hand based on category
        for cat, fn in [(Score.STRAIGHT_FLUSH,ch.straight_flush),
                        (Score.QUADS,ch.quads),
                        (Score.FLUSH,ch.flush),
                        (Score.FULL_HOUSE,ch.full_house),
                        (Score.STRAIGHT,ch.straight),
                        (Score.TRIPS,ch.trips),
                        (Score.TWO_PAIR,ch.two_pair),
                        (Score.PAIR,ch.pair),
                        (Score.NO_PAIR,ch.no_pair)]:
            res = fn()  # related function
            if res: 
                return Score(cat,res)   # category + hand score
        raise RuntimeError("Poker Score Detector Error")

### Entity
@dataclass # decorator to add __init__, __repr__, __eq__
class SimplePlayer:
    name: str
    money: int

CAT_NAMES = {
    Score.NO_PAIR: "High Card",
    Score.PAIR: "One Pair",
    Score.TWO_PAIR: "Two Pair",
    Score.TRIPS: "Three of a Kind",
    Score.STRAIGHT: "Straight",
    Score.FULL_HOUSE: "Full House",
    Score.FLUSH: "Flush",
    Score.QUADS: "Four of a Kind",
    Score.STRAIGHT_FLUSH: "Straight Flush"
}

def fmt_card(c):
    return f"{Card.RANKS[c.rank]}{Card.SUITS[c.suit]}"

def fmt_cards(cs): 
    return " ".join(fmt_card(c) for c in sorted(cs, key=int, reverse=True))

def print_state(player: SimplePlayer, pot: int, street: str):
    print(f"---{street}---\n Your chips: [{player.money}]\n Pot: [{pot}]\n-------------")

### Bet/Raise
MIN_BET = 5
ANTE = 1

def ask_int(prompt):    # get user input
    s = input(prompt).strip()
    if s == "": 
        return None
    if s.isdigit(): 
        return int(s)
    try: 
        return int(s)
    except: 
        return None
    
def ask_bet_amount(max_amt, min_amt):
    while True:
        v = ask_int(f"Enter your bet amount ({min_amt} - {max_amt}): ")
        if v is None:
            print("Please enter an integer amount.")
            continue
        if v < min_amt:
            print(f"The bet cannot be lower than the minimum amount ({min_amt}).")
            continue
        if v > max_amt:
            print(f"The bet cannot exceed your remaining chips ({max_amt}).")
            continue
        return v

def ask_raise_size(max_amt, min_raise):
    while True:
        v = ask_int(f"Enter your raise size (excluding the call amount), minimum {min_raise}, maximum {max_amt}: ")
        if v is None:
            print("Please enter an integer amount.")
            continue
        if v < min_raise:
            print(f"The raise size cannot be smaller than {min_raise}.")
            continue
        if v > max_amt:
            print(f"The raise size cannot exceed your remaining chips ({max_amt}).")
            continue
        return v

import random
from dataclasses import dataclass

### Card Face
class Card:
    RANKS = {2:"2",3:"3",4:"4",5:"5",6:"6",7:"7",8:"8",9:"9",10:"10",11:"J",12:"Q",13:"K",14:"A"}
    SUITS = {0:"♠",1:"♣",2:"♦",3:"♥"}
    def __init__(self, rank: int, suit: int):
        if rank not in Card.RANKS or suit not in Card.SUITS:
            raise ValueError("Invalid card")
        self._value = (rank<<2)+suit

    @property
    def rank(self): return self._value >> 2

    @property
    def suit(self): return self._value & 3

    def __int__(self): return self._value    # int(card)

    def __lt__(self, other): return int(self) < int(other)  # card1 < card2

    def __repr__(self): return f"{Card.RANKS[self.rank]}{Card.SUITS[self.suit]}"    # print(card)

class Deck:
    def __init__(self, lowest_rank: int = 2):
        self.cards = [Card(r, s) for r in range(lowest_rank, 15) for s in range(4)]
        self.discard = []
        random.shuffle(self.cards)

    # deal card
    def pop_cards(self, n=1):
        out = []
        while n > 0:
            if not self.cards:
                self.cards, self.discard = self.discard, []
                random.shuffile(self.cards)
            out.append(self.cards.pop())
            n-=1
        return out
    
    # fold card > 1
    def push_cards(self, disc):
        self.discard += disc

class CardsHelper:
    def __init__(self, cards, lowest_rank=2):
        # only sort by rank, neglect suit
        self._sorted = sorted(cards, key=lambda c: c.rank, reverse=True)
        self._lowest_rank = lowest_rank

    # sort the card to assess the cards
    def _group_by_ranks(self):
        d = {}
        for c in self._sorted:
            # if d does not contains key c.rank, then create a empty list or append directly
            d.setdefault(c.rank, []).append(c)
        return d

    def _x_sorted_list(self, x: int):
        # groups = [lst for lst in self._group_by_ranks().values() if len(lst) == x]
        groups = []  # to keep deck
        # get lists divided by rank
        for lst in self._group_by_ranks().values():
            if len(lst) == x:
                groups.append(lst)
        # neglect suits, rank by DESC
        groups.sort(key=lambda g: g[0].rank, reverse=True)
        return groups

    def _get_straight(self, sorted_cards):
        # straight needs to be at least 5
        if len(sorted_cards) < 5:
            return None

        # Deduplication by rank(neglect suit)
        uniq, seen = [], set()
        for c in sorted_cards:
            if c.rank not in seen:
                uniq.append(c)
                seen.add(c.rank)
        if not uniq:    # no cards
            return None

        # Use a sliding window to find the longest segment in uniq with a difference of 1 
        # between adjacent points return directly when the length reaches 5
        straight = [uniq[0]]
        for i in range(1, len(uniq)):
            if uniq[i].rank == uniq[i - 1].rank - 1:    # cur rank equals pre rank minus 1
                straight.append(uniq[i])
                if len(straight) == 5:  # directly return when find straight
                    return straight
            else:
                straight = [uniq[i]]    # rank interrupted inital straight list

        # special consideration for {1,2,3,4,5}
        ranks = [c.rank for c in uniq]
        if 14 in ranks and {2, 3, 4, 5}.issubset(ranks):
            seq, need = [], {5, 4, 3, 2}
            # collect 5,4,3,2
            for c in uniq:
                if c.rank in need:
                    seq.append(c)
                    need.remove(c.rank)
                    if not need:    # find all
                        break
            a = next((c for c in uniq if c.rank == 14), None)   # find 'A' 
            if a:
                seq.append(a)
                return seq
        return None

    # rank by kicks, besides score cards bucket, negelect suit
    def _merge(self, score_cards):
        return score_cards + [c for c in self._sorted if c not in score_cards]

    def _check_suits(self):
        # seperate cards by suits
        suits = {}  # suits bucket
        for c in self._sorted:
            suits.setdefault(c.suit, []).append(c)
        return suits

    def straight_flush(self):
        suits = self._check_suits()
        for s_cards in suits.values():
            if len(s_cards) >= 5:   # if one suit is more than 5 card
                s_cards.sort(key=lambda c: c.rank, reverse=True)    # sort card in bucket for checking straight
                st = self._get_straight(s_cards)
                if st:
                    return st
        return None

    def quads(self):
        q = self._x_sorted_list(4)
        # return quads and kicks
        return (self._merge(q[0])[:5]) if q else None

    def flush(self):
        suits = self._check_suits()
        for s_cards in suits.values():
            if len(s_cards) >= 5:
                s_cards.sort(key=lambda c: c.rank, reverse=True)
                return s_cards[:5]
        return None

    def full_house(self):
        trips = self._x_sorted_list(3)
        pairs = self._x_sorted_list(2)
        # 3+2 or 3+3 or 3 + 4
        if trips and (len(trips) >= 2 or pairs):
            if len(trips) >= 2:
                # big trip + 2 of small trip
                return (self._merge(trips[0] + trips[1][:2])[:5])
            # return full house
            return (self._merge(trips[0] + pairs[0])[:5])
        return None

    def straight(self):
        return self._get_straight(self._sorted)

    def trips(self):
        t = self._x_sorted_list(3)
        return (self._merge(t[0])[:5]) if t else None

    def two_pair(self):
        p = self._x_sorted_list(2)
        return (self._merge(p[0] + p[1])[:5]) if len(p) >= 2 else None

    def pair(self):
        p = self._x_sorted_list(2)
        return (self._merge(p[0])[:5]) if p else None

    def no_pair(self):
        return self._sorted[:5]

class Score:
    # 0-8 rank the card category
    NO_PAIR, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FULL_HOUSE, FLUSH, QUADS, STRAIGHT_FLUSH = range(9)
    def __init__(self, category, cards): 
        self.category = category
        self.cards = cards

    @property
    def strength(self):
        s = self.category   # category above
        for i in range(5):  # after will be [category][rank1][rank2][rank3][rank4][rank5]
            s <<= 4 # 2-14 need 2^4=16 t represent each card
            s += self.cards[i].rank if i < len(self.cards) else 0   # fold before 5 card
        return s    # do not consider suit, they do not provide weight
    
    def cmp(self, other):
        # compare categoty
        if self.category != other.category:
            return -1 if self.category < other.category else 1
        # compare rank
        for i in range(5):
            r1 = self.cards[i].rank if i < len(self.cards) else 0
            r2 = other.cards[i].rank if i < len(other.cards) else 0
            if r1 != r2:
                return -1 if r1 < r2 else 1
        # same score
        return 0

class PokerScoreCalculator:
    def __init__(self, lowest_rank=2): 
        self._lowest_rank=lowest_rank

    def get_score(self, cards) -> Score:
        ch = CardsHelper(cards, self._lowest_rank)
        # get score for hand based on category
        for cat, fn in [(Score.STRAIGHT_FLUSH,ch.straight_flush),
                        (Score.QUADS,ch.quads),
                        (Score.FLUSH,ch.flush),
                        (Score.FULL_HOUSE,ch.full_house),
                        (Score.STRAIGHT,ch.straight),
                        (Score.TRIPS,ch.trips),
                        (Score.TWO_PAIR,ch.two_pair),
                        (Score.PAIR,ch.pair),
                        (Score.NO_PAIR,ch.no_pair)]:
            res = fn()  # related function
            if res: 
                return Score(cat,res)   # category + hand score
        raise RuntimeError("Poker Score Detector Error")

### Entity
@dataclass # decorator to add __init__, __repr__, __eq__
class Player:
    name: str
    money: int

CAT_NAMES = {
    Score.NO_PAIR: "High Card",
    Score.PAIR: "One Pair",
    Score.TWO_PAIR: "Two Pair",
    Score.TRIPS: "Three of a Kind",
    Score.STRAIGHT: "Straight",
    Score.FULL_HOUSE: "Full House",
    Score.FLUSH: "Flush",
    Score.QUADS: "Four of a Kind",
    Score.STRAIGHT_FLUSH: "Straight Flush"
}

def fmt_card(c):
    return f"{Card.RANKS[c.rank]}{Card.SUITS[c.suit]}"

def fmt_cards(cs): 
    return " ".join(fmt_card(c) for c in sorted(cs, key=int, reverse=True))

def print_state(player, pot, street):
    print(f"---{street}---\n Your chips: [{player.money}]\n Pot: [{pot}]\n-------------")

### Bet/Raise
MIN_BET = 5
ANTE = 1

def ask_int(prompt):    # get user input
    s = input(prompt).strip()
    if s == "": 
        return None
    if s.isdigit(): 
        return int(s)
    try: 
        return int(s)
    except: 
        return None
    
def ask_bet_amount(max_amt, min_amt):
    while True:
        v = ask_int(f"Enter your bet amount ({min_amt} - {max_amt}): ")
        if v is None:
            print("Please enter an integer amount.")
            continue
        if v < min_amt:
            print(f"The bet cannot be lower than the minimum amount ({min_amt}).")
            continue
        if v > max_amt:
            print(f"The bet cannot exceed your remaining chips ({max_amt}).")
            continue
        return v

def ask_raise_size(max_amt, min_raise):
    while True:
        v = ask_int(f"Enter your raise size (excluding the call amount), minimum {min_raise}, maximum {max_amt}: ")
        if v is None:
            print("Please enter an integer amount.")
            continue
        if v < min_raise:
            print(f"The raise size cannot be smaller than {min_raise}.")
            continue
        if v > max_amt:
            print(f"The raise size cannot exceed your remaining chips ({max_amt}).")
            continue
        return v

def betting_round(active_players, pot):
    contrib = {p.name: 0 for p in active_players}   # bet amount in current round
    opened = False  # is someone opened(start bet)
    last_raise = MIN_BET    # init last raise

    actor = 0  # actor index init

    while len(active_players) > 1:
        player = active_players[actor]
        to_call = max(contrib.values()) - contrib[player.name]  # amount to call
        stack = player.money    # player stack

        print(f"{player.name} turn. To call: {to_call}. Stack: {stack}")
        # --------------------华丽的分割线-----------------------------
        # --- 处理玩家行动 ---
        if to_call == 0 and not opened:
            action = input("[check/bet]: ").strip().lower()
            if action == "check":
                print(f"{player.name} checks.")
            elif action == "bet":
                amt = ask_bet_amount(max_amt=stack, min_amt=MIN_BET)
                contrib[player.name] += amt
                pot += amt
                opened = True
                last_raise = amt
                last_aggressor = player
            else:
                print("Invalid input.")
        else:
            # 有下注要跟
            action = input("[fold/call/raise]: ").strip().lower()
            if action == "fold":
                print(f"{player.name} folds.")
                active_players.remove(player)
                if len(active_players) == 1:
                    winner = active_players[0]
                    print(f"{winner.name} wins the pot!")
                    return pot, winner
            elif action == "call":
                pay = min(to_call, stack)
                contrib[player.name] += pay
                pot += pay
            elif action == "raise":
                raise_amt = ask_raise_size(max_amt=stack - to_call, min_raise=last_raise)
                pay = to_call + raise_amt
                contrib[player.name] += pay
                pot += pay
                last_raise = raise_amt
                last_aggressor = player

        # 检查是否所有玩家投入额相等（行动完成）
        if len(set(contrib[p.name] for p in active_players)) == 1 and opened:
            break

        # 下一位玩家
        actor = (actor + 1) % len(active_players)

    return pot, None  # 若无人弃牌，返回 None 表示继续下一街

### prompt
def prompt_builder(
    street: str,
    hole: List[Card],
    board: List[Card],
    stack: int,
    pot: int,
    others: List[Player]
) -> str:
    hole_txt = fmt_cards(hole) if hole else "(unknown)"
    board_txt = fmt_cards(board) if board else "(no board)"
    others_txt = "\n".join([f"  - {p.name}: {p.money} chips" for p in others]) or "(no opponents)"

    prompt = f"""You are a poker decision agent. 
Game info (Texas Hold'em, heads-up or multiway agnostic for now):

Current state:
- Street: {street}
- Pot size: {pot}
- Your stack: {stack}
- Your hole cards: {hole_txt}
- Community board: {board_txt}
- Other players:
{others_txt}

Please decide your next action.

Only reply with a SINGLE JSON object on ONE LINE following this schema:
{{"action": "check|bet|call|raise|fold", "amount": <integer, use 0 for check/fold/call>}}

Rules:
- If you choose "check" or "fold", set "amount"=0.
- If you choose "call", set "amount"=0 (engine will compute the exact call amount).
- If you choose "bet" or "raise", set "amount" to a positive integer for your desired total put this turn.
- Do NOT include any explanation, reasoning, or extra text. Output JSON only.

Now output your decision JSON:
"""
    return prompt

if __name__ == '__main__':
    # d=Deck()
    # print(d.cards)
    # print(d.pop_cards(3))
    # print(d.cards)
    # cards = [Card(10,0), Card(13,1), Card(7,2), Card(11,3), Card(10,1),Card(9,0), Card(8,0)]
    # ch=CardsHelper(cards)
    # print(ch._get_straight(ch._sorted))
    # t = SimplePlayer('test', 100)
    # print_state(t, 100, 'PreFlop')
    prompt = prompt_builder("Preflop", 
                            [Card(14,1), Card(14,2)], 
                            [],
                            100,
                            2,
                            [Player('alice', 100)])
    resp = llm.invoke(prompt)
    print(resp.content) # {"action": "raise", "amount": 6}
