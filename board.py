from typing import Dict, List, Tuple

from state import MIN_BET, CAT_NAMES_HOLDEM
from agent import agent_policy
from entities import Card, Deck, Score, Player, PokerScoreDetector, fmt_cards

def fmt_board(board: List['Card']) -> str:
    return fmt_cards(board) if board else "(null)"

def ask_int(prompt):
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

def betting_round(
    active_players: List['Player'],
    pot: int,
    holes: Dict[str, List['Card']],
    board: List['Card'],
    street: str,
    human_name: str,
    agent_names: List[str],
    agent_complete
):
    contrib = {p.name: 0 for p in active_players}
    opened = False
    last_raise = MIN_BET
    actor = 0
    pending = set(p.name for p in active_players)
    name_order = [p.name for p in active_players]

    MAX_ITER = 600
    loops = 0

    def reset_pending_after_raise(raiser_name: str):
        nonlocal pending
        pending = set(p.name for p in active_players if p.name != raiser_name)

    def stacks_snapshot() -> Dict[str, int]:
        return {p.name: p.money for p in active_players}

    def print_stacks_and_pot():
        items = [f"{p.name}:{p.money}" for p in active_players]
        print("Stacks → " + " | ".join(items) + f" | Pot:{pot}")

    while len(active_players) > 1:
        loops += 1
        if loops > MAX_ITER:
            print("Safety break: too many iterations, forcing round end.")
            break
        if not pending:
            break
        if actor >= len(active_players):
            actor = 0

        player = active_players[actor]
        name = player.name

        max_in_round = max(contrib[nm] for nm in name_order) if active_players else 0
        to_call = max_in_round - contrib[name]
        stack = player.money

        if name == human_name:
            hole_view = fmt_cards(holes[name])
            print(f"{name} turn, hold[{hole_view}]. To call: {to_call}. Stack: {stack}")

        if sum(1 for p in active_players if p.money > 0) < 2 and to_call == 0 and not opened:
            print('-----------------------------------------------------------')
            return pot, None

        if name == human_name:
            if to_call == 0:
                action = input("[check/bet/all-in]: ").strip().lower()
                desired_amt = 0
            else:
                action = input(f"[fold/call/raise/all-in] (must call {to_call} to stay): ").strip().lower()
                desired_amt = 0
        else:
            stacks_now = stacks_snapshot()
            decision = agent_policy(
                agent_name=name,
                street=street,
                holes=holes,
                board=board,
                stacks=stacks_now,
                pot=pot,
                order=name_order,
                to_call_for_me=to_call,
                opened=opened,
                last_raise=last_raise,
                min_bet=MIN_BET,
                agent_complete=agent_complete,
            )
            action = decision["action"]
            desired_amt = int(decision.get("amount", 0))

        if to_call == 0 and not opened:
            if action == "check":
                if name == human_name:
                    print(f"{name} checks.")
                else:
                    print(f"{name} checks.")
                    print_stacks_and_pot()
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

            elif action == "bet":
                amt = desired_amt if name in agent_names else ask_bet_amount(max_amt=stack, min_amt=MIN_BET)
                if amt < MIN_BET or amt > stack:
                    if name == human_name:
                        print("Invalid bet size.")
                        continue
                    else:
                        print(f"{name} Invalid bet size. (auto fallback to check)")
                        print_stacks_and_pot()
                        pending.discard(name)
                        actor = (actor + 1) % len(active_players)
                        continue
                player.money -= amt
                contrib[name] += amt
                pot += amt
                opened = True
                last_raise = amt
                reset_pending_after_raise(name)
                print(f"{name} bets {amt}.")
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            elif action in ("all-in", "allin", "all in"):
                if stack <= 0:
                    if name == human_name:
                        print("You have no chips.")
                    else:
                        print(f"{name} has no chips.")
                        print_stacks_and_pot()
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue
                amt = stack
                player.money = 0
                contrib[name] += amt
                pot += amt
                opened = True
                last_raise = max(last_raise, amt)
                reset_pending_after_raise(name)
                print(f"{name} all-in for {amt}.")
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            else:
                if name == human_name:
                    print("Invalid input.")
                else:
                    print(f"{name} Invalid input. (auto fallback to check)")
                    print_stacks_and_pot()
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

        else:
            if action == "fold":
                print(f"{name} folds.")
                if name != human_name:
                    print_stacks_and_pot()
                pending.discard(name)
                del contrib[name]
                active_players.remove(player)
                name_order.remove(name)
                if len(active_players) == 1:
                    return pot, active_players[0]
                if actor >= len(active_players):
                    actor = 0
                continue

            elif action == "call":
                pay = min(to_call, stack)
                player.money -= pay
                contrib[name] += pay
                pot += pay
                print(f"{name} calls {pay}.")
                if name != human_name:
                    print_stacks_and_pot()
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

            elif action == "raise":
                max_raise_cap = max(0, stack - to_call)
                raise_amt = desired_amt - to_call if name in agent_names else ask_raise_size(max_amt=stack - to_call, min_raise=last_raise)
                if raise_amt < last_raise or raise_amt > max_raise_cap:
                    if stack >= to_call and to_call > 0:
                        pay = to_call
                        player.money -= pay
                        contrib[name] += pay
                        pot += pay
                        print(f"{name} invalid raise -> fallback to call {pay}.")
                        if name != human_name:
                            print_stacks_and_pot()
                        pending.discard(name)
                        actor = (actor + 1) % len(active_players)
                        continue
                    else:
                        print(f"{name} invalid raise -> fallback to fold.")
                        if name != human_name:
                            print_stacks_and_pot()
                        pending.discard(name)
                        del contrib[name]
                        active_players.remove(player)
                        name_order.remove(name)
                        if len(active_players) == 1:
                            return pot, active_players[0]
                        if actor >= len(active_players):
                            actor = 0
                        continue

                pay = to_call + raise_amt
                player.money -= pay
                contrib[name] += pay
                pot += pay
                last_raise = raise_amt
                opened = True
                reset_pending_after_raise(name)
                print(f"{name} raises to {contrib[name]}.")
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            elif action in ("all-in", "allin", "all in"):
                if stack <= 0:
                    if name == human_name:
                        print("You have no chips.")
                    else:
                        print(f"{name} has no chips.")
                        print_stacks_and_pot()
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue
                pay = stack
                raise_amt = max(0, pay - to_call)
                player.money = 0
                contrib[name] += pay
                pot += pay
                print(f"{name} all-in for {pay}.")
                if raise_amt >= last_raise and to_call > 0:
                    last_raise = raise_amt
                    opened = True
                    reset_pending_after_raise(name)
                else:
                    pending.discard(name)
                if name != human_name:
                    print_stacks_and_pot()
                actor = (actor + 1) % len(active_players)
                continue

            else:
                if stack >= to_call and to_call > 0:
                    pay = to_call
                    player.money -= pay
                    contrib[name] += pay
                    pot += pay
                    if name == human_name:
                        print(f"{name} Invalid input. (auto fallback to call {pay}).")
                    else:
                        print(f"{name} Invalid input. (auto fallback to call {pay}).")
                        print_stacks_and_pot()
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                else:
                    if name == human_name:
                        print(f"{name} Invalid input. (auto fallback to fold).")
                    else:
                        print(f"{name} Invalid input. (auto fallback to fold).")
                        print_stacks_and_pot()
                    pending.discard(name)
                    del contrib[name]
                    active_players.remove(player)
                    name_order.remove(name)
                    if len(active_players) == 1:
                        return pot, active_players[0]
                    if actor >= len(active_players):
                        actor = 0
                continue

    print('-----------------------------------------------------------')
    return pot, None

def play_hand(
    human_name: str,
    agent_names: List[str],
    players: List['Player'],
    agent_complete,   # Callable[[str], str]
    lowest_rank: int = 2,
    reveal_bots_at_showdown: bool = False, 
) -> bool:

    def settle_early(winner, pot) -> bool:
        if winner:
            print(f"{winner.name} win the pot {pot}.")
            winner.money += pot
            return True
        return False

    allow = set([human_name] + list(agent_names))
    active_players = [p for p in players if p.name in allow and p.money > 0]
    if len(active_players) < 2:
        print("player not enough")
        return False

    pot = 0
    for p in list(active_players):
        if p.money > 0:
            ante_amt = min(1, p.money)
            p.money -= ante_amt
            pot += ante_amt

    deck = Deck(lowest_rank=lowest_rank)
    detector = PokerScoreDetector()

    holes: Dict[str, List[Card]] = {p.name: deck.pop_cards(2) for p in active_players}
    board: List[Card] = []

    print(f"Player: {', '.join(p.name for p in active_players)}  | pot: {pot}")
    for p in active_players:
        if p.name == human_name:
            print(f"{p.name} holes: {fmt_cards(holes[p.name])}")

    # Preflop
    pot, winner = betting_round(
        active_players, pot, holes, board, "Preflop",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # Flop
    board += deck.pop_cards(3)
    print("Phase: Flop"); print("Borad: ", fmt_board(board))
    pot, winner = betting_round(
        active_players, pot, holes, board, "Flop",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # Turn
    board += deck.pop_cards(1)
    print("Phase: Turn"); print("Borad: ", fmt_board(board))
    pot, winner = betting_round(
        active_players, pot, holes, board, "Turn",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # River
    board += deck.pop_cards(1)
    print("Phase: River"); print("Borad: ", fmt_board(board))
    pot, winner = betting_round(
        active_players, pot, holes, board, "River",
        human_name, agent_names, agent_complete
    )
    if settle_early(winner, pot): return True

    # Showdown
    print("—— showdown ——")
    for p in active_players:
        if p.name == human_name or reveal_bots_at_showdown:
            print(f"{p.name} holes: {fmt_cards(holes[p.name])}")
        else:
            print(f"{p.name} holes: ?? ??")
    print("Board: ", fmt_board(board))

    winners, scores = showdown(detector, active_players, holes, board)
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