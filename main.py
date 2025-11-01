from collections import deque

from board import play_hand
from entities import Player
from agent import expert_agent
from pipeline import ChatAnthropic

from ui_cli import (
    banner_hand, show_seats, stacks_pot_table,
    info_line, hr, seats_positions_line,
    ask_report, ask_continue, render_ai_review_report,
    ask_num_players, ask_starting_stack, 
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
    total_players = ask_num_players(min_players=2, max_players=9, default=4)
    starting_stack = ask_starting_stack(default_stack=100)

    base_players = [Player("You", starting_stack)]
    for i in range(1, total_players):
        base_players.append(Player(f"Bot{i}", starting_stack))

    dq = deque(base_players)
    hand_no = 1

    while True:
        banner_hand(hand_no)

        players_order = list(dq)
        show_seats(players_order)

        dynamic_agent_names = [p.name for p in players_order if p.name != "You"]

        play_hand(
            human_name="You",
            agent_names=dynamic_agent_names,
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
            render_ai_review_report(analysis if analysis else "[Empty response]")


        if not ask_continue():
            info_line("Bye! 👋", "green")
            break

        dq.rotate(-1)
        hand_no += 1

if __name__ == "__main__":
    game_loop()
