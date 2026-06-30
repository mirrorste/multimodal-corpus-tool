# 多模态语料获取工具 - 项目进度表

**项目版本**: v0.3.0
**更新日期**: 2026-06-30
**当前阶段**: 第一阶段完成，第二阶段准备启动
**整体进度**: ██████████░░░░░░░░░░ 40%
**测试状态**: ✅ 数据库迁移配置完成，API接口测试通过

---

## 一、总体进度概览

| 阶段 | 计划时间 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **第一阶段**：基础框架搭建，视频下载功能 | 第 1-4 周 | ✅ 已完成 | 95% | 视频下载核心逻辑已实现，批量下载已完成，桌面应用已打包，ffmpeg已内置，数据库迁移已配置，API测试通过 |
| **第二阶段**：帧提取、字幕提取、音频提取 | 第 5-8 周 | ⏳ 未开始 | 0% | 数据模型已定义，业务逻辑未实现 |
| **第三阶段**：图像描述、多模态对齐 | 第 9-12 周 | ⏳ 未开始 | 0% | 数据模型已定义，业务逻辑未实现 |
| **第四阶段**：隐喻识别、不可译性识别 | 第 13-16 周 | ⏳ 未开始 | 0% | 数据模型已定义，业务逻辑未实现 |
| **第五阶段**：语料输出、用户界面 | 第 17-20 周 | ⏳ 未开始 | 5% | 前端页面骨架已搭建 |

---

## 二、功能模块进度详情

### 2.1 视频资源获取模块（FR-001 ~ FR-008）

**整体完成度: ██████████░░░░░░░░░░ 80%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-001 | YouTube 视频下载 | 高 | ✅ 已完成 | 100% | yt-dlp集成，支持异步下载，已验证 |
| FR-002 | Bilibili 视频下载 | 高 | ✅ 已完成 | 95% | yt-dlp集成，支持Cookies登录，批量下载已验证 |
| FR-003 | Vimeo 视频下载 | 中 | ✅ 已完成 | 90% | yt-dlp集成，支持异步下载 |
| FR-004 | 本地视频文件导入 | 高 | ✅ 已完成 | 85% | 文件上传API已实现，支持多种格式，大小限制 |
| FR-005 | 视频分辨率选择 | 中 | ✅ 已完成 | 100% | 前端表单和后端Schema已支持，下载时应用 |
| FR-006 | 批量导入视频链接 | 高 | ✅ 已完成 | 95% | 批量创建API、批量下载、批量取消、批量删除已实现 |
| FR-007 | 下载进度与状态显示 | 中 | ✅ 已完成 | 95% | 实时进度跟踪（百分比、字节数），多状态管理，单位显示正确 |
| FR-008 | 断点续传 | 低 | ❌ 未开始 | 0% | 未实现 |

**相关代码**:
- 后端API: [videos.py](file:///workspace/backend/app/api/v1/videos.py)
- 下载服务: [video_downloader.py](file:///workspace/backend/app/services/video_downloader.py)
- 视频服务: [video_service.py](file:///workspace/backend/app/services/video_service.py)
- 数据模型: [video.py](file:///workspace/backend/app/models/video.py)
- 前端组件: [TaskList.tsx](file:///workspace/frontend/src/components/TaskList.tsx)

---

### 2.2 帧提取模块（FR-009 ~ FR-015）

**整体完成度: ██░░░░░░░░░░░░░░░░░░ 15%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-009 | 字幕时间戳检测 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-010 | 关键帧提取 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-011 | 自定义帧提取频率 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-012 | 提取所有帧 | 低 | ❌ 未开始 | 0% | 未实现 |
| FR-013 | 帧质量设置 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-014 | 自动去除低质量帧 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-015 | 帧按时间顺序存储 | 高 | ⚠️ 部分完成 | 80% | 数据模型已定义（含timestamp、frame_number） |

**相关代码**:
- 数据模型: [frame.py](file:///workspace/backend/app/models/frame.py)

---

### 2.3 多模态内容提取模块

#### 2.3.1 字幕提取（FR-016 ~ FR-020）

**整体完成度: ██░░░░░░░░░░░░░░░░░░ 15%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-016 | 内嵌字幕轨道提取 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-017 | OCR 硬字幕识别 | 高 | ❌ 未开始 | 0% | 未实现（依赖已安装：paddleocr） |
| FR-018 | 多语言字幕识别 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-019 | 字幕时间轴校正 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-020 | 字幕分段与分句 | 高 | ❌ 未开始 | 0% | 未实现 |

**相关代码**:
- 数据模型: [subtitle.py](file:///workspace/backend/app/models/subtitle.py)

#### 2.3.2 原声提取（FR-021 ~ FR-025）

**整体完成度: █░░░░░░░░░░░░░░░░░░░ 10%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-021 | 音频轨道提取 | 高 | ❌ 未开始 | 0% | 未实现（依赖已安装：ffmpeg-python） |
| FR-022 | 按时间戳提取音频片段 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-023 | 音频降噪处理 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-024 | ASR 语音识别 | 高 | ❌ 未开始 | 0% | 未实现（依赖已安装：openai-whisper） |
| FR-025 | 多语言语音识别 | 中 | ❌ 未开始 | 0% | 未实现 |

**相关代码**:
- 数据模型: [audio_segment.py](file:///workspace/backend/app/models/audio_segment.py)

#### 2.3.3 画面描述（FR-026 ~ FR-030）

**整体完成度: █░░░░░░░░░░░░░░░░░░░ 10%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-026 | 图像描述生成 | 高 | ❌ 未开始 | 0% | 未实现（依赖已安装：transformers、torch） |
| FR-027 | 物体检测与识别 | 中 | ❌ 未开始 | 0% | 未实现（依赖已安装：torchvision） |
| FR-028 | 场景分类 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-029 | 情感/情绪识别 | 低 | ❌ 未开始 | 0% | 未实现 |
| FR-030 | 视觉显著性检测 | 中 | ❌ 未开始 | 0% | 未实现 |

**相关代码**:
- 数据模型: [visual_description.py](file:///workspace/backend/app/models/visual_description.py)

#### 2.3.4 多模态对齐（FR-031 ~ FR-034）

**整体完成度: █░░░░░░░░░░░░░░░░░░░ 10%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-031 | 时间轴对齐 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-032 | 语义对齐 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-033 | 对齐可视化展示 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-034 | 手动校正对齐结果 | 中 | ❌ 未开始 | 0% | 未实现 |

**相关代码**:
- 数据模型: [multimodal_alignment.py](file:///workspace/backend/app/models/multimodal_alignment.py)

---

### 2.4 隐喻与不可译性识别模块（FR-035 ~ FR-043）

**整体完成度: █░░░░░░░░░░░░░░░░░░░ 8%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-035 | 概念隐喻识别 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-036 | 视觉隐喻识别 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-037 | 多模态隐喻识别 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-038 | 文化专有项识别 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-039 | 语言不可译识别 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-040 | 文化不可译识别 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-041 | 语境不可译识别 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-042 | 自定义隐喻规则 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-043 | 不可译性分类配置 | 中 | ❌ 未开始 | 0% | 未实现 |

**相关代码**:
- 数据模型: [metaphor_annotation.py](file:///workspace/backend/app/models/metaphor_annotation.py)
- 数据模型: [untranslatability_annotation.py](file:///workspace/backend/app/models/untranslatability_annotation.py)
- API接口: [annotations.py](file:///workspace/backend/app/api/v1/annotations.py)（占位符）

---

### 2.5 语料输出模块（FR-044 ~ FR-050）

**整体完成度: ██░░░░░░░░░░░░░░░░░░ 12%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-044 | JSON 格式语料输出 | 高 | ⚠️ 部分完成 | 30% | 接口结构已定义，返回空timeline |
| FR-045 | CSV 格式语料输出 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-046 | 标注文件输出 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-047 | 多模态对齐时间线输出 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-048 | 自定义输出字段配置 | 中 | ❌ 未开始 | 0% | 未实现 |
| FR-049 | 批量输出语料 | 高 | ❌ 未开始 | 0% | 未实现 |
| FR-050 | 语料统计报告 | 中 | ❌ 未开始 | 0% | 未实现 |

**相关代码**:
- API接口: [corpus.py](file:///workspace/backend/app/api/v1/corpus.py)（占位符）

---

### 2.6 用户界面模块（FR-051 ~ FR-058）

**整体完成度: ██████████░░░░░░░░░░ 55%**

| 需求编号 | 需求描述 | 优先级 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FR-051 | 桌面图形化界面 | 高 | ✅ 已完成 | 100% | PyWebView 原生桌面窗口 + FastAPI 后端，无需浏览器 |
| FR-052 | 视频链接输入与列表管理 | 高 | ✅ 已完成 | 100% | 添加、批量添加、列表、搜索、删除功能已实现 |
| FR-053 | 处理流程配置 | 高 | ⚠️ 部分完成 | 50% | 分辨率选项已配置，Cookies 设置已支持 |
| FR-054 | 实时任务处理进度 | 高 | ✅ 已完成 | 90% | 实时进度条、状态标签、百分比、文件大小显示 |
| FR-055 | 单条语料详情展示 | 高 | ⚠️ 部分完成 | 50% | 视频详情面板已实现，语料详情未实现 |
| FR-056 | 语料搜索与筛选 | 中 | ✅ 已完成 | 60% | 视频搜索、状态筛选已实现 |
| FR-057 | 标注结果审核与修正 | 中 | ⚠️ 部分完成 | 15% | 页面框架已搭建，无实际数据 |
| FR-058 | 导出配置保存与复用 | 中 | ⚠️ 部分完成 | 30% | 设置保存功能已实现 |

**相关代码**:
- 主应用: [App.tsx](file:///workspace/frontend/src/App.tsx)
- 任务列表: [TaskList.tsx](file:///workspace/frontend/src/components/TaskList.tsx)
- 视频详情: [VideoDetail.tsx](file:///workspace/frontend/src/components/VideoDetail.tsx)
- 语料库: [CorpusList.tsx](file:///workspace/frontend/src/components/CorpusList.tsx)
- 标注管理: [AnnotationList.tsx](file:///workspace/frontend/src/components/AnnotationList.tsx)

---

## 三、技术架构进度

### 3.1 后端架构

| 层级 | 技术 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| Web框架 | FastAPI | ✅ 已完成 | 100% | 已配置并运行 |
| ORM | SQLAlchemy 2.0 | ✅ 已完成 | 100% | 异步版本已配置 |
| 数据库 | PostgreSQL / SQLite | ✅ 已完成 | 95% | 连接已配置，Alembic迁移已配置，初始迁移脚本已创建，支持SQLite和PostgreSQL |
| 缓存/队列 | Redis + Celery | ⚠️ 部分完成 | 20% | 依赖已安装，未实际使用 |
| 对象存储 | MinIO | ⚠️ 部分完成 | 10% | 配置已定义，未实际使用 |
| 视频下载 | yt-dlp | ✅ 已完成 | 95% | 已集成到业务逻辑，支持多平台异步下载、批量操作、进度跟踪、标题解析 |
| 视频处理 | FFmpeg | ✅ 已完成 | 80% | 已内置到桌面应用包，下载时自动使用，支持最佳画质合并 |
| 桌面应用 | PyWebView | ✅ 已完成 | 90% | 原生桌面窗口，内置ffmpeg，零依赖运行，已打包成exe |
| OCR | PaddleOCR | ⚠️ 部分完成 | 5% | 依赖已安装，未集成 |
| ASR | Whisper | ⚠️ 部分完成 | 5% | 依赖已安装，未集成 |
| NLP | Transformers | ⚠️ 部分完成 | 5% | 依赖已安装，未集成 |

### 3.2 前端架构

| 层级 | 技术 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 前端框架 | React 18 | ✅ 已完成 | 100% | 已配置并运行 |
| UI组件库 | Ant Design 5 | ✅ 已完成 | 100% | 已集成 |
| 路由 | React Router v6 | ✅ 已完成 | 100% | 已配置4个主要路由 |
| HTTP客户端 | Axios | ✅ 已完成 | 100% | 已配置代理 |
| 状态管理 | - | ❌ 未开始 | 0% | 未使用状态管理库 |
| 图表 | Recharts | ⚠️ 部分完成 | 10% | 依赖已安装，未使用 |

---

## 四、数据模型进度

**整体完成度: ██████████████████░░ 90%**

| 数据实体 | 状态 | 完成度 | 说明 |
| :--- | :--- | :--- | :--- |
| Video（视频） | ✅ 已完成 | 100% | 完整字段定义 |
| Frame（帧） | ✅ 已完成 | 100% | 完整字段定义 |
| Subtitle（字幕） | ✅ 已完成 | 100% | 完整字段定义 |
| AudioSegment（音频片段） | ✅ 已完成 | 100% | 完整字段定义 |
| VisualDescription（画面描述） | ✅ 已完成 | 100% | 完整字段定义 |
| MultimodalAlignment（多模态对齐） | ✅ 已完成 | 100% | 完整字段定义 |
| MetaphorAnnotation（隐喻标注） | ✅ 已完成 | 100% | 完整字段定义 |
| UntranslatabilityAnnotation（不可译标注） | ✅ 已完成 | 100% | 完整字段定义 |

---

## 五、API 接口进度

**整体完成度: █████████░░░░░░░░░░░ 45%**

| 模块 | 接口数 | 已实现 | 占位符 | 未实现 | 完成度 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 视频管理 | 12 | 12 | 0 | 0 | 95%（含下载、上传、进度、信息查询、批量操作） |
| 处理任务 | 4 | 4 | 0 | 0 | 70%（触发下载、进度查询、取消、列表） |
| 系统设置 | 2 | 2 | 0 | 0 | 80%（Cookies配置、设置保存） |
| 语料数据 | 3 | 0 | 3 | 0 | 10% |
| 标注管理 | 4 | 0 | 4 | 0 | 5% |
| **总计** | **25** | **18** | **7** | **0** | **52%** |

---

## 数据库迁移（Alembic）

| 项目 | 状态 | 说明 |
| :--- | :--- | :--- |
| Alembic 环境配置 | ✅ 已完成 | env.py、script.py.mako、alembic.ini 已配置 |
| 初始迁移脚本 | ✅ 已完成 | 包含全部 8 个数据模型 |
| SQLite 兼容性 | ✅ 已完成 | 支持 SQLite 和 PostgreSQL 双模式 |
| 自动初始化 | ✅ 已完成 | 应用启动时自动运行 alembic upgrade head |
| 升级/回滚 | ✅ 已完成 | 支持 upgrade 和 downgrade |

---

## 六、里程碑跟踪

| 里程碑 | 目标 | 当前状态 | 预计完成 |
| :--- | :--- | :--- | :--- |
| **M1**: 视频下载成功率 ≥ 95% | 第一阶段完成 | ❌ 未达成 | - |
| **M2**: 字幕提取准确率 ≥ 90% | 第二阶段完成 | ❌ 未达成 | - |
| **M3**: 多模态对齐准确率 ≥ 85% | 第三阶段完成 | ❌ 未达成 | - |
| **M4**: 隐喻识别准确率 ≥ 80% | 第四阶段完成 | ❌ 未达成 | - |
| **M5**: 系统完整交付，通过用户验收测试 | 第五阶段完成 | ❌ 未达成 | - |

---

## 七、当前已完成工作清单

### ✅ 已完成项

1. **项目基础架构**
   - FastAPI 后端框架搭建
   - React + TypeScript + Ant Design 前端框架搭建
   - Docker Compose 部署配置
   - 数据库连接配置（PostgreSQL + SQLAlchemy 异步 + SQLite 兼容）

2. **数据模型设计**
   - 8个核心数据实体完整定义
   - 外键关联关系建立
   - JSON 字段跨数据库兼容（SQLite + PostgreSQL）

3. **API 接口骨架**
   - 视频管理 CRUD 接口
   - 视频下载触发与进度查询
   - 本地视频文件上传
   - 视频信息预查询接口
   - 任务状态管理接口
   - 语料数据接口（占位符）
   - 标注管理接口（占位符）

4. **前端页面骨架**
   - 侧边栏导航布局
   - 任务管理页面（视频列表、添加、删除）
   - 视频详情页面
   - 语料库页面（框架）
   - 标注管理页面（框架）

5. **视频下载模块**
   - yt-dlp 集成，支持 YouTube/Bilibili/Vimeo 多平台下载
   - 异步下载任务，实时进度跟踪（百分比、已下载/总字节数）
   - 本地视频文件上传（支持 8 种格式，2GB 大小限制）
   - 多状态管理（pending/queued/downloading/completed/failed/cancelled）
   - 视频信息预查询接口
   - Services 层架构（video_downloader + video_service）
   - 批量操作（批量下载、批量取消、批量删除）
   - 视频标题解析与自动重命名（空格转下划线）
   - ffmpeg 自动检测与最佳画质合并
   - Bilibili Cookies 登录支持
   - SQLite WAL 模式优化并发性能

6. **桌面应用打包**
   - PyWebView 原生桌面窗口，无需浏览器
   - FastAPI 后端内嵌
   - ffmpeg 内置到安装包，零依赖运行
   - 桌面风格 UI 界面（三栏布局）
   - PyInstaller 打包成 exe

7. **数据库迁移（Alembic）**
   - Alembic 环境完整配置
   - 初始迁移脚本（8个表完整创建）
   - 支持 SQLite 和 PostgreSQL 双模式
   - 应用启动自动执行迁移
   - 支持 upgrade / downgrade

8. **Bug 修复**
   - 修复 subtitle_service.py 中 list 类型导入错误
   - 修复 VisualDescription 模型 JSON 字段 SQLite 兼容性
   - 修复 greenlet 与 Python 3.12 兼容性问题
   - 修复 alembic.ini 缺少日志配置问题

### ✅ 已交付

1. **视频下载工具（桌面版）** v1.0.0
   - 可执行文件：视频下载工具.exe
   - 内置 ffmpeg，零依赖运行
   - 支持 YouTube/Bilibili/Vimeo 多平台
   - 批量下载、取消、删除
   - 原生桌面窗口，无需浏览器

2. **第一阶段交付（v0.3.0）**
   - 视频下载模块完整可用
   - 数据库迁移体系建立
   - API 接口 18/25 已实现

### ❌ 待开始

1. 帧提取模块
2. 字幕提取（OCR/内嵌）
3. 音频提取与ASR
4. 图像描述生成
5. 多模态对齐
6. 隐喻识别
7. 不可译性识别
8. 语料导出功能
9. 标注审核功能

---

## 八、第二阶段开发计划（多模态内容提取）

**阶段名称**：多模态内容提取（帧提取 + 字幕提取 + 音频提取）  
**计划周期**：第 5-8 周  
**交付目标**：完整的视频内容解析能力，支持 AI 分析

---

### 8.1 目标概述

第二阶段的核心是从已下载的视频中提取三类内容，并集成 AI 分析能力：

| 内容类型 | 对应需求 | 依赖技术 | 数据输出 |
| :--- | :--- | :--- | :--- |
| **帧提取** | FR-009 ~ FR-015 | FFmpeg + VisionProvider | 图像帧序列 + 物体检测 |
| **字幕提取** | FR-016 ~ FR-020 | FFmpeg + OCRProvider + ASRProvider | 带时间轴的字幕文本 |
| **音频提取** | FR-021 ~ FR-025 | FFmpeg + ASRProvider | 音频片段 + ASR 文本 |
| **视觉描述** | FR-026 ~ FR-030 | VisionProvider + LLMProvider | 图像描述、场景分类 |

---

### 8.2 AI 服务层架构（已实现）

项目已实现 `backend/app/services/ai/` 目录，包含 4 个核心 Provider：

| Provider | 文件 | 本地模型 | 云端 API | 用途 |
| :--- | :--- | :--- | :--- | :--- |
| **OCRProvider** | [ocr_provider.py](file:///d:/work/多模态语料收集工具开发/backend/app/services/ai/ocr_provider.py) | PaddleOCR | 阿里云 DashScope、Google Vision | 硬字幕识别 |
| **ASRProvider** | [asr_provider.py](file:///d:/work/多模态语料收集工具开发/backend/app/services/ai/asr_provider.py) | Whisper (CPU) | 阿里云 DashScope | 语音识别 |
| **VisionProvider** | [vision_provider.py](file:///d:/work/多模态语料收集工具开发/backend/app/services/ai/vision_provider.py) | YOLOv8n | 阿里云 DashScope、腾讯云 | 图像描述、物体检测 |
| **LLMProvider** | [llm_provider.py](file:///d:/work/多模态语料收集工具开发/backend/app/services/ai/llm_provider.py) | - | DeepSeek、OpenAI、阿里云通义 | 隐喻分析、不可译分析 |

**核心设计**：
- 支持 **本地模型 + 云端 API** 双模式
- 自动 **降级策略**（本地失败 → 自动切换到 API）
- 统一返回格式，便于上层调用

---

### 8.3 功能模块详细设计

#### 模块 1：帧提取服务（Frame Extraction）

| 需求编号 | 功能点 | 优先级 | 实现说明 |
| :--- | :--- | :--- | :--- |
| FR-009 | 字幕时间戳检测 | 高 | 通过 FFmpeg 检测字幕轨道时间点 |
| FR-010 | 关键帧提取 | 高 | 在字幕显示时间段内提取帧 |
| FR-011 | 自定义帧提取频率 | 中 | 支持 fps 参数（如 1/5/10 帧/秒） |
| FR-012 | 提取所有帧 | 低 | 全量帧提取（按时间间隔采样） |
| FR-013 | 帧质量设置 | 中 | 支持分辨率、JPEG 压缩质量参数 |
| FR-014 | 自动去除低质量帧 | 高 | 基于清晰度/对比度检测过滤（OpenCV） |
| FR-015 | 帧按时间顺序存储 | 高 | 按 `videos/{id}/frames/` 时间戳命名 |

**AI 集成**：调用 `vision_provider.detect_objects()` 进行物体检测

#### 模块 2：字幕提取服务（Subtitle Extraction）

| 需求编号 | 功能点 | 优先级 | 实现说明 |
| :--- | :--- | :--- | :--- |
| FR-016 | 内嵌字幕轨道提取 | 高 | FFmpeg 导出字幕轨道（SRT/ASS） |
| FR-017 | OCR 硬字幕识别 | 高 | 调用 `ocr_provider.recognize()` |
| FR-018 | 多语言字幕识别 | 高 | 中文/英文/日文/韩文支持 |
| FR-019 | 字幕时间轴校正 | 中 | 对齐 OCR 结果与视频时间轴 |
| FR-020 | 字幕分段与分句 | 高 | 按标点、语义切分句子 |

**AI 集成**：
- `source="OCR"` → 调用 `ocr_provider.recognize()`
- `source="asr"` → 调用 `asr_provider.transcribe()`
- `source="auto"` → 优先内嵌，其次 OCR，最后 ASR

#### 模块 3：音频提取服务（Audio Extraction）

| 需求编号 | 功能点 | 优先级 | 实现说明 |
| :--- | :--- | :--- | :--- |
| FR-021 | 音频轨道提取 | 高 | FFmpeg 提取 WAV/MP3 |
| FR-022 | 按时间戳提取音频片段 | 高 | 截取字幕对应音频 |
| FR-023 | 音频降噪处理 | 中 | FFmpeg 降噪滤镜 |
| FR-024 | ASR 语音识别 | 高 | 调用 `asr_provider.transcribe()` |
| FR-025 | 多语言语音识别 | 中 | Whisper 多语言支持 |

**AI 集成**：调用 `asr_provider.transcribe()` 进行语音识别

#### 模块 4：视觉描述服务（Visual Description）

| 需求编号 | 功能点 | 优先级 | 实现说明 |
| :--- | :--- | :--- | :--- |
| FR-026 | 画面描述生成 | 高 | 调用 `vision_provider.describe_image()` |
| FR-027 | 关键对象标注 | 高 | 调用 `vision_provider.detect_objects()` |
| FR-028 | 场景分类 | 中 | 调用 `vision_provider.classify_scene()` |
| FR-029 | 情感分析 | 低 | 调用 `llm_provider` 分析画面情感 |
| FR-030 | 置信度评估 | 中 | 返回各 AI 模块置信度评分 |

**AI 集成**：
- 调用 `vision_provider.describe_image()` 生成图像描述
- 调用 `vision_provider.detect_objects()` 检测物体
- 调用 `llm_provider` 进行情感分析

---

### 8.4 API 接口设计

#### 帧提取接口

| 路径 | 方法 | 说明 |
| :--- | :--- | :--- |
| `POST /api/v1/videos/{id}/frames/extract` | 触发帧提取 | 参数：mode, fps, quality, analyze_objects |
| `GET /api/v1/videos/{id}/frames` | 获取帧列表 | 分页、筛选 |
| `GET /api/v1/videos/{id}/frames/{frame_id}` | 获取单帧详情 | 含质量评分 |

#### 字幕提取接口

| 路径 | 方法 | 说明 |
| :--- | :--- | :--- |
| `POST /api/v1/videos/{id}/subtitles/extract` | 触发字幕提取 | 参数：source, languages |
| `GET /api/v1/videos/{id}/subtitles` | 获取字幕列表 | 按语言/来源筛选 |
| `GET /api/v1/videos/{id}/subtitles/{subtitle_id}` | 获取字幕详情 | 含文本和时间轴 |
| `PUT /api/v1/videos/{id}/subtitles/{subtitle_id}` | 更新字幕（人工校正） | |

#### 音频提取接口

| 路径 | 方法 | 说明 |
| :--- | :--- | :--- |
| `POST /api/v1/videos/{id}/audio/extract` | 触发音频提取 | 参数：format, denoise, asr |
| `GET /api/v1/videos/{id}/audio` | 获取音频片段列表 | |
| `GET /api/v1/videos/{id}/audio/{segment_id}` | 获取音频片段详情 | 含 ASR 文本 |

#### 视觉描述接口

| 路径 | 方法 | 说明 |
| :--- | :--- | :--- |
| `POST /api/v1/videos/{id}/visual/describe` | 生成画面描述 | 参数：frame_ids, describe_objects, describe_scene |
| `GET /api/v1/videos/{id}/visual` | 获取视觉描述列表 | |

#### AI 状态与配置接口

| 路径 | 方法 | 说明 |
| :--- | :--- | :--- |
| `GET /api/v1/ai/status` | 获取 AI 服务状态 | 各 Provider 的可用性 |
| `GET /api/v1/ai/config` | 获取 AI 配置 | 模型名称、API Key 状态等 |
| `PUT /api/v1/ai/config` | 更新 AI 配置 | 设置 API Key、模型参数等 |

#### AI 直调接口

| 路径 | 方法 | 说明 |
| :--- | :--- | :--- |
| `POST /api/v1/ai/ocr` | OCR 识别 | 上传图片，返回文字识别结果 |
| `POST /api/v1/ai/asr` | 语音识别 | 上传音频，返回识别文本 |
| `POST /api/v1/ai/asr/translate` | 语音翻译 | 上传音频，返回翻译结果 |
| `POST /api/v1/ai/vision/describe` | 图像描述 | 上传图片，返回描述和物体列表 |
| `POST /api/v1/ai/vision/detect` | 物体检测 | 上传图片，返回检测到的物体 |
| `POST /api/v1/ai/llm/chat` | 通用对话 | 发送消息，返回 LLM 回复 |

---

### 8.5 技术实现路径

#### 阶段一（第 5 周）：帧提取 + 视觉 AI

```
1. 创建 FrameService（完善现有框架）
2. FFmpeg 帧提取集成
   - 字幕时间戳检测（ffmpeg -vf subtitles）
   - 关键帧提取（fps 模式）
3. 集成 VisionProvider（物体检测）
4. 帧质量过滤（OpenCV）
5. 存储与路径管理
6. API 接口实现
7. 单元测试
```

#### 阶段二（第 6 周）：字幕提取 + OCR/ASR AI

```
1. 内嵌字幕提取
   - FFmpeg 导出字幕轨道
   - SRT/ASS 解析
2. 集成 OCRProvider（硬字幕识别）
3. 集成 ASRProvider（语音转文字）
4. 字幕分段算法
5. API 接口实现
6. 集成测试
```

#### 阶段三（第 7 周）：音频提取 + ASR AI

```
1. AudioService 完善
   - FFmpeg 音频提取
   - 音频片段截取
2. 集成 ASRProvider（语音识别）
3. 音频降噪处理
4. API 接口实现
5. AI 配置管理接口
```

#### 阶段四（第 8 周）：视觉描述 + LLM 集成

```
1. VisualService 完善
2. 集成 VisionProvider（图像描述）
3. 集成 LLMProvider（隐喻分析、不可译分析）
4. 多模态对齐逻辑
5. AI 状态与配置接口
6. 阶段集成验收
```

---

### 8.6 依赖与环境

| 依赖 | 版本 | 用途 | 状态 |
| :--- | :--- | :--- | :--- |
| ffmpeg-python | 0.2.0 | FFmpeg Python 封装 | ✅ 已安装 |
| paddleocr | 2.12.0 | OCR 识别 | ⚠️ 已安装，未集成到业务层 |
| openai-whisper | 2024.11.17 | ASR 语音识别 | ⚠️ 已安装，未集成到业务层 |
| opencv-python | 4.10.0.84 | 帧质量检测 | ❌ 需安装 |
| numpy | 1.26.4 | 数值计算 | ✅ 已安装 |
| ultralytics | - | YOLOv8 物体检测 | ⚠️ 需安装 |

---

### 8.7 里程碑

| 里程碑 | 目标 | 验收标准 |
| :--- | :--- | :--- |
| M2.1 | 帧提取功能完成 | 能提取视频帧，支持三种模式，质量过滤生效，物体检测可用 |
| M2.2 | 字幕提取功能完成 | 内嵌字幕和 OCR 均可提取，时间轴准确，ASR 可用 |
| M2.3 | 音频提取功能完成 | 音频提取 + Whisper ASR 工作正常，降噪处理生效 |
| M2.4 | 阶段集成验收 | 四模块联动测试通过，API 接口测试通过，AI 服务状态正常 |

---

### 8.8 AI 配置环境变量

```env
# OCR
DASHSCOPE_API_KEY=your-key
GOOGLE_VISION_API_KEY=your-key

# ASR
WHISPER_MODEL=base  # tiny/base/small

# Vision
TENCENT_SECRET_ID=your-id
TENCENT_SECRET_KEY=your-key

# LLM
DEEPSEEK_API_KEY=your-key
OPENAI_API_KEY=your-key
DASHSCOPE_MODEL=qwen-turbo

# 策略配置
PREFER_LOCAL=true
FALLBACK_TO_API=true
LOCAL_ONLY=false
```

---

### 8.9 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
| :--- | :--- | :--- | :--- |
| OCR 准确率低 | 中 | 高 | 优先使用内嵌字幕，OCR 作为补充 |
| Whisper 模型加载慢 | 高 | 中 | 模型缓存，首次加载后复用 |
| 视频格式不支持 | 中 | 中 | FFmpeg 自动检测，优雅降级 |
| GPU 资源不足 | 高 | 中 | CPU 回退，异步队列削峰 |
| AI API 调用失败 | 中 | 中 | 自动降级到本地模型 |

---

### 8.10 交付清单

| 交付物 | 验收条件 |
| :--- | :--- |
| FrameService 源码 | 含单元测试，集成 VisionProvider |
| SubtitleService 源码 | 含单元测试，集成 OCRProvider/ASRProvider |
| AudioService 源码 | 含单元测试，集成 ASRProvider |
| VisualService 源码 | 含单元测试，集成 VisionProvider/LLMProvider |
| AI API 接口 | 符合设计，可正常调用 |
| 迁移脚本（如需） | 可在现有数据库执行 |
| 进度文档更新 | 反映最新状态 |

---

## 九、风险与问题

| 风险/问题 | 严重程度 | 状态 | 说明 |
| :--- | :--- | :--- | :--- |
| Bilibili 下载需登录 | 高 | 🟡 已缓解 | 需用户提供 Cookies，已支持 Cookies 配置功能 |
| YouTube 403 反爬 | 中 | 🟢 已解决 | 通过信号量控制并发下载数，限制为3个并发 |
| SQLite 并发锁 | 中 | 🟢 已解决 | 启用 WAL 模式，设置 busy_timeout=30000 |
| 模型推理性能 | 中 | 🟡 关注 | GPU 资源未配置，可能影响处理速度 |
| 数据库迁移缺失 | 中 | 🟢 已解决 | Alembic 已配置，初始迁移脚本已创建 |
| 对象存储未集成 | 中 | 🟡 待处理 | MinIO 配置已定义但未实际使用 |
| 前端状态管理 | 低 | 🟢 后续优化 | 当前组件状态管理可满足初期需求 |
| greenlet 兼容性 | 低 | 🟢 已解决 | 降级到 greenlet 3.0.3 兼容 Python 3.12 |
| JSON 字段兼容性 | 低 | 🟢 已解决 | 使用通用 JSON 类型替代 PostgreSQL 专用类型 |

---

## 十、测试执行记录

| 测试日期 | 测试类型 | 用例数 | 通过 | 失败 | 通过率 | 测试报告 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-06-29 | API接口测试 | 16 | 16 | 0 | 100% | [test_report_20260629_091404.json](file:///workspace/backend/test_report_20260629_091404.json) |

### 已验证功能

- ✅ 健康检查接口
- ✅ 创建视频记录
- ✅ 获取视频列表（支持状态/平台筛选）
- ✅ 获取单个视频详情
- ✅ 批量创建视频
- ✅ 触发视频下载任务
- ✅ 查询下载进度
- ✅ 获取任务状态
- ✅ 取消任务
- ✅ 删除视频
- ✅ 本地文件上传
- ✅ 错误处理（404等）

---

*进度表将根据项目进展持续更新*
