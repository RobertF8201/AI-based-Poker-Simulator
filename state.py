import re

MIN_BET = 5

CAT_NAMES_HOLDEM = [
    "High Card",
    "One Pair",
    "Two Pair",
    "Three of a Kind",
    "Straight",
    "Full House",
    "Flush",
    "Four of a Kind",
    "Straight Flush"
]

JSON_RE = re.compile(r'\{[^{}]+\}')

RANKS = {2:"2",3:"3",4:"4",5:"5",6:"6",7:"7",8:"8",9:"9",10:"10",11:"J",12:"Q",13:"K",14:"A"}
SUITS = {0:"♠",1:"♣",2:"♦",3:"♥"}