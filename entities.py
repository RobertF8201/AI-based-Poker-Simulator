import random
from state import RANKS, SUITS
from dataclasses import dataclass

class Card:
    def __init__(self, rank: int, suit: int):
        if rank not in RANKS or suit not in SUITS:
            raise ValueError("Invalid card")
        self._value = (rank<<2)+suit

    @property
    def rank(self): return self._value >> 2

    @property
    def suit(self): return self._value & 3

    def __int__(self): return self._value    # int(card)

    def __lt__(self, other): return int(self) < int(other)  # card1 < card2

    def __repr__(self): return f"{RANKS[self.rank]}{SUITS[self.suit]}"    # print(card)

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

@dataclass # decorator to add __init__, __repr__, __eq__
class Player:
    name: str
    money: int

def fmt_cards(cs):
    f = lambda c: f"{RANKS[c.rank]}{SUITS[c.suit]}"
    return " ".join(f(c) for c in sorted(cs, key=int, reverse=True))


def print_state(player, pot, street):
    print(f"---{street}---\n Your chips: [{player.money}]\n Pot: [{pot}]\n-------------")
