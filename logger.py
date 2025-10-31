import json, time, uuid
from typing import Dict, List

from entities import Player, Score, Card

class HandLogger:
    def __init__(self, path: str = "hand_logs.jsonl"):
        self._path = path
        self._data = None

    @staticmethod
    def _fmt_cards_str(cards, fmt_cards_fn):
        return fmt_cards_fn(cards) if cards else ""

    def start_hand(self, players, ante_by_player: dict, holes: Dict[str, List["Card"]], fmt_cards_fn):
        self._data = {
            "hand_id": str(uuid.uuid4()),
            "ts_start": time.time(),
            "players_start": {p.name: p.money + ante_by_player.get(p.name, 0) for p in players},
            "players_end": {},
            "antes": ante_by_player,
            "human_name": None,
            "agent_names": [],
            "holes_at_start": {name: self._fmt_cards_str(holes.get(name), fmt_cards_fn) for name in holes},
            "board": {"Preflop": "", "Flop": "", "Turn": "", "River": ""},
            "streets": [],
            "actions": [],
            "showdown": {
                "winners": [],
                "pot": 0,
                "scores": {},
                "holes_at_showdown": {}
            },
            "ts_end": None
        }

    def set_names(self, human_name: str, agent_names: List[str]):
        if self._data is not None:
            self._data["human_name"] = human_name
            self._data["agent_names"] = list(agent_names)

    def log_board(self, street: str, board_str: str):
        if self._data is not None:
            self._data["board"][street] = board_str

    def log_action(self, street: str, name: str, action: str, *,
                   to_call_before: int, stack_before: int,
                   amount: int, stack_after: int,
                   pot_after: int, contrib_after: int,
                   last_raise: int, opened: bool):
        if self._data is None: return
        self._data["actions"].append({
            "street": street,
            "name": name,
            "action": action,
            "to_call_before": to_call_before,
            "amount": amount,
            "stack_before": stack_before,
            "stack_after": stack_after,
            "pot_after": pot_after,
            "contrib_after": contrib_after,
            "last_raise": last_raise,
            "opened": opened,
            "t": time.time(),
        })

    def log_street_end(self, street: str, pot: int, contrib_snapshot: Dict[str, int]):
        if self._data is None: return
        self._data["streets"].append({
            "street": street,
            "pot_end": pot,
            "contribs": dict(contrib_snapshot),
            "t": time.time(),
        })

    def log_showdown(self, winners: List["Player"], pot: int,
                     scores: Dict[str, "Score"], cat_names: List[str],
                     holes: Dict[str, List["Card"]], fmt_cards_fn):
        if self._data is None: return
        self._data["showdown"]["winners"] = [w.name for w in winners]
        self._data["showdown"]["pot"] = pot
        self._data["showdown"]["scores"] = {
            name: {"category": s.category, "cat_name": cat_names[s.category]}
            for name, s in scores.items()
        }
        self._data["showdown"]["holes_at_showdown"] = {
            name: self._fmt_cards_str(holes.get(name), fmt_cards_fn) for name in holes
        }

    def finish_hand(self, players):
        if self._data is None: return
        self._data["players_end"] = {p.name: p.money for p in players}
        self._data["ts_end"] = time.time()

    def dump(self):
        if self._data is None: return
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._data, ensure_ascii=False) + "\n")
        self._data = None
