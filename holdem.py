import random

class Card:
    RANKS = {2:"2",3:"3",4:"4",5:"5",6:"6",7:"7",8:"8",9:"9",10:"10",11:"J",12:"Q",13:"K",14:"A"}
    SUITS = {0:"♠",1:"♣",2:"♦",3:"♥"}
    def __init__(self, rank: int, suit: int):
        if rank not in Card.RANKS or suit not in Card.SUITS:
            raise ValueError("Invalid card")
        # to get rank and suit use: 
        # rank = value >> 2
        # suit = value & 3(11)
        self.value = (rank<<2)+suit
        self.rank = self.value>>2 
        self.suit = self.value&2

    def __int__(self): return self.value    # int(card)

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

    # ----------------华丽的分割线-----------------------
    def straight_flush(self):
        suits = {}
        for c in self._sorted:
            suits.setdefault(c.suit, []).append(c)
        for s_cards in suits.values():
            if len(s_cards) >= 5:
                # 在同花桶内按 rank 排序（忽略 suit）
                s_cards.sort(key=lambda c: c.rank, reverse=True)
                st = self._get_straight(s_cards)
                if st:
                    return st
        return None

    def quads(self):
        q = self._x_sorted_list(4)
        return (self._merge(q[0])[:5]) if q else None

    def flush(self):
        suits = {}
        for c in self._sorted:
            suits.setdefault(c.suit, []).append(c)
        for s_cards in suits.values():
            if len(s_cards) >= 5:
                # 同花内仅按 rank 取前 5
                s_cards.sort(key=lambda c: c.rank, reverse=True)
                return s_cards[:5]
        return None

    def full_house(self):
        trips = self._x_sorted_list(3)
        pairs = self._x_sorted_list(2)
        if trips and (len(trips) >= 2 or pairs):
            if len(trips) >= 2:
                return (self._merge(trips[0] + trips[1][:2])[:5])
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

if __name__ == '__main__':
    d=Deck()
    # print(d.cards)
    # print(d.pop_cards(3))
    # print(d.cards)
    cards = [Card(10,0), Card(13,1), Card(7,2), Card(11,3), Card(10,1),Card(9,0), Card(8,0)]
    ch=CardsHelper(cards)
    print(ch._get_straight(ch._sorted))