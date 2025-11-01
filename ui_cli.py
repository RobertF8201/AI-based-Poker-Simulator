import re
from typing import Optional, List, Dict, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
from rich import box

console = Console()

def banner_hand(hand_no: int):
    console.rule(f"[bold cyan]Hand #{hand_no}")

def seats_positions_line(players_order) -> str:
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

def show_seats(players_order):
    txt = seats_positions_line(players_order)
    console.print(Panel.fit(txt, title="Seats & Positions", style="bold green"))

def show_hole(name: str, hole_txt: str):
    console.print(Panel.fit(f"[bold]{name}[/] holes: [yellow]{hole_txt}[/]"))

def show_board(street: str, board_txt: str):
    console.print(Panel.fit(f"[italic]{street}[/]\n[white]{board_txt}[/]", title="Board", style="magenta"))

def stacks_pot_table(active_players, pot: int, highlight: Optional[str] = None):
    tb = Table(box=box.SIMPLE_HEAVY, expand=True)
    tb.add_column("Player", justify="left", style="bold")
    tb.add_column("Chips", justify="right")
    for p in active_players:
        nm = f"[cyan]{p.name}[/]" if highlight and p.name == highlight else p.name
        tb.add_row(nm, str(p.money))
    console.print(Panel(tb, title=f"Pot: {pot}", style="blue"))

def info_line(msg: str, style: str = "white"):
    console.print(f"[{style}]{msg}[/{style}]")

def hr():
    console.rule()

def ask_action_when_to_call0(opened: bool) -> str:
    if not opened:
        choices = "check / bet / all-in"
        prompt = "[check/bet/all-in]"
        valid = ["check","bet","all-in","allin","all in"]
    else:
        choices = "check / raise / all-in"
        prompt = "[check/raise/all-in]"
        valid = ["check","raise","all-in","allin","all in"]
    info_line(f"Available actions: {choices}", "dim")
    return Prompt.ask(prompt, choices=valid, default="check").lower()

def ask_action_when_to_call_gt0(to_call: int) -> str:
    info_line(f"You must call at least {to_call} to continue", "dim")
    return Prompt.ask("[fold/call/raise/all-in]", choices=["fold","call","raise","all-in","allin","all in"], default="call").lower()

def ask_bet_amount(max_amt: int, min_amt: int) -> int:
    console.print(f"Enter your bet amount (min [yellow]{min_amt}[/], max [yellow]{max_amt}[/])")
    return IntPrompt.ask("Bet", default=min_amt, show_default=True)

def ask_raise_size(max_amt: int, min_raise: int) -> int:
    console.print(f"Enter your raise size (excluding call) – min [yellow]{min_raise}[/], max [yellow]{max_amt}[/]")
    return IntPrompt.ask("Raise size", default=min_raise, show_default=True)

def ask_continue() -> bool:
    return Confirm.ask("Continue playing?", default=True)

def ask_report() -> bool:
    return Confirm.ask("Generate AI report for this hand?", default=False)

def human_turn_header(player_name: str, hole_view: str, to_call: int, stack: int):
    console.print(Panel.fit(
        f"[bold]{player_name}[/] turn\n"
        f"To call: [yellow]{to_call}[/]   Stack: [yellow]{stack}[/]\n"
        f"Your cards: [green]{hole_view}[/]",
        style="bold white on rgb(30,30,30)",
    ))

_SECTION_RE = re.compile(r"^\s*(\d+)\.\s*\*\*(.+?)\*\*\s*$")

def _split_sections(md: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current_title = None
    for line in md.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current_title = m.group(2).strip()
            sections[current_title] = []
        else:
            if current_title is None:
                current_title = "_Preamble_"
                sections[current_title] = []
            sections[current_title].append(line)
    return sections

def _parse_overview(lines: List[str]) -> Table:
    kv = {}
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if ":" in ln:
            key, _, val = ln.partition(":")
            kv[key.strip()] = val.strip()
    tb = Table(title="Overview", box=box.SIMPLE_HEAVY)
    tb.add_column("Field", style="bold", justify="right")
    tb.add_column("Value", justify="left")
    for k in ("Hand ID", "Overall Score", "Summary"):
        if k in kv:
            tb.add_row(k, kv[k])
    for k, v in kv.items():
        if k not in ("Hand ID","Overall Score","Summary"):
            tb.add_row(k, v)
    return tb

def _extract_markdown_table(lines: List[str]) -> Tuple[List[str], List[List[str]]]:
    pipe_blocks: List[List[str]] = []
    cur: List[str] = []
    for ln in lines:
        if ln.strip().startswith("|") and ln.strip().endswith("|"):
            cur.append(ln.strip())
        else:
            if cur:
                pipe_blocks.append(cur)
                cur = []
    if cur:
        pipe_blocks.append(cur)
    if not pipe_blocks:
        return [], []

    block = pipe_blocks[0]
    if len(block) < 2:
        return [], []
    header = [c.strip() for c in block[0].strip("|").split("|")]
    rows = []
    for ln in block[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        rows.append(cells[:len(header)])
    return header, rows

def _md_bullets_to_text(lines: List[str]) -> str:
    buf = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("- "):
            buf.append("• " + s[2:])
        elif s.startswith("* "):
            buf.append("• " + s[2:])
        else:
            buf.append(s)
    return "\n".join(buf).strip()

def render_ai_review_report(analysis: str):
    if not analysis or analysis.strip() == "[Empty response]":
        info_line("\n=== AI Review Report ===\n", "bold")
        info_line("[Empty response]", "red")
        return

    info_line("\n=== AI Review Report ===\n", "bold")

    sections = _split_sections(analysis)

    if "Overview" in sections:
        tb = _parse_overview(sections["Overview"])
        console.print(Panel(tb, style="bold cyan"))
    else:
        pre = sections.get("_Preamble_", [])
        if pre:
            console.print(Panel(_md_bullets_to_text(pre), title="Summary", style="bold cyan"))

    if "Quantitative Table" in sections:
        headers, rows = _extract_markdown_table(sections["Quantitative Table"])
        if headers:
            t = Table(title="Quantitative Table", box=box.SIMPLE_HEAVY)
            for h in headers:
                t.add_column(h, overflow="fold")
            for r in rows:
                t.add_row(*r)
            console.print(Panel(t, style="bold magenta"))
        else:
            console.print(Panel(_md_bullets_to_text(sections["Quantitative Table"]), title="Quantitative Table", style="bold magenta"))

    for title in ("Street-by-Street Analysis", "Equity & Probabilities", "Strategic Recommendations", "Notes / Assumptions"):
        if title in sections:
            txt = _md_bullets_to_text(sections[title])
            console.print(Panel(txt, title=title, style="green"))

    hr()

def ask_num_players(min_players: int = 2, max_players: int = 9, default: int = 4) -> int:
    info_line(f"How many players in total? (min {min_players}, max {max_players})", "dim")
    while True:
        n = IntPrompt.ask("Players", default=default, show_default=True)
        if n < min_players:
            info_line(f"Players cannot be fewer than {min_players}.", "red")
            continue
        if n > max_players:
            info_line(f"Players cannot exceed {max_players}.", "red")
            continue
        return n

def ask_starting_stack(default_stack: int = 100, min_stack: int = 1, max_stack: int = 100000) -> int:
    info_line(f"Starting stack for each player? (default {default_stack})", "dim")
    while True:
        v = IntPrompt.ask("Starting Stack", default=default_stack, show_default=True)
        if v < min_stack:
            info_line(f"Stack must be ≥ {min_stack}.", "red")
            continue
        if v > max_stack:
            info_line(f"Stack must be ≤ {max_stack}.", "red")
            continue
        return v