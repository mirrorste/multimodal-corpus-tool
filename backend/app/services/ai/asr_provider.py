"""ASR 提供方 - Whisper 本地 + 云端 API"""
import os
import asyncio
import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ASRProvider:
    """ASR 提供方 - Whisper 本地 + 云端 API（低 GPU 依赖）"""

    def __init__(self):
        self.local_available = self._check_whisper()
        self.dashscope_key = os.getenv("DASHSCOPE_API_KEY")
        self.model_name = os.getenv("WHISPER_MODEL", "base")  # tiny/base/small
        self.whisper_model = None

        self.config = self._auto_config()
        logger.info(
            f"ASR Provider initialized: "
            f"Whisper ({self.model_name}): {'✓' if self.local_available else '✗'}, "
            f"DashScope: {'✓' if self.dashscope_key else '✗'}"
        )

    def _check_whisper(self) -> bool:
        """检查 Whisper 是否可用"""
        try:
            import whisper
            return True
        except ImportError:
            return False

    def _auto_config(self) -> Optional[str]:
        """自动选择配置"""
        if self.dashscope_key:
            return "dashscope"
        return None

    def is_available(self) -> bool:
        return self.local_available or self.config is not None

    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        语音转文字

        Args:
            audio_path: 音频文件路径
            language: 语言代码（None 为自动检测）

        Returns:
            {
                "success": bool,
                "text": str,
                "segments": [{"start": float, "end": float, "text": str}],
                "language": str,
                "error": str
            }
        """
        # 优先本地 Whisper（CPU 模式）
        if self.local_available:
            result = await self._transcribe_whisper(audio_path, language)
            if result["success"]:
                return result

        # 备选云端
        if self.config == "dashscope":
            return await self._transcribe_dashscope(audio_path, language)

        return {
            "success": False,
            "text": None,
            "segments": [],
            "language": None,
            "error": "No ASR method available",
        }

    async def _transcribe_whisper(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """本地 Whisper 转录（CPU 模式）"""
        try:
            import whisper

            # 懒加载模型
            if self.whisper_model is None:
                logger.info(f"Loading Whisper model: {self.model_name} (CPU)")

                def load_model():
                    return whisper.load_model(
                        self.model_name,
                        device="cpu",  # 明确使用 CPU
                    )

                # 在线程中加载模型（避免阻塞）
                self.whisper_model = await asyncio.to_thread(load_model)
                logger.info(f"Whisper model loaded: {self.model_name}")

            # 执行转录
            def do_transcribe():
                options = {
                    "language": language,
                    "fp16": False,  # 禁用 FP16（CPU）
                    "verbose": False,
                    "task": "transcribe",
                }

                # 如果没有指定语言，设为 None 让模型自动检测
                if language is None:
                    del options["language"]

                return self.whisper_model.transcribe(audio_path, **options)

            result = await asyncio.to_thread(do_transcribe)

            segments = []
            for seg in result.get("segments", []):
                segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip(),
                })

            return {
                "success": True,
                "text": result["text"].strip(),
                "segments": segments,
                "language": result.get("language", language or "unknown"),
                "detected_language": result.get("language"),
                "confidence": 0.9,  # Whisper 不直接提供整体置信度
                "provider": f"whisper-{self.model_name}-cpu",
            }

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return {
                "success": False,
                "text": None,
                "segments": [],
                "language": None,
                "error": str(e),
                "provider": f"whisper-{self.model_name}-cpu",
            }

    async def _transcribe_dashscope(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """阿里云 ASR API"""
        try:
            # 读取音频文件
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            # 阿里云语音识别 API
            async with httpx.AsyncClient(timeout=120.0) as client:
                # paraformer-zh 是中文识别模型
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/audio/asr",
                    headers={
                        "Authorization": f"Bearer {self.dashscope_key}",
                    },
                    files={"file": ("audio.wav", audio_data, "audio/wav")},
                    data={
                        "model": "paraformer-zh" if language in [None, "zh"] else "paraformer-en",
                        "sample_rate": 16000,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    output = data.get("output", {})

                    # 解析阿里云 ASR 输出
                    sentences = output.get("sentences", [])

                    segments = []
                    texts = []

                    for sent in sentences:
                        start = sent.get("begin_time", 0) / 1000  # ms -> s
                        end = sent.get("end_time", 0) / 1000
                        text = sent.get("text", "")

                        segments.append({
                            "start": start,
                            "end": end,
                            "text": text,
                        })
                        texts.append(text)

                    return {
                        "success": True,
                        "text": "".join(texts),
                        "segments": segments,
                        "language": "zh" if language in [None, "zh"] else "en",
                        "confidence": 0.95,
                        "provider": "dashscope-asr",
                    }

                else:
                    error_msg = f"API error: {response.status_code}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "text": None,
                        "segments": [],
                        "language": None,
                        "error": error_msg,
                        "provider": "dashscope-asr",
                    }

        except Exception as e:
            logger.error(f"DashScope ASR failed: {e}")
            return {
                "success": False,
                "text": None,
                "segments": [],
                "language": None,
                "error": str(e),
                "provider": "dashscope-asr",
            }

    async def translate(
        self,
        audio_path: str,
        target_language: str = "en",
    ) -> Dict[str, Any]:
        """
        语音翻译（先识别再翻译）

        Args:
            audio_path: 音频文件路径
            target_language: 目标语言

        Returns:
            {"success": bool, "text": str, "language": str, "error": str}
        """
        # 先转录
        result = await self.transcribe(audio_path)

        if not result["success"]:
            return result

        # 如果是 Whisper 本地，可以直接使用 translate 模式
        if self.local_available:
            try:
                import whisper

                if self.whisper_model is None:
                    logger.info(f"Loading Whisper model: {self.model_name} (CPU)")
                    self.whisper_model = await asyncio.to_thread(
                        whisper.load_model, self.model_name, device="cpu"
                    )

                def do_translate():
                    return self.whisper_model.transcribe(
                        audio_path,
                        task="translate",
                        fp16=False,
                    )

                result = await asyncio.to_thread(do_translate)

                return {
                    "success": True,
                    "text": result["text"].strip(),
                    "segments": result.get("segments", []),
                    "language": target_language,
                    "detected_language": result.get("language"),
                    "provider": f"whisper-{self.model_name}-translate",
                }

            except Exception as e:
                logger.error(f"Whisper translate failed: {e}")

        # 备选：返回识别结果，标记需要后续翻译
        return {
            "success": True,
            "text": result["text"],
            "segments": result["segments"],
            "language": result.get("language", "unknown"),
            "warning": "Translation not available, use LLM for translation",
        }


# 全局单例
asr_provider = ASRProvider()
