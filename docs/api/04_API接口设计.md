# API 接口设计文档

**版本**: v0.1.0
**更新日期**: 2026-06-30

---

## 一、API 概览

### 1.1 接口规范

| 项目 | 规范 |
|------|------|
| 基础路径 | `/api/v1` |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |
| 认证方式 | Bearer Token (可选) |
| 分页 | `page`, `page_size` |

### 1.2 响应格式

**成功响应**：
```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

**错误响应**：
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

### 1.3 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |

---

## 二、视频管理接口

### 2.1 创建视频任务

**POST** `/api/v1/videos`

**请求体**：
```json
{
  "url": "https://www.youtube.com/watch?v=xxx",
  "platform": "youtube",
  "preferred_resolution": "1080p"
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "url": "https://www.youtube.com/watch?v=xxx",
    "platform": "youtube",
    "title": "示例视频",
    "status": "pending",
    "created_at": "2026-06-30T10:00:00Z"
  }
}
```

### 2.2 获取视频列表

**GET** `/api/v1/videos`

**查询参数**：
| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| page | int | 页码 | 1 |
| page_size | int | 每页数量 | 10 |
| status | string | 状态筛选 | - |
| platform | string | 平台筛选 | - |

**响应**：
```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 10,
    "total_pages": 10
  }
}
```

### 2.3 获取视频详情

**GET** `/api/v1/videos/{video_id}`

**响应**：
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "url": "https://www.youtube.com/watch?v=xxx",
    "platform": "youtube",
    "title": "示例视频",
    "duration": 120,
    "resolution": "1080p",
    "status": "done",
    "file_path": "/data/videos/xxx.mp4",
    "file_size": 104857600,
    "created_at": "2026-06-30T10:00:00Z",
    "updated_at": "2026-06-30T10:05:00Z"
  }
}
```

### 2.4 删除视频

**DELETE** `/api/v1/videos/{video_id}`

**响应**：
```json
{
  "success": true,
  "message": "视频删除成功"
}
```

### 2.5 批量创建视频任务

**POST** `/api/v1/videos/batch`

**请求体**：
```json
{
  "urls": [
    {"url": "https://youtube.com/watch?v=xxx1", "platform": "youtube"},
    {"url": "https://bilibili.com/video/xxx2", "platform": "bilibili"}
  ]
}
```

---

## 三、任务处理接口

### 3.1 获取任务状态

**GET** `/api/v1/tasks/{task_id}`

**响应**：
```json
{
  "success": true,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "progress": 45,
    "current_step": "frame_extraction",
    "steps": [
      {"name": "download", "status": "done", "progress": 100},
      {"name": "frame_extraction", "status": "processing", "progress": 45},
      {"name": "subtitle_extraction", "status": "pending", "progress": 0}
    ],
    "created_at": "2026-06-30T10:00:00Z"
  }
}
```

### 3.2 开始处理

**POST** `/api/v1/tasks/{task_id}/process`

**请求体**：
```json
{
  "steps": ["download", "frame", "subtitle", "audio", "visual", "alignment", "metaphor", "untranslatability"]
}
```

**响应**：
```json
{
  "success": true,
  "message": "任务开始处理",
  "data": {
    "task_id": "xxx",
    "status": "processing"
  }
}
```

### 3.3 取消任务

**POST** `/api/v1/tasks/{task_id}/cancel`

**响应**：
```json
{
  "success": true,
  "message": "任务已取消"
}
```

---

## 四、帧提取接口

### 4.1 提取帧

**POST** `/api/v1/frames/extract`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "fps": 1.0,
  "quality": 2
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "success": true,
    "frames": ["frame_id_1", "frame_id_2"],
    "total_frames": 120
  }
}
```

### 4.2 获取帧列表

**GET** `/api/v1/frames?video_id={video_id}`

**查询参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| video_id | string | 视频ID |
| start_time | float | 开始时间 |
| end_time | float | 结束时间 |

### 4.3 检测字幕帧

**POST** `/api/v1/frames/detect-subtitles`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 五、字幕接口

### 5.1 提取内嵌字幕

**POST** `/api/v1/subtitles/extract-embedded`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "zh"
}
```

### 5.2 OCR 字幕识别

**POST** `/api/v1/subtitles/ocr`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 5.3 获取字幕列表

**GET** `/api/v1/subtitles?video_id={video_id}`

---

## 六、音频接口

### 6.1 提取音频

**POST** `/api/v1/audio/extract`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "format": "wav",
  "sample_rate": 16000
}
```

### 6.2 ASR 语音识别

**POST** `/api/v1/audio/asr`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "base",
  "language": null
}
```

---

## 七、视觉分析接口

### 7.1 分析单帧

**POST** `/api/v1/visual/analyze-frame`

**请求体**：
```json
{
  "frame_id": "xxx",
  "enable_description": true,
  "enable_object_detection": true,
  "enable_scene_classification": true
}
```

### 7.2 分析视频帧

**POST** `/api/v1/visual/analyze-video`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 八、多模态对齐接口

### 8.1 执行时间轴对齐

**POST** `/api/v1/alignment/time`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "time_tolerance": 0.5
}
```

### 8.2 执行语义对齐

**POST** `/api/v1/alignment/semantic`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000",
  "semantic_threshold": 0.7
}
```

### 8.3 获取对齐时间线

**GET** `/api/v1/alignment/timeline?video_id={video_id}`

---

## 九、隐喻标注接口

### 9.1 检测概念隐喻

**POST** `/api/v1/metaphors/detect-conceptual`

**请求体**：
```json
{
  "video_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 9.2 检测视觉隐喻

**POST** `/api/v1/metaphors/detect-visual`

### 9.3 检测多模态隐喻

**POST** `/api/v1/metaphors/detect-multimodal`

### 9.4 获取隐喻列表

**GET** `/api/v1/metaphors?video_id={video_id}&type={type}`

### 9.5 更新隐喻标注

**PUT** `/api/v1/metaphors/{annotation_id}`

**请求体**：
```json
{
  "type": "conceptual",
  "source_domain": "journey",
  "target_domain": "life",
  "confidence": 0.95
}
```

---

## 十、不可译性标注接口

### 10.1 检测语言不可译

**POST** `/api/v1/untranslatability/detect-linguistic`

### 10.2 检测文化不可译

**POST** `/api/v1/untranslatability/detect-cultural`

### 10.3 检测语境不可译

**POST** `/api/v1/untranslatability/detect-contextual`

### 10.4 获取不可译性列表

**GET** `/api/v1/untranslatability?video_id={video_id}&type={type}`

### 10.5 获取统计信息

**GET** `/api/v1/untranslatability/statistics?video_id={video_id}`

---

## 十一、语料输出接口

### 11.1 获取语料

**GET** `/api/v1/corpus/{video_id}`

**查询参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| include_subtitles | bool | 包含字幕 |
| include_audio | bool | 包含音频 |
| include_visual | bool | 包含视觉 |
| include_annotations | bool | 包含标注 |

### 11.2 导出 JSON

**GET** `/api/v1/corpus/{video_id}/export/json`

### 11.3 导出 CSV

**GET** `/api/v1/corpus/{video_id}/export/csv`

### 11.4 批量导出

**POST** `/api/v1/corpus/export/batch`

**请求体**：
```json
{
  "video_ids": ["id1", "id2", "id3"],
  "format": "json",
  "output_path": "/data/exports"
}
```

### 11.5 生成统计报告

**GET** `/api/v1/corpus/{video_id}/report`

---

## 十二、WebSocket 接口

### 12.1 任务进度推送

**连接**：`ws://host/ws/tasks/{task_id}`

**推送消息**：
```json
{
  "type": "progress",
  "task_id": "xxx",
  "progress": 45,
  "current_step": "frame_extraction"
}
```

---

*API 接口文档持续更新中*
