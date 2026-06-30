"""隐喻识别服务 - 低 GPU 依赖版本"""
import asyncio
import re
from typing import Optional, Callable, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.metaphor_annotation import MetaphorAnnotation
from app.models.multimodal_alignment import MultimodalAlignment

logger = logging.getLogger(__name__)


class MetaphorService:
    """隐喻识别服务 - 规则引擎 + LLM API"""

    # 预定义隐喻模式（基于 Lakoff & Johnson 理论）
    COMMON_METAPHORS = {
        "TIME_IS_MONEY": {
            "source": "money",
            "target": "time",
            "keywords": ["花费", "浪费", "节约", "投资", "宝贵", "节省", "消耗"],
            "patterns": [r"花.*时间", r"浪费.*时间", r"节约.*时间", r"投资.*时间"],
        },
        "TIME_IS_SPACE": {
            "source": "space",
            "target": "time",
            "keywords": ["前", "后", "往前", "回顾", "展望", "前方", "身后", "时间线"],
            "patterns": [r"时间.*前", r"时间.*后", r"往前.*年", r"回顾.*年"],
        },
        "LIFE_IS_JOURNEY": {
            "source": "journey",
            "target": "life",
            "keywords": ["路", "道路", "旅程", "人生", "同行", "分道扬镳", "终点", "起点", "坎坷", "平坦"],
            "patterns": [r".*道路", r"人生.*路", r"同行", r"分道扬镳", r"起点", r"终点"],
        },
        "LIFE_IS_GAME": {
            "source": "game",
            "target": "life",
            "keywords": ["赢", "输", "比赛", "竞争", "规则", "博弈", "胜者", "输家"],
            "patterns": [r"人生.*游戏", r"生活.*博弈", r"赢.*人生", r"输.*人生"],
        },
        "LOVE_IS_WAR": {
            "source": "war",
            "target": "love",
            "keywords": ["征服", "俘获", "投降", "攻陷", "俘虏", "沦陷"],
            "patterns": [r"征服.*心", r"俘获.*心", r"攻陷.*防线"],
        },
        "HAPPY_IS_UP": {
            "source": "up",
            "target": "happy",
            "keywords": ["高兴", "开心", "振奋", "昂扬", "情绪高涨", "兴高采烈", "精神振奋"],
            "patterns": [r"情绪.*高", r"精神.*振", r"心情.*好"],
        },
        "SAD_IS_DOWN": {
            "source": "down",
            "target": "sad",
            "keywords": ["低落", "沮丧", "心情沉重", "垂头丧气", "情绪低"],
            "patterns": [r"情绪.*低", r"心情.*沉", r"精神.*沉"],
        },
        "IDEAS_ARE_OBJECTS": {
            "source": "objects",
            "target": "ideas",
            "keywords": ["抓住", "丢弃", "持有", "传递", "提炼", "构建"],
            "patterns": [r"抓住.*想法", r"丢弃.*观念", r"构建.*思想"],
        },
        "UNDERSTANDING_IS_SEEING": {
            "source": "seeing",
            "target": "understanding",
            "keywords": ["看清", "明白", "洞察", "视野", "视角", "盲点"],
            "patterns": [r"看清.*本质", r"洞察.*问题", r"视野.*宽"],
        },
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

    async def get_metaphor_annotation(self, db: AsyncSession, annotation_id: str) -> Optional[MetaphorAnnotation]:
        """获取单条隐喻标注"""
        result = await db.execute(
            select(MetaphorAnnotation).where(MetaphorAnnotation.id == annotation_id)
        )
        return result.scalar_one_or_none()

    async def get_metaphor_annotations_by_video(
        self,
        db: AsyncSession,
        video_id: str,
        metaphor_type: Optional[str] = None,
    ) -> List[MetaphorAnnotation]:
        """获取视频的所有隐喻标注"""
        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        annotations = []
        for alignment in alignments:
            query = select(MetaphorAnnotation).where(MetaphorAnnotation.alignment_id == alignment.id)
            if metaphor_type:
                query = query.where(MetaphorAnnotation.type == metaphor_type)
            result = await db.execute(query)
            items = result.scalars().all()
            annotations.extend(items)

        return annotations

    async def create_metaphor_annotation(
        self,
        db: AsyncSession,
        alignment_id: str,
        metaphor_type: str,
        source_domain: Optional[str] = None,
        target_domain: Optional[str] = None,
        trigger: Optional[str] = None,
        confidence: Optional[float] = None,
        annotator: str = "auto",
    ) -> MetaphorAnnotation:
        """创建隐喻标注"""
        annotation = MetaphorAnnotation(
            alignment_id=alignment_id,
            type=metaphor_type,
            source_domain=source_domain,
            target_domain=target_domain,
            trigger=trigger,
            confidence=confidence,
            annotator=annotator,
        )
        db.add(annotation)
        await db.commit()
        await db.refresh(annotation)
        return annotation

    async def batch_create_metaphor_annotations(
        self,
        db: AsyncSession,
        annotations_data: List[Dict[str, Any]],
    ) -> List[MetaphorAnnotation]:
        """批量创建隐喻标注"""
        annotations = []
        for data in annotations_data:
            annotation = MetaphorAnnotation(
                alignment_id=data["alignment_id"],
                type=data.get("type", "conceptual"),
                source_domain=data.get("source_domain"),
                target_domain=data.get("target_domain"),
                trigger=data.get("trigger"),
                confidence=data.get("confidence", 0.5),
                annotator=data.get("annotator", "auto"),
            )
            db.add(annotation)
            annotations.append(annotation)
        await db.commit()
        for annotation in annotations:
            await db.refresh(annotation)
        return annotations

    def _detect_with_rules(self, text: str) -> List[Dict[str, Any]]:
        """使用规则引擎检测隐喻"""
        detected = []

        for metaphor_id, pattern in self.COMMON_METAPHORS.items():
            # 检查关键词
            for keyword in pattern.get("keywords", []):
                if keyword in text:
                    detected.append({
                        "type": "conceptual",
                        "metaphor_id": metaphor_id,
                        "source_domain": pattern["source"],
                        "target_domain": pattern["target"],
                        "trigger": keyword,
                        "confidence": 0.5,  # 规则引擎置信度较低
                        "method": "keyword",
                    })
                    break

            # 检查正则模式
            for regex in pattern.get("patterns", []):
                if re.search(regex, text):
                    detected.append({
                        "type": "conceptual",
                        "metaphor_id": metaphor_id,
                        "source_domain": pattern["source"],
                        "target_domain": pattern["target"],
                        "trigger": regex,
                        "confidence": 0.6,
                        "method": "pattern",
                    })
                    break

        return detected

    async def _detect_with_llm(self, text: str, language: str = "zh") -> List[Dict[str, Any]]:
        """使用 LLM 检测隐喻"""
        result = await self.llm_provider.analyze_metaphor(text, language)

        if result.get("success"):
            return result.get("metaphors", [])
        return []

    async def detect_metaphors(
        self,
        text: str,
        use_llm: bool = True,
        language: str = "zh",
    ) -> Dict[str, Any]:
        """
        检测文本中的隐喻

        Args:
            text: 待检测文本
            use_llm: 是否使用 LLM（优先规则后用 LLM）
            language: 语言代码

        Returns:
            {"success": bool, "metaphors": list, "rule_detected": int, "llm_detected": int}
        """
        result = {
            "success": True,
            "metaphors": [],
            "rule_detected": 0,
            "llm_detected": 0,
            "methods": [],
        }

        # 1. 先用规则引擎（快速，零成本）
        rule_results = self._detect_with_rules(text)
        result["metaphors"].extend(rule_results)
        result["rule_detected"] = len(rule_results)
        result["methods"].append("rule")

        # 2. 如果需要且可用，再用 LLM
        if use_llm and self.is_llm_available():
            llm_results = await self._detect_with_llm(text, language)
            result["llm_detected"] = len(llm_results)
            result["metaphors"].extend(llm_results)
            result["methods"].append("llm")
            result["llm_provider"] = self.llm_provider.config.provider if self.llm_provider.config else "unknown"
        elif use_llm and not self.is_llm_available():
            result["warning"] = "LLM API not available, using rules only"
            result["methods"].append("rule (llm unavailable)")

        # 去重（基于触发词）
        seen_triggers = set()
        unique_metaphors = []
        for m in result["metaphors"]:
            trigger = m.get("trigger", "")
            if trigger and trigger not in seen_triggers:
                seen_triggers.add(trigger)
                unique_metaphors.append(m)

        result["metaphors"] = unique_metaphors
        result["total"] = len(unique_metaphors)

        return result

    async def detect_conceptual_metaphors(
        self,
        db: AsyncSession,
        video_id: str,
        use_llm: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """检测视频中的概念隐喻"""
        result = {
            "success": False,
            "annotations": [],
            "total_metaphors": 0,
            "rule_detected": 0,
            "llm_detected": 0,
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
                # 获取文本内容
                text = await self._get_alignment_text(db, alignment)

                if text and len(text.strip()) > 0:
                    # 检测隐喻
                    detect_result = await self.detect_metaphors(text, use_llm=use_llm)

                    for metaphor in detect_result.get("metaphors", []):
                        annotations_data.append({
                            "alignment_id": alignment.id,
                            "type": metaphor.get("type", "conceptual"),
                            "source_domain": metaphor.get("source_domain"),
                            "target_domain": metaphor.get("target_domain"),
                            "trigger": metaphor.get("trigger"),
                            "confidence": metaphor.get("confidence", 0.5),
                            "annotator": "llm" if metaphor.get("method") == "llm" else "rule",
                        })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(alignments),
                        "percent": round((i + 1) / len(alignments) * 100, 2),
                    })

            # 批量创建标注
            if annotations_data:
                annotations = await self.batch_create_metaphor_annotations(db, annotations_data)
                result["annotations"] = [a.id for a in annotations]

            result["success"] = True
            result["total_metaphors"] = len(annotations_data)
            result["rule_detected"] = sum(1 for a in annotations_data if a.get("annotator") == "rule")
            result["llm_detected"] = sum(1 for a in annotations_data if a.get("annotator") == "llm")
            logger.info(f"隐喻检测完成: {result['total_metaphors']} 条 (规则: {result['rule_detected']}, LLM: {result['llm_detected']})")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"隐喻检测失败: {e}")

        return result

    async def detect_visual_metaphors(
        self,
        db: AsyncSession,
        video_id: str,
        use_llm: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """检测视觉隐喻"""
        result = {
            "success": False,
            "annotations": [],
            "total_metaphors": 0,
            "error": None,
        }

        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        try:
            annotations_data = []

            for i, alignment in enumerate(alignments):
                visual_desc = await self._get_visual_description(db, alignment)

                if visual_desc:
                    # 简单的视觉隐喻规则
                    detected = []

                    scene = visual_desc.get("scene", "")
                    objects = visual_desc.get("objects", [])

                    # 示例：检测"爱情"视觉隐喻（心形图案）
                    for obj in objects:
                        if "heart" in obj.get("label", "").lower() or "心" in obj.get("label", ""):
                            detected.append({
                                "type": "visual",
                                "source_domain": "heart",
                                "target_domain": "love",
                                "trigger": f"物体: {obj.get('label')}",
                                "confidence": 0.7,
                                "annotator": "rule",
                            })

                    for metaphor in detected:
                        annotations_data.append({
                            "alignment_id": alignment.id,
                            **metaphor,
                        })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(alignments),
                        "percent": round((i + 1) / len(alignments) * 100, 2),
                    })

            if annotations_data:
                annotations = await self.batch_create_metaphor_annotations(db, annotations_data)
                result["annotations"] = [a.id for a in annotations]

            result["success"] = True
            result["total_metaphors"] = len(annotations_data)

        except Exception as e:
            result["error"] = str(e)

        return result

    async def detect_multimodal_metaphors(
        self,
        db: AsyncSession,
        video_id: str,
        use_llm: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """检测多模态隐喻"""
        result = {
            "success": False,
            "annotations": [],
            "total_metaphors": 0,
            "error": None,
        }

        alignments_result = await db.execute(
            select(MultimodalAlignment).where(MultimodalAlignment.video_id == video_id)
        )
        alignments = alignments_result.scalars().all()

        try:
            annotations_data = []

            for i, alignment in enumerate(alignments):
                text = await self._get_alignment_text(db, alignment)
                visual_desc = await self._get_visual_description(db, alignment)

                if text and visual_desc:
                    # 简单检测：文本隐喻和视觉元素协同
                    text_metaphors = self._detect_with_rules(text)
                    visual_desc_str = str(visual_desc)

                    for tm in text_metaphors:
                        # 检查视觉描述是否包含相关元素
                        if any(keyword in visual_desc_str for keyword in tm.get("source_domain", "").split()):
                            annotations_data.append({
                                "alignment_id": alignment.id,
                                "type": "multimodal",
                                "source_domain": tm.get("source_domain"),
                                "target_domain": tm.get("target_domain"),
                                "trigger": f"文本+视觉: {tm.get('trigger')}",
                                "confidence": 0.85,  # 多模态协同置信度更高
                                "annotator": "rule",
                            })

                if progress_callback:
                    progress_callback({
                        "current": i + 1,
                        "total": len(alignments),
                        "percent": round((i + 1) / len(alignments) * 100, 2),
                    })

            if annotations_data:
                annotations = await self.batch_create_metaphor_annotations(db, annotations_data)
                result["annotations"] = [a.id for a in annotations]

            result["success"] = True
            result["total_metaphors"] = len(annotations_data)

        except Exception as e:
            result["error"] = str(e)

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

    async def delete_metaphor_annotations_by_video(self, db: AsyncSession, video_id: str) -> int:
        """删除视频的所有隐喻标注"""
        annotations = await self.get_metaphor_annotations_by_video(db, video_id)
        count = 0
        for annotation in annotations:
            await db.delete(annotation)
            count += 1
        await db.commit()
        return count


# 单例实例
metaphor_service = MetaphorService()
