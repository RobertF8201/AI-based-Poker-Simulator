from typing import Dict, List, Tuple, Optional

from logger import HandLogger
from agent import player_agent
from state import MIN_BET, CAT_NAMES_HOLDEM
from entities import Card, Deck, Score, Player, PokerScoreDetector, fmt_cards

from ui_cli import (
    stacks_pot_table, info_line, show_board, show_hole,
    ask_action_when_to_call0, ask_action_when_to_call_gt0,
    ask_bet_amount as ui_ask_bet_amount,
    ask_raise_size as ui_ask_raise_size,
    human_turn_header, hr,
)

def fmt_board(board: List["Card"]) -> str:
    return fmt_cards(board) if board else "(null)"

# def ask_int(prompt):
#     try:
#         s = input(prompt).strip()
#         if s == "":
#             return None
#         return int(s)
#     except Exception:
#         return None

def ask_bet_amount(max_amt, min_amt):
    while True:
        v = ui_ask_bet_amount(max_amt, min_amt)
        if v is None:
            info_line("Please enter an integer amount.", "red")
            continue
        if v < min_amt:
            info_line(f"The bet cannot be lower than the minimum amount ({min_amt}).", "red")
            continue
        if v > max_amt:
            info_line(f"The bet cannot exceed your remaining chips ({max_amt}).", "red")
            continue
        return v

def ask_raise_size(max_amt, min_raise):
    while True:
        v = ui_ask_raise_size(max_amt, min_raise)
        if v is None:
            info_line("Please enter an integer amount.", "red")
            continue
        if v < min_raise:
            info_line(f"The raise size cannot be smaller than {min_raise}.", "red")
            continue
        if v > max_amt:
            info_line(f"The raise size cannot exceed your remaining chips ({max_amt}).", "red")
            continue
        return v

def showdown(
    detector,
    active_players: List["Player"],
    holes: Dict[str, List["Card"]],
    board: List["Card"],
) -> Tuple[List["Player"], Dict[str, "Score"]]:

    if not active_players:
        return [], {}

    scores: Dict[str, "Score"] = {}
    for p in active_players:
        hole = holes.get(p.name, [])
        scores[p.name] = detector.get_score(hole + board)

    best_player = active_players[0]
    for p in active_players[1:]:
        if scores[p.name].cmp(scores[best_player.name]) > 0:
            best_player = p

    winners = [
        p for p in active_players if scores[p.name].cmp(scores[best_player.name]) == 0
    ]
    return winners, scores

def betting_round(
    active_players, 
    pot, 
    holes, 
    board, 
    street,
    human_name, 
    agent_names, 
    agent_complete,
    logger: Optional[HandLogger] = None,
    initial_contrib: Optional[Dict[str,int]] = None,
    start_actor: int = 0,
    opened0: bool = False,
    last_raise0: int = MIN_BET
):
    contrib = initial_contrib if initial_contrib is not None else {p.name: 0 for p in active_players}
    opened = opened0
    last_raise = last_raise0
    actor = start_actor
    pending = set(p.name for p in active_players)
    name_order = [p.name for p in active_players]
    MAX_ITER = 600
    loops = 0

    def reset_pending_after_raise(raiser_name: str):
        nonlocal pending
        pending = set(p.name for p in active_players if p.name != raiser_name)

    def stacks_snapshot() -> Dict[str, int]:
        return {p.name: p.money for p in active_players}

    def print_stacks_and_pot(highlight: Optional[str] = None):
        stacks_pot_table(active_players, pot, highlight=highlight)

    while len(active_players) > 1:
        loops += 1
        if loops > MAX_ITER:
            info_line("Safety break: too many iterations, forcing round end.", "red")
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

        amt = 0
        pay = 0
        raise_amt = 0
        to_call_before = to_call
        stack_before = stack

        if name == human_name:
            hole_view = fmt_cards(holes[name])
            human_turn_header(name, hole_view, to_call, stack)

        # auto check
        if (
            sum(1 for p in active_players if p.money > 0) < 2
            and to_call == 0
            and not opened
        ):
            hr()
            if logger: logger.log_street_end(street, pot, contrib)
            return pot, None

        # action input
        if name == human_name:
            if to_call == 0:
                action = ask_action_when_to_call0(opened=opened)
                desired_amt = 0
            else:
                action = ask_action_when_to_call_gt0(to_call)
                desired_amt = 0
        else:
            stacks_now = stacks_snapshot()
            decision = player_agent(
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

        if to_call == 0 and opened and action == "bet":
            action = "raise"

        # action execution
        if to_call == 0 and not opened:
            if action == "check":
                if logger:
                    logger.log_action(street, name, "check",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=0, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} checks.", "cyan")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

            elif action == "bet":
                amt = desired_amt if name in agent_names else ask_bet_amount(max_amt=stack, min_amt=MIN_BET)
                if amt < MIN_BET or amt > stack:
                    if logger:
                        logger.log_action(street, name, "check",
                            to_call_before=to_call_before, stack_before=stack_before,
                            amount=0, stack_after=player.money,
                            pot_after=pot, contrib_after=contrib[name],
                            last_raise=last_raise, opened=opened)
                    info_line(f"{name} Invalid bet size. (auto fallback to check)", "red")
                    print_stacks_and_pot(highlight=name if name!=human_name else None)
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue
                player.money -= amt
                contrib[name] += amt
                pot += amt
                opened = True
                last_raise = amt
                reset_pending_after_raise(name)
                if logger:
                    logger.log_action(street, name, "bet",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=amt, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} bets {amt}.", "yellow")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                actor = (actor + 1) % len(active_players)
                continue

            elif action in ("all-in", "allin", "all in"):
                if stack <= 0:
                    if logger:
                        logger.log_action(street, name, "check",
                            to_call_before=to_call_before, stack_before=stack_before,
                            amount=0, stack_after=player.money,
                            pot_after=pot, contrib_after=contrib[name],
                            last_raise=last_raise, opened=opened)
                    info_line(f"{name} has no chips. (fallback to check)", "red")
                    print_stacks_and_pot(highlight=name if name!=human_name else None)
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
                if logger:
                    logger.log_action(street, name, "all-in",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=amt, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} all-in for {amt}.", "yellow")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                actor = (actor + 1) % len(active_players)
                continue

            else:
                if logger:
                    logger.log_action(street, name, "check",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=0, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} Invalid input. (auto fallback to check)", "red")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue
        else:
            if action == "check" and to_call == 0:
                if logger:
                    logger.log_action(street, name, "check",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=0, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} checks.", "cyan")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

            if action == "fold":
                if logger:
                    logger.log_action(street, name, "fold",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=0, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} folds.", "red")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                pending.discard(name)
                del contrib[name]
                active_players.remove(player)
                name_order.remove(name)
                if len(active_players) == 1:
                    if logger: logger.log_street_end(street, pot, contrib)
                    return pot, active_players[0]
                if actor >= len(active_players):
                    actor = 0
                continue

            elif action == "call":
                pay = min(to_call, stack)
                player.money -= pay
                contrib[name] += pay
                pot += pay
                if logger:
                    logger.log_action(street, name, "call",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=pay, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} calls {pay}.", "yellow")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                pending.discard(name)
                actor = (actor + 1) % len(active_players)
                continue

            elif action == "raise":
                max_raise_cap = max(0, stack - to_call)
                raise_amt = (
                    desired_amt - to_call
                    if name in agent_names
                    else ask_raise_size(max_amt=stack - to_call, min_raise=last_raise)
                )
                if raise_amt < last_raise or raise_amt > max_raise_cap:
                    if stack >= to_call and to_call > 0:
                        pay = to_call
                        player.money -= pay
                        contrib[name] += pay
                        pot += pay
                        if logger:
                            logger.log_action(street, name, "call",
                                to_call_before=to_call_before, stack_before=stack_before,
                                amount=pay, stack_after=player.money,
                                pot_after=pot, contrib_after=contrib[name],
                                last_raise=last_raise, opened=opened)
                        info_line(f"{name} invalid raise -> fallback to call {pay}.", "red")
                        print_stacks_and_pot(highlight=name if name!=human_name else None)
                        pending.discard(name)
                        actor = (actor + 1) % len(active_players)
                        continue
                    else:
                        if logger:
                            logger.log_action(street, name, "invalid-raise->fold",
                                to_call_before=to_call_before, stack_before=stack_before,
                                amount=0, stack_after=player.money,
                                pot_after=pot, contrib_after=contrib[name],
                                last_raise=last_raise, opened=opened)
                        info_line(f"{name} invalid raise -> fallback to fold.", "red")
                        print_stacks_and_pot(highlight=name if name!=human_name else None)
                        pending.discard(name)
                        del contrib[name]
                        active_players.remove(player)
                        name_order.remove(name)
                        if len(active_players) == 1:
                            if logger: logger.log_street_end(street, pot, contrib)
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
                if logger:
                    logger.log_action(street, name, "raise",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=pay, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} raises to {contrib[name]}.", "yellow")
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                actor = (actor + 1) % len(active_players)
                continue

            elif action in ("all-in", "allin", "all in"):
                if stack <= 0:
                    if logger:
                        logger.log_action(street, name, "invalid-all-in",
                            to_call_before=to_call_before, stack_before=stack_before,
                            amount=0, stack_after=player.money,
                            pot_after=pot, contrib_after=contrib[name],
                            last_raise=last_raise, opened=opened)
                    info_line(f"{name} has no chips.", "red")
                    print_stacks_and_pot(highlight=name if name!=human_name else None)
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                    continue

                pay = stack
                raise_amt = max(0, pay - to_call)
                player.money = 0
                contrib[name] += pay
                pot += pay
                if logger:
                    logger.log_action(street, name, "all-in",
                        to_call_before=to_call_before, stack_before=stack_before,
                        amount=pay, stack_after=player.money,
                        pot_after=pot, contrib_after=contrib[name],
                        last_raise=last_raise, opened=opened)
                info_line(f"{name} all-in for {pay}.", "yellow")
                if raise_amt >= last_raise and to_call > 0:
                    last_raise = raise_amt
                    opened = True
                    reset_pending_after_raise(name)
                else:
                    pending.discard(name)
                print_stacks_and_pot(highlight=name if name!=human_name else None)
                actor = (actor + 1) % len(active_players)
                continue

            else:
                if to_call == 0:
                    if logger:
                        logger.log_action(street, name, "check",
                            to_call_before=to_call_before, stack_before=stack_before,
                            amount=0, stack_after=player.money,
                            pot_after=pot, contrib_after=contrib[name],
                            last_raise=last_raise, opened=opened)
                    info_line(f"{name} Invalid input. (auto fallback to check).", "red")
                    print_stacks_and_pot(highlight=name if name!=human_name else None)
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                elif stack >= to_call:
                    pay = to_call
                    player.money -= pay
                    contrib[name] += pay
                    pot += pay
                    if logger:
                        logger.log_action(street, name, "call",
                            to_call_before=to_call_before, stack_before=stack_before,
                            amount=pay, stack_after=player.money,
                            pot_after=pot, contrib_after=contrib[name],
                            last_raise=last_raise, opened=opened)
                    info_line(f"{name} Invalid input. (auto fallback to call {pay}).", "red")
                    print_stacks_and_pot(highlight=name if name!=human_name else None)
                    pending.discard(name)
                    actor = (actor + 1) % len(active_players)
                else:
                    if logger:
                        logger.log_action(street, name, "fold",
                            to_call_before=to_call_before, stack_before=stack_before,
                            amount=0, stack_after=player.money,
                            pot_after=pot, contrib_after=contrib[name],
                            last_raise=last_raise, opened=opened)
                    info_line(f"{name} Invalid input. (auto fallback to fold).", "red")
                    print_stacks_and_pot(highlight=name if name!=human_name else None)
                    pending.discard(name)
                    del contrib[name]
                    active_players.remove(player)
                    name_order.remove(name)
                    if len(active_players) == 1:
                        if logger: logger.log_street_end(street, pot, contrib)
                        return pot, active_players[0]
                    if actor >= len(active_players):
                        actor = 0
                continue

    hr()
    if logger: logger.log_street_end(street, pot, contrib)
    return pot, None

def play_hand(
    human_name: str,
    agent_names: List[str],
    players: List["Player"],
    agent_complete,  # Callable[[str], str]
    lowest_rank: int = 2,
    logger: Optional[HandLogger] = HandLogger("hand_logs.jsonl")
) -> bool:

    def settle_early(winner, pot) -> bool:
        if winner:
            info_line(f"{winner.name} win the pot {pot}.", "bold green")
            winner.money += pot
            if logger and logger._data:
                logger.log_showdown([winner], pot, {}, CAT_NAMES_HOLDEM, holes, fmt_cards)
                logger.finish_hand(players)
                logger.dump()
            return True
        return False

    allow = set([human_name] + list(agent_names))
    active_players = [p for p in players if p.name in allow and p.money > 0]
    if len(active_players) < 2:
        info_line("player not enough", "red")
        return False

    pot = 0
    ante_by_player = {}
    # ── SB/BB ──
    n = len(active_players)
    if n == 2:
        sb_i, bb_i = 0, 1
    else:
        sb_i, bb_i = 1, 2 if n >= 3 else (0, 1)
    sb_i = sb_i % n
    bb_i = bb_i % n
    sb_player = active_players[sb_i]
    bb_player = active_players[bb_i]
    sb_amt = min(5, sb_player.money)
    bb_amt = min(10, bb_player.money)
    if sb_amt > 0:
        sb_player.money -= sb_amt
        pot += sb_amt
        ante_by_player[sb_player.name] = sb_amt
    if bb_amt > 0:
        bb_player.money -= bb_amt
        pot += bb_amt
        ante_by_player[bb_player.name] = ante_by_player.get(bb_player.name, 0) + bb_amt

    preflop_contrib = {p.name: 0 for p in active_players}
    preflop_contrib[sb_player.name] = sb_amt
    preflop_contrib[bb_player.name] = bb_amt
    if n <= 3:
        preflop_actor = 0
    else:
        preflop_actor = 3 % n

    deck = Deck(lowest_rank=lowest_rank)

    holes: Dict[str, List[Card]] = {p.name: deck.pop_cards(2) for p in active_players}
    board: List[Card] = []

    if logger:
        logger.start_hand(active_players, ante_by_player, holes, fmt_cards)
        logger.set_names(human_name, agent_names)

    info_line(f"Players: {', '.join(p.name for p in active_players)}  | pot: {pot}", "bold")
    for p in active_players:
        if p.name == human_name:
            show_hole(p.name, fmt_cards(holes[p.name]))

    # Preflop
    if logger:
        logger.log_board("Preflop", fmt_board(board))
    show_board("Preflop", fmt_board(board))
    pot, winner = betting_round(
        active_players, pot, holes, board, "Preflop",
        human_name, agent_names, agent_complete,
        logger=logger,
        initial_contrib=preflop_contrib,
        start_actor=preflop_actor,
        opened0=True,
        last_raise0=max(10, MIN_BET) 
    )
    if settle_early(winner, pot):
        return True

    # Flop
    board += deck.pop_cards(3)
    info_line("Phase: Flop", "magenta")
    show_board("Flop", fmt_board(board))
    if logger:
        logger.log_board("Flop", fmt_board(board))
    pot, winner = betting_round(
        active_players, pot, holes, board, "Flop",
        human_name, agent_names, agent_complete, logger=logger
    )
    if settle_early(winner, pot):
        return True

    # Turn
    board += deck.pop_cards(1)
    info_line("Phase: Turn", "magenta")
    show_board("Turn", fmt_board(board))
    if logger:
        logger.log_board("Turn", fmt_board(board))
    pot, winner = betting_round(
        active_players, pot, holes, board, "Turn",
        human_name, agent_names, agent_complete, logger=logger
    )
    if settle_early(winner, pot):
        return True

    # River
    board += deck.pop_cards(1)
    info_line("Phase: River", "magenta")
    show_board("River", fmt_board(board))
    if logger:
        logger.log_board("River", fmt_board(board))
    pot, winner = betting_round(
        active_players, pot, holes, board, "River",
        human_name, agent_names, agent_complete, logger=logger
    )
    if settle_early(winner, pot):
        return True

    # Showdown
    info_line("—— showdown ——", "bold")
    for p in active_players:
        show_hole(p.name, fmt_cards(holes[p.name]))
    info_line("Board: " + fmt_board(board))

    detector = PokerScoreDetector(lowest_rank=lowest_rank)
    winners, scores = showdown(detector, active_players, holes, board)
    for p in active_players:
        s = scores[p.name]
        info_line(f"{p.name} category: {CAT_NAMES_HOLDEM[s.category]}")

    if logger:
        logger.log_showdown(winners, pot, scores, CAT_NAMES_HOLDEM, holes, fmt_cards)

    if len(winners) == 1:
        w = winners[0]
        info_line(f"{w.name} win, get pot {pot}.", "bold green")
        w.money += pot
    else:
        split = pot // len(winners)
        remainder = pot - split * len(winners)
        names = ", ".join(p.name for p in winners)
        msg = f"Share pot: {names} get {split}"
        if remainder:
            msg += f", reminder {remainder} to first {winners[0].name}"
        info_line(msg, "yellow")
        for i, w in enumerate(winners):
            w.money += split + (remainder if i == 0 else 0)

    if logger:
        logger.finish_hand(players)
        logger.dump()

    return True
