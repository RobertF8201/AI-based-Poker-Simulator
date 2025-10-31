#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real LLM vs Human test
"""

import os
from test3 import (
    play_hand_human_vs_multi_agents,
    Player,
)

# ✅ 建议使用环境变量保存密钥（更安全）
# os.environ["ANTHROPIC_API_KEY"] = "你的密钥"

# ------------------ Anthropic 官方 / 代理 API 封装 ------------------
import requests
import json


class ChatAnthropic:
    def __init__(
        self,
        model="claude-3-5-sonnet-20241022",
        api_key=None,
        base_url="https://yinli.one",
        temperature=0,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    def complete(self, prompt: str) -> str:
        """调用 Claude / 代理接口，返回模型输出文本（单行 JSON）"""
        url = f"{self.base_url}/v1/messages"
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = {
            "model": self.model,
            "max_tokens": 64,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=45)
            resp.raise_for_status()
            js = resp.json()
            content = js.get("content", [])
            if content and isinstance(content, list):
                text = "".join(
                    [seg.get("text", "") for seg in content if isinstance(seg, dict)]
                )
                # ✅ 确保是单行 JSON
                return text.strip().splitlines()[0]
            return '{"action":"check","amount":0}'
        except Exception as e:
            print(f"⚠️ API 调用失败: {e}")
            return '{"action":"check","amount":0}'


# ------------------ 创建 AI 玩家 & 开打 ------------------

def run_vs_real_claude():
    # ✅ 初始化 LLM 接口（直接用你提供的网关）
    llm = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        api_key="sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI",  # 生产中请改成环境变量
        base_url="https://yinli.one",
        temperature=0,
    )

    # ✅ 准备玩家（你 + 3 个 AI）
    players = [
        Player("You", 100),
        Player("Bot1", 100),
        Player("Bot2", 100),
        Player("Bot3", 100),
    ]

    # ✅ 启动一手牌
    play_hand_human_vs_multi_agents(
        human_name="You",
        agent_names=["Bot1", "Bot2", "Bot3"],
        players=players,
        agent_complete=llm.complete,
        lowest_rank=2,
    )

    # ✅ 打印结算
    print("\n=== Final stacks ===")
    for p in players:
        print(f"{p.name}: {p.money}")


if __name__ == "__main__":
    run_vs_real_claude()
