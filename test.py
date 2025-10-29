from holdem import PokerScoreDetector, Card, Player, showdown, play_hand_multi
from typing import List, Dict


def test_showdown_fc():
    detector = PokerScoreDetector()

    # 模拟玩家
    alice = Player("Alice", 100)
    bob = Player("Bob", 100)
    charlie = Player("Charlie", 100)
    active_players = [alice, bob, charlie]

    # 模拟手牌（♠♣♦♥ 分别是 0,1,2,3，对应 card.py）
    # Alice: A♠ K♠   （同花色）
    # Bob:   Q♦ Q♣
    # Charlie: 9♥ 9♠
    holes: Dict[str, List[Card]] = {
        "Alice":   [Card(14, 0), Card(13, 0)],
        "Bob":     [Card(12, 2), Card(12, 1)],
        "Charlie": [Card(9, 3),  Card(9, 0)],
    }

    # 公共牌 board: 10♠, J♠, Q♠, 2♦, 7♥
    board = [Card(10, 0), Card(11, 0), Card(9, 2), Card(2, 2), Card(7, 3)]

    # 调用 showdown
    winners, scores = showdown(detector, active_players, holes, board)

    # 输出结果
    if len(winners) == 1:
        print(f"{winners[0].name} wins!")
    else:
        names = ", ".join(p.name for p in winners)
        print(f"Split pot: {names}")

    # 打印每位玩家的牌型
    for p in active_players:
        s = scores[p.name]
        cards_text = " ".join(f"{Card.RANKS[c.rank]}{Card.SUITS[c.suit]}" for c in s.cards)
        print(f"{p.name} ({cards_text}) -> category={s.category}, strength={s.strength}")

import random
def test_play_hand_multi():
    players = [
        Player("Alice", 100),
        Player("Bob", 100),
        Player("Charlie", 100),
    ]
    ok = play_hand_multi(players, lowest_rank=2)
    print("Play hand finished:", ok)
    for p in players:
        print(f"{p.name} money: {p.money}")

if __name__ == "__main__":
    test_play_hand_multi()
