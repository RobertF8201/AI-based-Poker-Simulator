#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import builtins
from contextlib import contextmanager
from typing import List

# ==== 按你的项目实际路径来导入 ====
# 这里假设你已把下面这些函数/类集成到项目（即上一条我给你的实现）：
# - play_hand_human_vs_multi_agents
# - betting_round_human_vs_multi_agents（被上面调用）
# 以及项目里已有：
# - Player, Deck, Card, PokerScoreDetector, showdown
# - fmt_cards, fmt_board, CAT_NAMES_HOLDEM
# - ask_bet_amount, ask_raise_size
#
# from your_project import (
#     play_hand_human_vs_multi_agents, Player
# )
from test2 import play_hand_human_vs_multi_agents, Player   # 改成你的包名

# ============ 两个“假 LLM”示例，返回一行 JSON ============

class AlwaysCheckLLM:
    """永远让 AI 选择 check，演示最稳定路径：全桌过牌，直接摊牌。"""
    def complete(self, prompt: str) -> str:
        return '{"action":"check","amount":0}'


class TightLLM:
    """
    简单的紧手风格：
    - Preflop：开池小注（bet 10）
    - Flop/Turn/River：大多数时候 check（演示已开池/未开池分支）
    说明：引擎会在“已开池”时把 amount 视作“本轮总投入”，合法性校验仍由你的下注轮逻辑完成。
    """
    def complete(self, prompt: str) -> str:
        # 粗糙地从提示词里读一读 Street
        street = "Preflop"
        for line in prompt.splitlines():
            if line.strip().startswith("- Street:"):
                street = line.split(":", 1)[1].strip()
                break
        if street == "Preflop":
            return '{"action":"bet","amount":10}'
        return '{"action":"check","amount":0}'


# ============ 一个小工具：把 input() 打补丁 ============

@contextmanager
def patched_input(responses: List[str]):
    """
    将 builtins.input 打补丁，按给定序列依次返回。
    序列用尽后，继续返回 "check"，以避免 StopIteration。
    """
    it = iter(responses)
    orig_input = builtins.input

    def fake_input(prompt: str = "") -> str:
        try:
            ans = next(it)
        except StopIteration:
            ans = "check"
        print(prompt + ans)  # 打印回显，便于调试
        return ans

    builtins.input = fake_input
    try:
        yield
    finally:
        builtins.input = orig_input


# ============ 测试主程序 ============

def run_demo(llm_mode: str = "check_only"):
    """
    llm_mode:
      - "check_only": 全桌 AI 都 check（AlwaysCheckLLM）
      - "tight":      Preflop 偶尔开池（TightLLM）
    """
    # 1) 准备玩家：1 人类 + 3 AI
    players = [
        Player("You",   100),
        Player("Bot1",  100),
        Player("Bot2",  100),
        Player("Bot3",  100),
    ]

    human_name = "You"
    agent_names = ["Bot1", "Bot2", "Bot3"]

    # 2) 选择一个“假 LLM”
    if llm_mode == "tight":
        llm = TightLLM()
    else:
        llm = AlwaysCheckLLM()

    # 3) 人类动作脚本（可根据需要更换）
    #   - 未开池时：check/bet/all-in
    #   - 已开池时：fold/call/raise/all-in
    # 下面给一套“全程过牌”的脚本，足够跑通到摊牌
    human_script = [
        # Preflop: 你行动若先到，多数情况可以 check
        "check",
        # Flop:
        "check",
        # Turn:
        "check",
        # River:
        "check",
        # 若中途出现已开池分支、引擎会再询问，这里脚本用尽后自动回退到 "check"
    ]

    # 4) 打补丁并开打
    print("========== START HAND (mode: {}) ==========".format(llm_mode))
    with patched_input(human_script):
        ok = play_hand_human_vs_multi_agents(
            human_name=human_name,
            agent_names=agent_names,
            players=players,
            agent_complete=llm.complete,   # 关键：传入“返回一行 JSON”的回调
            lowest_rank=2
        )

    print("Hand finished:", ok)
    print("Final stacks:")
    for p in players:
        print(f" - {p.name}: {p.money}")


if __name__ == "__main__":
    # 场景 A：最稳定，所有 AI check；人类也全程 check，直接摊牌
    run_demo("check_only")

    # 场景 B：Preflop 紧手开池（bet 10），你可以把 human_script 改成 "call"/"fold" 等看看已开池分支
    run_demo("tight")
