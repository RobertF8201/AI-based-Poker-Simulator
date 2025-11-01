from collections import deque

from board import play_hand
from entities import Player
from agent import expert_agent
from pipeline import ChatAnthropic

from ui_cli import (
    banner_hand, show_seats, stacks_pot_table,
    info_line, hr, seats_positions_line,
    ask_report, ask_continue
)

CLAUDE_API_KEY = "sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI"

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key=CLAUDE_API_KEY,
    base_url="https://yinli.one",   
    temperature=0,
)

def pretty_positions_line(players_order):
    return seats_positions_line(players_order)

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
        banner_hand(hand_no)

        players_order = list(dq)
        show_seats(players_order)

        play_hand(
            human_name="You",
            agent_names=["Bot1", "Bot2", "Bot3"],
            players=players_order,
            agent_complete=llm.complete,
            lowest_rank=2,
        )

        hr()
        info_line("=== Final stacks ===", "bold")
        stacks_pot_table(base_players, pot=0)

        if ask_report():
            info_line("\n=== Sending last hand record for analysis... ===\n", "dim")
            analysis = expert_agent(agent_complete=llm.complete, stream=False, max_tokens=1800)
            info_line("\n=== AI Review Report ===\n", "bold")
            print(analysis if analysis else "[Empty response]")

        if not ask_continue():
            info_line("Bye! 👋", "green")
            break

        dq.rotate(-1)
        hand_no += 1

if __name__ == "__main__":
    game_loop()
