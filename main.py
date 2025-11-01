from board import play_hand
from entities import Player
from agent import expert_agent
from pipeline import ChatAnthropic

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key="sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI",
    base_url="https://yinli.one",
    temperature=0,
)

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


if __name__ == "__main__":
    one_hand()
