"""LLM 提供商 - 支持 DeepSeek、OpenAI 等"""
import json
import os
import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str  # deepseek, openai, dashscope
    model: str
    api_key: str
    base_url: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.1


class LLMProvider:
    """LLM 提供商 - 统一接口"""

    PROVIDERS = {
        "deepseek": {
            "name": "DeepSeek",
            "models": ["deepseek-chat", "deepseek-coder"],
            "base_url": "https://api.deepseek.com/v1",
            "cost_per_1k": 0.001,  # $0.001/1K tokens
        },
        "openai": {
            "name": "OpenAI",
            "models": ["gpt-4o-mini", "gpt-3.5-turbo"],
            "base_url": "https://api.openai.com/v1",
            "cost_per_1k": 0.005,
        },
        "dashscope": {
            "name": "阿里云通义",
            "models": ["qwen-turbo", "qwen-plus"],
            "base_url": "https://dashscope.aliyuncs.com/api/v1",
            "cost_per_1k": 0.0,  # 有免费额度
        },
    }

    def __init__(self):
        self.config = self._auto_config()
        logger.info(f"LLM Provider initialized: {self.config.provider if self.config else 'None'}")

    def _auto_config(self) -> Optional[LLMConfig]:
        """自动检测并配置 LLM"""
        # 优先 DeepSeek（性价比高）
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if api_key:
            return LLMConfig(
                provider="deepseek",
                model="deepseek-chat",
                api_key=api_key,
                base_url=self.PROVIDERS["deepseek"]["base_url"],
            )

        # 备选 OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return LLMConfig(
                provider="openai",
                model=model,
                api_key=api_key,
                base_url=self.PROVIDERS["openai"]["base_url"],
            )

        # 备选阿里云
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if api_key:
            model = os.getenv("DASHSCOPE_MODEL", "qwen-turbo")
            return LLMConfig(
                provider="dashscope",
                model=model,
                api_key=api_key,
                base_url=self.PROVIDERS["dashscope"]["base_url"],
            )

        return None

    def is_available(self) -> bool:
        """检查是否可用"""
        return self.config is not None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            system_prompt: 系统提示词
            temperature: 温度参数

        Returns:
            {"success": bool, "content": str, "error": str, "usage": dict}
        """
        if not self.config:
            return {
                "success": False,
                "error": "No LLM provider configured",
                "content": None,
                "usage": None,
            }

        try:
            # 构建消息
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)

            # 调用 API
            async with httpx.AsyncClient(timeout=60.0) as client:
                if self.config.provider == "dashscope":
                    response = await client.post(
                        f"{self.config.base_url}/services/aigc/text-generation/generation",
                        headers={
                            "Authorization": f"Bearer {self.config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.config.model,
                            "input": {"messages": full_messages},
                            "parameters": {
                                "temperature": temperature,
                                "max_tokens": self.config.max_tokens,
                            },
                        },
                    )
                else:
                    # OpenAI / DeepSeek 格式
                    response = await client.post(
                        f"{self.config.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.config.model,
                            "messages": full_messages,
                            "temperature": temperature,
                            "max_tokens": self.config.max_tokens,
                        },
                    )

                if response.status_code == 200:
                    data = response.json()

                    if self.config.provider == "dashscope":
                        content = data["output"]["text"]
                    else:
                        content = data["choices"][0]["message"]["content"]

                    usage = data.get("usage", {})

                    return {
                        "success": True,
                        "content": content,
                        "error": None,
                        "usage": usage,
                        "provider": self.config.provider,
                        "model": self.config.model,
                    }
                else:
                    error_msg = f"API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "content": None,
                        "usage": None,
                    }

        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "usage": None,
            }

    async def analyze_metaphor(self, text: str, language: str = "zh") -> Dict[str, Any]:
        """
        隐喻分析

        Args:
            text: 待分析文本
            language: 语言代码

        Returns:
            {"success": bool, "metaphors": list, "error": str}
        """
        system_prompt = """你是一个专业的隐喻分析专家。请分析文本中的隐喻表达。

分析要求：
1. 识别概念隐喻（源域→目标域映射）
2. 识别视觉隐喻（画面中的隐喻）
3. 识别多模态隐喻（文字+画面协同）

输出格式（JSON）：
{
    "metaphors": [
        {
            "type": "conceptual|visual|multimodal",
            "source_domain": "源域",
            "target_domain": "目标域",
            "trigger": "触发词/表达",
            "confidence": 0.0-1.0,
            "explanation": "简要解释"
        }
    ]
}"""

        messages = [
            {"role": "user", "content": f"语言：{language}\n文本：{text}"}
        ]

        result = await self.chat(messages, system_prompt)

        if result["success"]:
            try:
                # 尝试解析 JSON
                data = json.loads(result["content"])
                return {
                    "success": True,
                    "metaphors": data.get("metaphors", []),
                    "error": None,
                    "provider": result["provider"],
                }
            except json.JSONDecodeError:
                # 解析失败，返回原始内容
                return {
                    "success": True,
                    "metaphors": [{"type": "unknown", "raw": result["content"]}],
                    "error": "JSON parse failed",
                    "provider": result["provider"],
                }

        return {
            "success": False,
            "metaphors": [],
            "error": result["error"],
        }

    async def analyze_untranslatability(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, Any]:
        """
        不可译性分析

        Args:
            text: 待分析文本
            source_lang: 源语言
            target_lang: 目标语言

        Returns:
            {"success": bool, "items": list, "error": str}
        """
        system_prompt = """你是一个专业的翻译质量分析专家。请分析文本中的不可译现象。

不可译类型：
1. 语言层面（语音、词汇、句法、语义）
2. 文化层面（文化专有项、习语、典故）
3. 语境层面（需要上下文理解）

输出格式（JSON）：
{
    "items": [
        {
            "type": "linguistic|cultural|contextual",
            "category": "具体类别",
            "text": "原文片段",
            "description": "不可译原因",
            "severity": 1-5,
            "translation_hint": "翻译建议"
        }
    ]
}"""

        messages = [
            {"role": "user", "content": f"源语言：{source_lang}\n目标语言：{target_lang}\n文本：{text}"}
        ]

        result = await self.chat(messages, system_prompt)

        if result["success"]:
            try:
                data = json.loads(result["content"])
                return {
                    "success": True,
                    "items": data.get("items", []),
                    "error": None,
                    "provider": result["provider"],
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "items": [{"type": "unknown", "raw": result["content"]}],
                    "error": "JSON parse failed",
                    "provider": result["provider"],
                }

        return {
            "success": False,
            "items": [],
            "error": result["error"],
        }

    def estimate_cost(self, text_length: int) -> float:
        """估算成本"""
        if not self.config:
            return 0.0

        provider_info = self.PROVIDERS.get(self.config.provider, {})
        cost_per_1k = provider_info.get("cost_per_1k", 0)

        # 粗略估算 token 数（中文约 1.5 tokens/字，英文约 4 chars/token）
        estimated_tokens = text_length * 1.5

        return (estimated_tokens / 1000) * cost_per_1k


# 全局单例
llm_provider = LLMProvider()
