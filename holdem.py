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

class PokerScoreDetector:
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

def betting_round(active_players, pot, holes):
    contrib = {p.name: 0 for p in active_players}   # bet amount in current round
    opened = False  # is someone opened(start bet)
    last_raise = MIN_BET    # init last raise

    actor = 0  # actor index init
    pending = set(p.name for p in active_players)

    def reset_pending_after_raise(raiser_name: str):
        nonlocal pending
        pending = set(p.name for p in active_players if p.name != raiser_name)

    # all-in/only 1 player has chips
    can_bet_cnt = sum(1 for p in active_players if p.money > 0)
    if can_bet_cnt < 2:
        print('-----------------------------------------------------------')
        return pot, None

    while len(active_players) > 1:
        if not pending:
            break
        
        if actor >= len(active_players):
            actor = 0

        player = active_players[actor]
        name = player.name

        max_in_round = max(contrib[p.name] for p in active_players) if active_players else 0
        to_call = max_in_round - contrib[player.name]  # amount to call
        stack = player.money    # player stack

        print(f"{player.name} turn, hold[{fmt_cards(holes[player.name])}]. To call: {to_call}. Stack: {stack}") 

        can_bet_cnt = sum(1 for p in active_players if p.money > 0)
        if can_bet_cnt < 2 and to_call == 0 and not opened:
            print('-----------------------------------------------------------')
            return pot, None

        # if no one opened
        if to_call == 0 and not opened:
            action = input("[check/bet/all-in]: ").strip().lower()
            if action == "check":
                print(f"{player.name} checks.")
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue
            elif action == "bet":
                amt = ask_bet_amount(max_amt=stack, min_amt=MIN_BET)
                if amt < MIN_BET or amt > stack:
                    print("Invalid bet size.")
                    continue
                player.money -= amt   
                contrib[player.name] += amt
                pot += amt
                opened = True
                last_raise = amt
                reset_pending_after_raise(name) # reset 
                actor = (actor + 1) % len(active_players)
                continue
            elif action in ("allin", "all-in", "all in"):
                amt = stack
                if amt <= 0:
                    print("You have no chips.")
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue
                player.money = 0
                contrib[name] += amt
                pot += amt
                opened = True
                last_raise = max(last_raise, amt) 
                reset_pending_after_raise(name)
                actor = (actor + 1) % len(active_players)
                continue
            else:
                print("Invalid input.")
                continue  
        else:   # someone opened
            action = input("[fold/call/raise]: ").strip().lower()
            if action == "fold":
                print(f"{name} folds.")
                pending.discard(name)
                del contrib[name]
                active_players.remove(player)
                if len(active_players) == 1:
                    winner = active_players[0]
                    return pot, winner
                if actor >= len(active_players):
                    actor = 0
                continue
            elif action == "call":
                pay = min(to_call, stack)
                if pay < 0:
                    print("Invalid call.")
                    continue
                player.money -= pay  
                contrib[player.name] += pay
                pot += pay
                pending.discard(name)  
                actor = (actor + 1) % len(active_players)
                continue
            elif action == "raise":
                max_raise_cap = max(0, stack - to_call)
                if max_raise_cap < last_raise:
                    print("You don't have enough chips to raise; try call/fold.")
                    continue
                raise_amt = ask_raise_size(max_amt=stack - to_call, min_raise=last_raise)
                if raise_amt < last_raise or raise_amt > max_raise_cap:
                    print("Invalid raise size.")
                    continue
                
                pay = to_call + raise_amt
                player.money -= pay
                contrib[player.name] += pay
                pot += pay
                last_raise = raise_amt
                opened = True
                reset_pending_after_raise(name) # reset 
                actor = (actor + 1) % len(active_players)
                continue
            elif action in ("allin", "all-in", "all in"):
                # all in, pay = stack
                if stack <= 0:
                    print("You have no chips.")
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue

                pay = stack
                raise_amt = max(0, pay - to_call)  # raise amount could be 0 or not enough
                player.money = 0
                contrib[name] += pay
                pot += pay

                # check is reopen action
                if raise_amt >= last_raise and to_call > 0:
                    last_raise = raise_amt
                    opened = True
                    reset_pending_after_raise(name)
                else:
                    pending.discard(name)

                actor = (actor + 1) % len(active_players)
                continue
            else:
                print("Invalid input.")
                continue  
    
    print('-----------------------------------------------------------')

    return pot, None  # no one win, go to next street

def showdown(detector, 
             active_players: List['Player'], 
             holes: Dict[str, List['Card']], 
             board: List['Card']) -> Tuple[List['Player'], Dict[str, 'Score']]:

    if not active_players:
        return [], {}

    # calculate active player's holes + board
    scores: Dict[str, 'Score'] = {}
    for p in active_players:
        hole = holes.get(p.name, [])
        scores[p.name] = detector.get_score(hole + board)

    # find current best player
    best_player = active_players[0]
    for p in active_players[1:]:
        if scores[p.name].cmp(scores[best_player.name]) > 0:
            best_player = p

    # share the pot
    winners = [p for p in active_players if scores[p.name].cmp(scores[best_player.name]) == 0]
    return winners, scores

def fmt_board(board: List['Card']) -> str:
    return fmt_cards(board) if board else "(null)"

CAT_NAMES_HOLDEM = [
    "High Card",
    "One Pair",
    "Two Pair",
    "Three of a Kind",
    "Straight",
    "Full House",
    "Flush",
    "Four of a Kind",
    "Straight Flush"
]

def play_hand_multi(active_players: List['Player'], lowest_rank: int = 2) -> bool:

    def win(winner, pot):
        if winner:
            print(f"{winner.name} win the pot {pot}.")
            winner.money += pot
            return True
        return False
        
    # player with no money
    active_players = [p for p in active_players if p.money > 0]
    if len(active_players) < 2:
        print("player not enough")
        return False

    pot = 0
    # ante(1 for each)
    for p in list(active_players):
        if p.money <= 0:
            continue
        ante_amt = min(1, p.money)
        p.money -= ante_amt
        pot += ante_amt

    deck = Deck(lowest_rank=lowest_rank)
    detector = PokerScoreDetector()

    holes: Dict[str, List[Card]] = {}
    for p in active_players:
        holes[p.name] = deck.pop_cards(2)

    board: List[Card] = []

    print(f"Player: {', '.join(p.name for p in active_players)}  | pot: {pot}")
    for p in active_players:
        print(f"{p.name} holes: {fmt_cards(holes[p.name])}")

    # Preflop
    pot, winner = betting_round(active_players, pot, holes)
    if win(winner, pot):
            return True
    # Flop
    board += deck.pop_cards(3)
    print("Phase: Flop")
    print("Borad: ", fmt_board(board))
    pot, winner = betting_round(active_players, pot, holes)
    if win(winner, pot):
            return True
    # Turn
    board += deck.pop_cards(1)
    print("Phase: Turn")
    print("Borad: ", fmt_board(board))
    pot, winner = betting_round(active_players, pot, holes)
    if win(winner, pot):
            return True

    # River
    board += deck.pop_cards(1)
    print("Phase: River")
    print("Borad: ", fmt_board(board))
    pot, winner = betting_round(active_players, pot, holes)
    if win(winner, pot):
            return True
    
    # —— showdown ——
    print("—— showdown ——")
    for p in active_players:
        print(f"{p.name} holes: {fmt_cards(holes[p.name])}")
    print("Board: ", fmt_board(board))

    winners, scores = showdown(detector, active_players, holes, board)

    # show category
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
    # prompt = prompt_builder("Preflop", 
    #                         [Card(14,1), Card(14,2)], 
    #                         [],
    #                         100,
    #                         2,
    #                         [Player('alice', 100)])
    # resp = llm.invoke(prompt)
    # print(resp.content) # {"action": "raise", "amount": 6}
    pass
