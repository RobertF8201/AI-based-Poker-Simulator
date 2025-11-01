from board import play_hand
from entities import Player
from collections import deque
from agent import expert_agent
from pipeline import ChatAnthropic

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key="sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI",
    base_url="https://yinli.one",
    temperature=0,
)

def pretty_positions_line(players_order):
    n = len(players_order)
    labels = []
    for i, p in enumerate(players_order):
        if n == 2:
            lab = "BTN/SB" if i == 0 else "BB"
        else:
            if i == 0:
                lab = "BTN"
            elif i == 1:
                lab = "SB"
            elif i == 2:
                lab = "BB"
            else:
                lab = "UTG" if i == 3 else f"UTG+{i-3}" if i >= 4 else "CO" 
        labels.append(f"{p.name}({lab})")
    return " | ".join(labels)

def one_hand():
    players = [
        Player("You", 100),
        Player("Bot1", 100),
        Player("Bot2", 100),
        Player("Bot3", 100),
    ]

    play_hand(
        human_name="You",
        agent_names=["Bot1", "Bot2", "Bot3"],
        players=players,
        agent_complete=llm.complete,
        lowest_rank=2,
    )

    print("\n=== Final stacks ===")
    for p in players:
        print(f"{p.name}: {p.money}")

    is_report = input("Do you want to generate report for this hand?(Yes/No)\n").strip().lower()
    if is_report == "yes":
        print("\n=== Sending last hand record for analysis... ===\n")
        analysis = expert_agent(agent_complete=llm.complete, stream=False, max_tokens=1800)
        print("\n=== AI Review Report ===\n")
        print(analysis)


def pretty_positions_line(players_order):
    n = len(players_order)
    labels = []
    for i, p in enumerate(players_order):
        if n == 2:
            lab = "BTN/SB" if i == 0 else "BB"
        else:
            if i == 0:
                lab = "BTN"
            elif i == 1:
                lab = "SB"
            elif i == 2:
                lab = "BB"
            else:
                lab = "UTG" if i == 3 else f"UTG+{i-3}" if i >= 4 else "CO" 
        labels.append(f"{p.name}({lab})")
    return " | ".join(labels)

def game_loop():
    base_players = [
        Player("You", 100),
        Player("Bot1", 100),
        Player("Bot2", 100),
        Player("Bot3", 100),
    ]

    dq = deque(base_players)
    hand_no = 1

    while True:
        print(f"\n=== Hand #{hand_no} ===")

        players_order = list(dq) 
        print("Seats & Positions → " + pretty_positions_line(players_order))

        play_hand(
            human_name="You",
            agent_names=["Bot1", "Bot2", "Bot3"],
            players=players_order,      
            agent_complete=llm.complete,
            lowest_rank=2,
        )

        print("\n=== Final stacks ===")
        for p in base_players:
            print(f"{p.name}: {p.money}")

        is_report = input("\nDo you want to generate report for this hand? (Yes/No)\n").strip().lower()
        if is_report in ("y", "yes"):
            print("\n=== Sending last hand record for analysis... ===\n")
            analysis = expert_agent(agent_complete=llm.complete, stream=False, max_tokens=1800)
            print("\n=== AI Review Report ===\n")
            print(analysis if analysis else "[Empty response]")

        cont = input("\nDo you want to continue playing? (Yes/No)\n").strip().lower()
        if cont not in ("y", "yes"):
            print("Bye! 👋")
            break

        dq.rotate(-1)
        hand_no += 1


if __name__ == "__main__":
    game_loop()
