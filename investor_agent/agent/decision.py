"""
LLM 决策执行引擎 - 支持多模型自适应回退与 503 指数退避重试
"""
import json
import os
import time
from typing import Dict, List, Optional
from investor_agent.agent.prompts import build_trading_system_prompt

class TradingAgent:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or os.environ.get("GEMINI_MODEL")
        if not self.api_key:
            raise ValueError("未配置 GEMINI_API_KEY！请在环境变量或 GitHub Secrets 中配置。")

    def generate_decisions(
        self,
        account_info: Dict,
        market_data: Dict[str, Dict],
        macro_data: Dict[str, Dict]
    ) -> List[Dict]:
        """
        调用 LLM 生成符合结构化约束的投资决策
        """
        from google import genai
        from google.genai import types

        system_prompt = build_trading_system_prompt(account_info, market_data, macro_data)
        client = genai.Client(api_key=self.api_key)

        # 候选模型优先级列表
        candidate_models = [
            self.model_name,
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-3.6-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]
        # 去重保持顺序
        seen = set()
        candidate_models = [m for m in candidate_models if m and not (m in seen or seen.add(m))]

        response = None
        for m in candidate_models:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents=system_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2
                        ),
                    )
                    print(f"成功使用模型生成决策: {m}")
                    break
                except Exception as e:
                    err_msg = str(e)
                    if any(code in err_msg for code in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                        wait_sec = (attempt + 1) * 3
                        print(f"模型 {m} 临时繁忙，等待 {wait_sec} 秒后重试 (第 {attempt + 1}/3 次)...")
                        time.sleep(wait_sec)
                        continue
                    print(f"模型 {m} 调用异常: {e}")
                    break
            if response and response.text:
                break

        # 如果预设模型均失败，自动从 API 动态获取可用模型列表兜底
        if not response or not response.text:
            print("预设模型暂不可用，正在动态获取当前 API Key 权限下的可用模型列表...")
            try:
                available_models = [m.name.replace("models/", "") for m in client.models.list()]
                print(f"当前支持的模型列表: {available_models}")
                for m in available_models:
                    if ("flash" in m or "pro" in m) and m not in candidate_models:
                        try:
                            print(f"尝试备选模型: {m}")
                            response = client.models.generate_content(
                                model=m,
                                contents=system_prompt,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    temperature=0.2
                                ),
                            )
                            print(f"成功使用模型: {m}")
                            break
                        except Exception as e:
                            print(f"模型 {m} 调用异常: {e}")
            except Exception as list_err:
                print(f"获取可用模型列表失败: {list_err}")

        if not response or not response.text:
            raise RuntimeError("所有候选模型调用均失败，无法获取 AI 决策输出。")

        # 剥离可能存在的 markdown 标签并解析 JSON
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            decisions = json.loads(raw_text)
            if isinstance(decisions, dict) and "decisions" in decisions:
                decisions = decisions["decisions"]
            return decisions if isinstance(decisions, list) else []
        except json.JSONDecodeError as e:
            print(f"解析 AI 决策 JSON 失败: {e}\n原始内容: {response.text}")
            return []
