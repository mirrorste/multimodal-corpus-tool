# Services 模块设计文档

**版本**: v0.1.0
**更新日期**: 2026-06-30

---

## 一、模块概述

Services 层是业务逻辑的核心，负责处理各模块的具体功能实现。每个服务对应一个功能领域，通过依赖注入实现模块解耦。

### 1.1 服务列表

| 服务 | 文件 | 职责 |
|------|------|------|
| VideoService | video_service.py | 视频管理 |
| VideoDownloader | video_downloader.py | 视频下载 |
| FrameService | frame_service.py | 帧提取 |
| SubtitleService | subtitle_service.py | 字幕提取 |
| AudioService | audio_service.py | 音频处理 |
| VisualService | visual_service.py | 视觉分析 |
| AlignmentService | alignment_service.py | 多模态对齐 |
| MetaphorService | metaphor_service.py | 隐喻识别 |
| UntranslatabilityService | untranslatability_service.py | 不可译性识别 |
| CorpusService | corpus_service.py | 语料输出 |

---

## 二、视频服务 (VideoService)

### 2.1 类定义

```python
class VideoService:
    """视频管理服务"""
```

### 2.2 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `create_video()` | 创建视频记录 | Video |
| `get_video()` | 获取视频 | Video |
| `list_videos()` | 列表查询 | list[Video] |
| `update_video()` | 更新视频 | Video |
| `delete_video()` | 删除视频 | bool |
| `start_download()` | 开始下载 | Video |
| `process_video()` | 处理视频 | dict |

### 2.3 数据模型

```python
# 输入模型
class VideoCreate(BaseModel):
    url: str
    platform: str
    preferred_resolution: str = "1080p"

# 输出模型
class VideoResponse(BaseModel):
    id: str
    url: str
    platform: str
    title: Optional[str]
    duration: Optional[int]
    resolution: Optional[str]
    status: str
    file_path: Optional[str]
    created_at: datetime
```

---

## 三、视频下载器 (VideoDownloader)

### 3.1 类定义

```python
class VideoDownloader:
    """多平台视频下载器"""
```

### 3.2 支持平台

| 平台 | 类名 | 支持功能 |
|------|------|----------|
| YouTube | YouTubeDownloader | 多种分辨率、字幕下载 |
| Bilibili | BilibiliDownloader | 弹幕下载、番剧支持 |
| Vimeo | VimeoDownloader | 专业视频 |
| 本地文件 | LocalFileHandler | 格式转换 |

### 3.3 核心方法

| 方法 | 说明 | 参数 |
|------|------|------|
| `download()` | 下载视频 | url, output_dir, options |
| `get_info()` | 获取视频信息 | url |
| `extract_subtitle()` | 下载字幕 | url, language |

### 3.4 使用示例

```python
downloader = VideoDownloader()

# 下载视频
result = await downloader.download(
    url="https://youtube.com/watch?v=xxx",
    output_dir="/data/videos",
    resolution="1080p",
    progress_callback=lambda p: print(f"进度: {p}%")
)

# 获取视频信息
info = await downloader.get_info(url)
```

---

## 四、帧提取服务 (FrameService)

### 4.1 类定义

```python
class FrameService:
    """帧提取服务 - 从视频中提取关键帧"""
```

### 4.2 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `extract_frames()` | 提取帧 | dict |
| `extract_key_frames()` | 提取关键帧 | dict |
| `detect_subtitle_frames()` | 检测字幕帧 | dict |
| `get_frames_by_video()` | 获取帧列表 | list[Frame] |
| `batch_create_frames()` | 批量创建 | list[Frame] |

### 4.3 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| fps | float | 1.0 | 每秒提取帧数 |
| quality | int | 2 | 图片质量 1-5 |
| format | str | "jpg" | 输出格式 |

### 4.4 处理流程

```
1. 验证视频文件存在
2. 创建帧存储目录
3. 调用 FFmpeg 提取帧
4. 获取帧文件列表
5. 计算时间戳和质量分数
6. 批量创建数据库记录
```

---

## 五、字幕提取服务 (SubtitleService)

### 5.1 类定义

```python
class SubtitleService:
    """字幕提取服务 - 从视频提取字幕"""
```

### 5.2 字幕来源

| 来源 | 方法 | 说明 |
|------|------|------|
| 内嵌字幕 | `extract_embedded_subtitles()` | FFmpeg 提取字幕轨道 |
| OCR 硬字幕 | `extract_ocr_subtitles()` | PaddleOCR 识别 |

### 5.3 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `extract_embedded_subtitles()` | 提取内嵌字幕 | dict |
| `extract_ocr_subtitles()` | OCR 识别 | dict |
| `get_subtitles_by_video()` | 获取字幕列表 | list[Subtitle] |
| `_merge_adjacent_subtitles()` | 合并相邻字幕 | list |

### 5.4 OCR 配置

```python
class OCRConfig:
    engine: str = "paddleocr"  # paddleocr, tesseract
    language: str = "ch"  # ch, en, ja, ko
    use_angle_cls: bool = True
```

---

## 六、音频服务 (AudioService)

### 6.1 类定义

```python
class AudioService:
    """音频提取服务 - 音频提取和 ASR"""
```

### 6.2 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `extract_audio()` | 提取完整音频 | dict |
| `extract_audio_segments()` | 提取音频片段 | dict |
| `perform_asr()` | 语音识别 | dict |
| `get_audio_segments_by_video()` | 获取片段列表 | list[AudioSegment] |

### 6.3 配置参数

```python
class AudioExtractionConfig:
    format: str = "wav"      # wav, mp3, flac
    sample_rate: int = 16000 # 采样率
    channels: int = 1        # 声道数
    bitrate: Optional[str] = None

class ASRConfig:
    model: str = "whisper"   # whisper, google, azure
    language: Optional[str] = None  # 自动检测
    task: str = "transcribe" # transcribe, translate
```

### 6.4 ASR 处理流程

```
1. 提取完整音频
2. 加载 Whisper 模型
3. 执行语音转文字
4. 解析识别结果
5. 批量创建音频片段记录
```

---

## 七、视觉分析服务 (VisualService)

### 7.1 类定义

```python
class VisualService:
    """视觉描述服务 - 图像分析和描述生成（低GPU依赖）"""
```

### 7.2 分析功能

| 功能 | 本地模型 | 云端API | 说明 |
|------|----------|---------|------|
| 图像描述 | ❌ 不支持 | DeepSeek/阿里云 | 云端生成描述 |
| 物体检测 | YOLOv8n (CPU) | 可选API | 轻量检测 |
| 场景分类 | ❌ | 云端API | 分类场景 |
| 情感检测 | ❌ | 云端API | 人脸情感 |

> 实际代码使用 `vision_provider.py`，支持本地/API混合模式

### 7.3 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `analyze_frame()` | 分析单帧 | dict |
| `analyze_video_frames()` | 分析所有帧 | dict |
| `_generate_description()` | 生成描述 | dict |
| `_detect_objects()` | 物体检测 | dict |
| `_classify_scene()` | 场景分类 | dict |
| `_detect_emotions()` | 情感检测 | dict |

### 7.4 输出格式

```python
{
    "description_id": "xxx",
    "description": "一个人在咖啡馆里工作",
    "objects": [
        {"label": "person", "confidence": 0.95, "bbox": [100, 50, 200, 300]},
        {"label": "cup", "confidence": 0.85, "bbox": [150, 200, 180, 250]}
    ],
    "scene": "office",
    "emotions": [
        {"label": "focused", "confidence": 0.8}
    ],
    "confidence": 0.9
}
```

---

## 八、多模态对齐服务 (AlignmentService)

### 8.1 类定义

```python
class AlignmentService:
    """多模态对齐服务 - 时间轴和语义对齐"""
```

### 8.2 对齐策略

| 策略 | 方法 | 说明 |
|------|------|------|
| 时间对齐 | `perform_time_alignment()` | 基于时间戳对齐 |
| 语义对齐 | `perform_semantic_alignment()` | 基于文本相似度 |

### 8.3 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `perform_time_alignment()` | 时间轴对齐 | dict |
| `perform_semantic_alignment()` | 语义对齐 | dict |
| `get_aligned_timeline()` | 获取时间线 | list[dict] |
| `_align_by_time()` | 时间聚合 | list |
| `_calculate_semantic_similarity()` | 语义相似度 | float |

### 8.4 对齐配置

```python
class AlignmentConfig:
    time_tolerance: float = 0.5      # 时间容差（秒）
    semantic_threshold: float = 0.7  # 语义相似度阈值
    enable_semantic_alignment: bool = True
```

---

## 九、隐喻识别服务 (MetaphorService)

### 9.1 类定义

```python
class MetaphorService:
    """隐喻识别服务 - 概念、视觉、多模态隐喻"""
```

### 9.2 隐喻类型

| 类型 | 说明 | 检测方法 |
|------|------|----------|
| conceptual | 概念隐喻 | 关键词匹配 + NLP |
| visual | 视觉隐喻 | 图像分析 |
| multimodal | 多模态隐喻 | 跨模态关联 |

### 9.3 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `detect_conceptual_metaphors()` | 概念隐喻 | dict |
| `detect_visual_metaphors()` | 视觉隐喻 | dict |
| `detect_multimodal_metaphors()` | 多模态隐喻 | dict |
| `_detect_metaphors_in_text()` | 文本隐喻检测 | list |
| `_detect_visual_metaphor()` | 视觉隐喻检测 | list |
| `_detect_multimodal_metaphor()` | 多模态隐喻检测 | list |

### 9.4 概念隐喻库

```python
COMMON_CONCEPTUAL_METAPHORS = {
    "TIME_IS_MONEY": {
        "source_domain": "money",
        "target_domain": "time",
        "keywords": ["花费", "浪费", "节约", "投资"],
    },
    "LIFE_IS_A_JOURNEY": {
        "source_domain": "journey",
        "target_domain": "life",
        "keywords": ["路", "道路", "旅程", "同行"],
    },
    # ... 更多隐喻类型
}
```

---

## 十、不可译性识别服务 (UntranslatabilityService)

### 10.1 类定义

```python
class UntranslatabilityService:
    """不可译性识别服务 - 语言、文化、语境层面"""
```

### 10.2 不可译类型

| 类型 | 类别 | 说明 |
|------|------|------|
| linguistic | phonological | 语音不可译 |
| linguistic | morphological | 形态不可译 |
| linguistic | syntactic | 句法不可译 |
| linguistic | semantic | 语义不可译 |
| cultural | idiom | 习语 |
| cultural | reference | 文化指涉 |
| contextual | discourse | 话语语境 |
| contextual | pragmatic | 语用语境 |

### 10.3 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `detect_linguistic_untranslatability()` | 语言不可译 | dict |
| `detect_cultural_untranslatability()` | 文化不可译 | dict |
| `detect_contextual_untranslatability()` | 语境不可译 | dict |
| `get_untranslatability_statistics()` | 统计信息 | dict |

### 10.4 文化专有项库

```python
CULTURAL_SPECIFIC_ITEMS = {
    "zh": {
        "idioms": ["龙", "凤", "春节", "功夫"],
        "social_terms": ["面子", "人情", "关系"],
    },
    "en": {
        "idioms": ["break a leg", "piece of cake"],
        "cultural_refs": ["Thanksgiving", "Super Bowl"],
    },
}
```

---

## 十一、语料输出服务 (CorpusService)

### 11.1 类定义

```python
class CorpusService:
    """语料输出服务 - 生成标准化多模态语料"""
```

### 11.2 导出格式

| 格式 | 方法 | 说明 |
|------|------|------|
| JSON | `export_to_json()` | 完整语料结构 |
| CSV | `export_to_csv()` | 表格化数据 |
| 标注文件 | `export_annotations_file()` | 纯标注数据 |

### 11.3 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `get_video_corpus()` | 获取语料 | CorpusOutput |
| `export_to_json()` | JSON 导出 | dict |
| `export_to_csv()` | CSV 导出 | dict |
| `batch_export()` | 批量导出 | dict |
| `generate_statistics_report()` | 统计报告 | dict |

### 11.4 输出格式

```python
class CorpusOutput(BaseModel):
    video_info: VideoInfo
    timeline: list[TimelineEntry]
    metadata: dict

class TimelineEntry(BaseModel):
    timestamp: float
    subtitle: Optional[dict]  # {"text": "", "language": ""}
    audio: Optional[dict]     # {"asr_text": "", "language": ""}
    visual: Optional[dict]    # {"description": "", "objects": []}
    annotations: Optional[dict]  # {"metaphors": [], "untranslatability": []}
```

---

## 十二、服务依赖关系

```
┌─────────────────────┐
│   VideoService     │
└──────────┬─────────┘
           │
           ▼
┌─────────────────────┐     ┌─────────────────────┐
│ VideoDownloader     │     │   FrameService      │
└──────────┬──────────┘     └──────────┬──────────┘
           │                            │
           ▼                            ▼
┌─────────────────────┐     ┌─────────────────────┐
│   SubtitleService  │     │   AudioService      │
│ (OCR + Embedded)   │     │   (Whisper ASR)    │
└──────────┬──────────┘     └──────────┬──────────┘
           │                            │
           └─────────────┬──────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  VisualService     │
              │  (BLIP-2 + YOLOv8)│
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ AlignmentService   │
              └──────────┬──────────┘
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│MetaphorService│  │ UntransService│  │CorpusService │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

*Services 模块设计文档持续更新中*
