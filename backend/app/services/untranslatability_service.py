"""不可译性识别服务 - 低 GPU 依赖版本"""
import asyncio
import re
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime

from app.models.untranslatability_annotation import UntranslatabilityAnnotation
from app.models.multimodal_alignment import MultimodalAlignment
from app.core.config import settings

logger = logging.getLogger(__name__)


class UntranslatabilityService:
    """不可译性识别服务 - 识别语言、文化、语境层面的不可译现象"""

    # 文化专有项类别
    CULTURAL_SPECIFIC_ITEMS = {
        # 中文文化专有项
        "zh": {
            "idioms": [
                "龙", "凤", "麒麟", "熊猫",  # 文化符号
                "春节", "中秋", "清明", "端午",  # 传统节日
                "风水", "太极", "阴阳", "八卦",  # 传统概念
                "四书五经", "论语", "道德经",  # 经典著作
                "功夫", "武侠", "江湖",  # 文化概念
                "戏曲", "京剧", "昆曲",  # 传统艺术
                "茶道", "书法", "国画",  # 文化技艺
            ],
            "social_terms": [
                "老师", "师傅", "师兄",  # 社会称谓
                "面子", "人情", "关系",  # 社会概念
                "孝道", "仁义", "礼",  # 道德概念
            ],
            "food": [
                "饺子", "汤圆", "月饼", "粽子",  # 传统食品
                "火锅", "豆腐", "豆浆",  # 特色食品
            ],
        },
        # 英文文化专有项
        "en": {
            "idioms": [
                "break a leg", "piece of cake", "spill the beans",  # 习语
                "under the weather", "hit the road", "cost an arm and a leg",
            ],
            "cultural_refs": [
                "Thanksgiving", "Halloween", "Easter",  # 节日
                "super bowl", "MLB", "NBA",  # 体育文化
                "Congress", "Senate", "Parliament",  # 政治术语
            ],
        },
        # 日语文化专有项
        "ja": {
            "idioms": [
                "樱花", "和服", "寿司",  # 文化符号
                "武士", "武士道", "忍者",  # 历史文化
                "茶道", "花道", "书道",  # 传统艺术
            ],
        },
    }

    # 语言层面不可译现象
    LINGUISTIC_UNTRANSLATABLE = {
        # 语音层面
        "phonological": [
            "pun", "谐音梗", "双关",  # 双关语
            "rhyme", "押韵",  # 韵律
            "onomatopoeia", "拟声词",  # 拟声词
        ],
        # 形态层面
        "morphological": [
            "compounding", "复合词",
            "derivation", "派生词",
            "inflection", "屈折变化",
        ],
        # 句法层面
        "syntactic": [
            "topic-comment", "话题-评论结构",
            "relative clause ordering", "定语语序",
        ],
        # 语义层面
        "semantic": [
            "lexical gap", "词汇空缺",
            "polysemy", "多义词",
            "category mismatch", "范畴不匹配",
        ],
    }

    # 语境层面不可译现象
    CONTEXTUAL_UNTRANSLATABLE = {
        "discourse": [
            "cohesion devices", "衔接手段",
            "speech acts", "言语行为",
            "register", "语域",
        ],
        "pragmatic": [
            "implicature", "隐含意义",
            "presupposition", "预设",
            "speech act theory", "言语行为理论",
        ],
        "intercultural": [
            "taboo", "禁忌",
            "politeness strategies", "礼貌策略",
            "face work", "面子工作",
        ],
    }

    def __init__(self):
        self._llm_provider = None

    @property
    def llm_provider(self):
        """懒加载 LLM 提供方"""
        if self._llm_provider is None:
            from app.services.ai.llm_provider import llm_provider
            self._llm_provider = llm_provider
        return self._llm_provider

    def is_llm_available(self) -> bool:
        """检查 LLM API 是否可用"""
        return self.llm_provider.is_available()

    async def get_untranslatability_annotation(self, db: AsyncSession, annotation_id: str) -> Optional[UntranslatabilityAnnotation]:
        """获取单条不可译性标注"""
        result = await db.execute(
            select(UntranslatabilityAnnotation).where(UntranslatabilityAnnotation.id == annotation_id)
        )
        return result.scalar_one_or_none()

    async def get_untranslatability_annotations_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        annotation_type: Optional[str] = None,
    ) -> List[UntranslatabilityAnnotation]:
        """获取视频的所有不可译性标注"""
        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        annotations = []
        for alignment in alignments:
            query = select(UntranslatabilityAnnotation).where(
                UntranslatabilityAnnotation.alignment_id == alignment.id
            )
            if annotation_type:
                query = query.where(UntranslatabilityAnnotation.type == annotation_type)
            result = await db.execute(query)
            items = result.scalars().all()
            annotations.extend(items)

        return annotations

    async def create_untranslatability_annotation(
        self,
        db: AsyncSession,
        alignment_id: str,
        type: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        severity: Optional[int] = None,
        confidence: Optional[float] = None,
        annotator: str = "auto",
    ) -> UntranslatabilityAnnotation:
        """创建不可译性标注"""
        annotation = UntranslatabilityAnnotation(
            alignment_id=alignment_id,
            type=type,
            category=category,
            description=description,
            severity=severity,
            confidence=confidence,
            annotator=annotator,
        )
        db.add(annotation)
        await db.commit()
        await db.refresh(annotation)
        return annotation

    async def batch_create_untranslatability_annotations(
        self,
        db: AsyncSession,
        annotations_data: List[Dict[str, Any]],
    ) -> List[UntranslatabilityAnnotation]:
        """批量创建不可译性标注"""
        annotations = []
        for data in annotations_data:
            annotation = UntranslatabilityAnnotation(
                alignment_id=data["alignment_id"],
                type=data.get("type", "cultural"),
                category=data.get("category"),
                description=data.get("description"),
                severity=data.get("severity", 3),
                confidence=data.get("confidence", 0.5),
                annotator=data.get("annotator", "auto"),
            )
            db.add(annotation)
            annotations.append(annotation)
        await db.commit()
        for annotation in annotations:
            await db.refresh(annotation)
        return annotations

    async def detect_linguistic_untranslatability(
        self,
        db: AsyncSession,
        video_id: str,
        source_language: str = "en",
        target_language: str = "zh",
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """检测语言层面不可译现象"""
        result = {
            "success": False,
            "annotations": [],
            "total_annotations": 0,
            "error": None,
        }

        # 获取对齐记录
        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        if not alignments:
            result["error"] = "没有可用的对齐数据"
            return result

        try:
            annotations_data = []

            for i, alignment in enumerate(alignments):
                text = await self._get_alignment_text(db, alignment)

                if text:
                    # 检测语言层面不可译现象
                    detected_items = await self._detect_linguistic_issues(
                        text, source_language, target_language
                    )

                    for item in detected_items:
                        annotations_data.append({
                            "alignment_id": alignment.id,
                            "type": "linguistic",
                            "category": item["category"],
                            "description": item["description"],
                            "severity": item["severity"],
                            "confidence": item["confidence"],
                            "annotator": "auto",
                        })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(alignments),
                        "percent": round((i + 1) / len(alignments) * 100, 2),
                    })

            # 批量创建标注
            annotations = await self.batch_create_untranslatability_annotations(db, annotations_data)

            result["success"] = True
            result["annotations"] = [a.id for a in annotations]
            result["total_annotations"] = len(annotations)
            logger.info(f"语言不可译性检测完成: {len(annotations)} 条")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"语言不可译性检测失败: {e}")

        return result

    async def detect_cultural_untranslatability(
        self,
        db: AsyncSession,
        video_id: str,
        source_language: str = "en",
        target_language: str = "zh",
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """检测文化层面不可译现象"""
        result = {
            "success": False,
            "annotations": [],
            "total_annotations": 0,
            "error": None,
        }

        # 获取对齐记录
        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        if not alignments:
            result["error"] = "没有可用的对齐数据"
            return result

        try:
            annotations_data = []

            for i, alignment in enumerate(alignments):
                text = await self._get_alignment_text(db, alignment)

                if text:
                    # 检测文化专有项
                    detected_items = await self._detect_cultural_items(
                        text, source_language, target_language
                    )

                    for item in detected_items:
                        annotations_data.append({
                            "alignment_id": alignment.id,
                            "type": "cultural",
                            "category": item["category"],
                            "description": item["description"],
                            "severity": item["severity"],
                            "confidence": item["confidence"],
                            "annotator": "auto",
                        })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(alignments),
                        "percent": round((i + 1) / len(alignments) * 100, 2),
                    })

            # 批量创建标注
            annotations = await self.batch_create_untranslatability_annotations(db, annotations_data)

            result["success"] = True
            result["annotations"] = [a.id for a in annotations]
            result["total_annotations"] = len(annotations)
            logger.info(f"文化不可译性检测完成: {len(annotations)} 条")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"文化不可译性检测失败: {e}")

        return result

    async def detect_contextual_untranslatability(
        self,
        db: AsyncSession,
        video_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """检测语境层面不可译现象"""
        result = {
            "success": False,
            "annotations": [],
            "total_annotations": 0,
            "error": None,
        }

        # 获取对齐记录
        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        if not alignments:
            result["error"] = "没有可用的对齐数据"
            return result

        try:
            annotations_data = []

            for i, alignment in enumerate(alignments):
                text = await self._get_alignment_text(db, alignment)
                visual_desc = await self._get_visual_description(db, alignment)

                if text or visual_desc:
                    # 检测语境依赖问题
                    detected_items = await self._detect_contextual_issues(text, visual_desc)

                    for item in detected_items:
                        annotations_data.append({
                            "alignment_id": alignment.id,
                            "type": "contextual",
                            "category": item["category"],
                            "description": item["description"],
                            "severity": item["severity"],
                            "confidence": item["confidence"],
                            "annotator": "auto",
                        })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(alignments),
                        "percent": round((i + 1) / len(alignments) * 100, 2),
                    })

            # 批量创建标注
            annotations = await self.batch_create_untranslatability_annotations(db, annotations_data)

            result["success"] = True
            result["annotations"] = [a.id for a in annotations]
            result["total_annotations"] = len(annotations)
            logger.info(f"语境不可译性检测完成: {len(annotations)} 条")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"语境不可译性检测失败: {e}")

        return result

    async def _get_alignment_text(self, db: AsyncSession, alignment: MultimodalAlignment) -> Optional[str]:
        """获取对齐记录的文本内容"""
        from app.models.subtitle import Subtitle
        from app.models.audio_segment import AudioSegment

        text = None

        if alignment.subtitle_id:
            subtitle_result = await db.execute(
                select(Subtitle).where(Subtitle.id == alignment.subtitle_id)
            )
            subtitle = subtitle_result.scalar_one_or_none()
            if subtitle and subtitle.text:
                text = subtitle.text

        if not text and alignment.audio_segment_id:
            audio_result = await db.execute(
                select(AudioSegment).where(AudioSegment.id == alignment.audio_segment_id)
            )
            audio = audio_result.scalar_one_or_none()
            if audio and audio.asr_text:
                text = audio.asr_text

        return text

    async def _get_visual_description(self, db: AsyncSession, alignment: MultimodalAlignment) -> Optional[Dict]:
        """获取视觉描述"""
        from app.models.visual_description import VisualDescription

        if not alignment.visual_description_id:
            return None

        visual_result = await db.execute(
            select(VisualDescription).where(VisualDescription.id == alignment.visual_description_id)
        )
        visual = visual_result.scalar_one_or_none()

        if visual:
            return {
                "description": visual.description,
                "objects": visual.objects,
                "scene": visual.scene,
            }
        return None

    def _detect_with_rules(self, text: str, source_language: str = "en") -> List[Dict[str, Any]]:
        """使用规则引擎检测不可译性"""
        detected = []

        # 检测语言层面
        linguistic_results = self._detect_linguistic_issues_sync(text)
        for item in linguistic_results:
            item["method"] = "rule"
            detected.append(item)

        # 检测文化专有项
        cultural_results = self._detect_cultural_items_sync(text, source_language)
        for item in cultural_results:
            item["method"] = "rule"
            detected.append(item)

        return detected

    def _detect_linguistic_issues_sync(self, text: str) -> List[Dict[str, Any]]:
        """同步检测语言层面不可译问题"""
        detected = []

        # 检测双关语
        pun_patterns = [
            (r"\b(son|sun)\b", "pun", "双关语 'son/sun'"),
            (r"\b(right/write)\b", "pun", "双关语 'right/write'"),
            (r"谐音", "pun", "中文谐音梗"),
        ]

        for pattern, category, description in pun_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append({
                    "type": "linguistic",
                    "category": category,
                    "description": description,
                    "severity": 4,
                    "confidence": 0.7,
                })

        # 检测拟声词
        onomatopoeia = ["buzz", "hiss", "bang", "crash", "啪", "砰", "呼呼"]
        for word in onomatopoeia:
            if word.lower() in text.lower():
                detected.append({
                    "type": "linguistic",
                    "category": "onomatopoeia",
                    "description": f"拟声词 '{word}'",
                    "severity": 3,
                    "confidence": 0.8,
                })

        return detected

    def _detect_cultural_items_sync(self, text: str, source_language: str = "en") -> List[Dict[str, Any]]:
        """同步检测文化专有项"""
        detected = []

        # 获取源语言的文化专有项
        cultural_items = self.CULTURAL_SPECIFIC_ITEMS.get(source_language, {})

        for category, items in cultural_items.items():
            for item in items:
                if item.lower() in text.lower():
                    detected.append({
                        "type": "cultural",
                        "category": category,
                        "description": f"文化专有项 '{item}'",
                        "severity": 4,
                        "confidence": 0.8,
                    })

        # 检测习语
        idioms = cultural_items.get("idioms", [])
        for idiom in idioms:
            if idiom.lower() in text.lower():
                detected.append({
                    "type": "cultural",
                    "category": "idiom",
                    "description": f"习语 '{idiom}'",
                    "severity": 4,
                    "confidence": 0.85,
                })

        return detected

    async def _detect_with_llm(
        self,
        text: str,
        source_language: str = "en",
        target_language: str = "zh",
    ) -> List[Dict[str, Any]]:
        """使用 LLM 检测不可译性"""
        result = await self.llm_provider.analyze_untranslatability(
            text, source_language, target_language
        )

        if result.get("success"):
            return result.get("items", [])
        return []

    async def detect_untranslatability(
        self,
        text: str,
        source_language: str = "en",
        target_language: str = "zh",
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        检测文本中的不可译性

        Args:
            text: 待检测文本
            source_language: 源语言
            target_language: 目标语言
            use_llm: 是否使用 LLM（优先规则后用 LLM）

        Returns:
            {"success": bool, "items": list, "rule_detected": int, "llm_detected": int}
        """
        result = {
            "success": True,
            "items": [],
            "rule_detected": 0,
            "llm_detected": 0,
            "methods": [],
        }

        # 1. 先用规则引擎（快速，零成本）
        rule_results = self._detect_with_rules(text, source_language)
        result["items"].extend(rule_results)
        result["rule_detected"] = len(rule_results)
        result["methods"].append("rule")

        # 2. 如果需要且可用，再用 LLM
        if use_llm and self.is_llm_available():
            llm_results = await self._detect_with_llm(text, source_language, target_language)
            result["llm_detected"] = len(llm_results)
            result["items"].extend(llm_results)
            result["methods"].append("llm")
            result["llm_provider"] = self.llm_provider.config.provider if self.llm_provider.config else "unknown"
        elif use_llm and not self.is_llm_available():
            result["warning"] = "LLM API not available, using rules only"
            result["methods"].append("rule (llm unavailable)")

        # 去重（基于描述）
        seen = set()
        unique_items = []
        for item in result["items"]:
            desc = item.get("description", "")
            if desc and desc not in seen:
                seen.add(desc)
                unique_items.append(item)

        result["items"] = unique_items
        result["total"] = len(unique_items)

        return result

    async def _detect_linguistic_issues(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> List[Dict[str, Any]]:
        """检测语言层面不可译问题"""
        detected = []

        # 检测双关语
        pun_patterns = [
            (r"\b(son|sun)\b", "pun", "双关语 'son/sun'"),
            (r"\b(right/write)\b", "pun", "双关语 'right/write'"),
            (r"谐音", "pun", "中文谐音梗"),
        ]

        for pattern, category, description in pun_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append({
                    "category": category,
                    "description": description,
                    "severity": 4,
                    "confidence": 0.7,
                })

        # 检测拟声词
        onomatopoeia = ["buzz", "hiss", "bang", "crash", "啪", "砰", "呼呼"]
        for word in onomatopoeia:
            if word.lower() in text.lower():
                detected.append({
                    "category": "onomatopoeia",
                    "description": f"拟声词 '{word}'",
                    "severity": 3,
                    "confidence": 0.8,
                })

        # 检测韵律（简化检测）
        # 实际应使用 NLP 分析韵律结构

        return detected

    async def _detect_cultural_items(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> List[Dict[str, Any]]:
        """检测文化专有项"""
        detected = []

        # 获取源语言的文化专有项
        cultural_items = self.CULTURAL_SPECIFIC_ITEMS.get(source_language, {})

        for category, items in cultural_items.items():
            for item in items:
                if item.lower() in text.lower():
                    detected.append({
                        "category": category,
                        "description": f"文化专有项 '{item}'",
                        "severity": 4,
                        "confidence": 0.8,
                    })

        # 检测习语
        idioms = cultural_items.get("idioms", [])
        for idiom in idioms:
            if idiom.lower() in text.lower():
                detected.append({
                    "category": "idiom",
                    "description": f"习语 '{idiom}'",
                    "severity": 4,
                    "confidence": 0.85,
                })

        return detected

    async def _detect_contextual_issues(
        self,
        text: Optional[str],
        visual_desc: Optional[Dict],
    ) -> List[Dict[str, Any]]:
        """检测语境依赖问题"""
        detected = []

        # 检测需要语境的指代
        if text:
            # 检测代词（可能需要语境才能理解）
            pronouns = ["it", "this", "that", "he", "she", "they", "这", "那", "他", "她"]
            for pronoun in pronouns:
                if pronoun.lower() in text.lower():
                    detected.append({
                        "category": "discourse",
                        "description": f"代词指代 '{pronoun}' 需要语境",
                        "severity": 2,
                        "confidence": 0.6,
                    })

        # 检测视觉语境依赖
        if visual_desc:
            objects = visual_desc.get("objects", [])
            if objects:
                # 如果画面中有多个对象，可能需要语境理解关系
                if len(objects) > 3:
                    detected.append({
                        "category": "visual_context",
                        "description": "画面包含多个对象，关系需语境理解",
                        "severity": 2,
                        "confidence": 0.5,
                    })

        return detected

    async def get_untranslatability_statistics(
        self,
        db: AsyncSession,
        video_id: str,
    ) -> Dict[str, Any]:
        """获取不可译性统计信息"""
        annotations = await self.get_untranslatability_annotations_by_video(db, video_id)

        stats = {
            "total": len(annotations),
            "by_type": {},
            "by_severity": {},
            "high_severity_items": [],
        }

        # 按类型统计
        for annotation in annotations:
            type_key = annotation.type
            stats["by_type"][type_key] = stats["by_type"].get(type_key, 0) + 1

            # 按严重程度统计
            severity_key = annotation.severity or 0
            stats["by_severity"][severity_key] = stats["by_severity"].get(severity_key, 0) + 1

            # 高严重程度项
            if annotation.severity >= 4:
                stats["high_severity_items"].append({
                    "id": annotation.id,
                    "type": annotation.type,
                    "category": annotation.category,
                    "description": annotation.description,
                    "severity": annotation.severity,
                })

        return stats

    async def delete_untranslatability_annotations_by_video(self, db: AsyncSession, video_id: str) -> int:
        """删除视频的所有不可译性标注"""
        annotations = await self.get_untranslatability_annotations_by_video(db, video_id)
        count = 0
        for annotation in annotations:
            await db.delete(annotation)
            count += 1
        await db.commit()
        return count


# 单例实例
untranslatability_service = UntranslatabilityService()