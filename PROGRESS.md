# Citadel 开发进度

## 项目信息

- **开始日期**: 2025-12-26
- **当前版本**: v0.2.6
- **项目状态**: 🔄 开发中
- **当前分支**: main

---

## 阶段1: 项目初始化 ✅

**状态**: 已完成并测试验证
**完成日期**: 2025-12-26
**测试日期**: 2025-12-28

### 完成项目
- [x] 创建项目目录结构
- [x] 配置 `pixi.toml` 依赖文件
- [x] 复制核心脚本 (`download.sh` 和 `convert.py`)
- [x] 创建CLI工具骨架
- [x] 编写 `README.md`
- [x] 编写 `PROGRESS.md`
- [x] 执行 `pixi install` 验证环境 ✅ **已通过**
- [x] 测试CLI工具启动 ✅ **已通过**
- [x] 测试mc工具连接 ✅ **已通过** (v2025-08-13)
- [x] 测试BOS文件下载 ✅ **已通过** (2.55MB/s)

### 测试结果
**✅ 通过的测试**:
- pixi依赖安装成功
- download CLI工具正常启动，参数解析正确
- convert CLI工具正常启动，参数解析正确
- mc工具可用，可正常访问BOS存储
- 成功从BOS下载测试文件 (episode_0002.h5, 2.55MB)

**⚠️ 发现的问题**:
- ✅ ~~convert.py脚本与BOS数据格式不匹配~~ (已解决)

**关键文件**:
- ✅ `pixi.toml`
- ✅ `scripts/download.sh`
- ✅ `scripts/convert.py` (已适配v1格式)
- ✅ `cli/download_cli.py`
- ✅ `cli/convert_cli.py`

---

## 阶段2: 后端核心服务 ✅

**状态**: 已完成
**开始日期**: 2025-12-28
**完成日期**: 2025-12-28
**实际耗时**: <0.5天

### 2.1 数据模型和存储 ✅
- [x] 实现 `backend/models/task.py` - 任务数据模型
- [x] 实现 `backend/services/database.py` - SQLite数据库服务
- [x] 任务状态机：pending → running → completed/failed

### 2.2 下载服务 ✅
- [x] 实现 `backend/services/download_service.py`
- [x] 复用 `cli/utils/mc_executor.py`
- [x] 异步任务执行和进度上报

### 2.3 转换服务 ✅
- [x] 实现 `backend/services/convert_service.py`
- [x] 复用 `scripts/convert.py` 逻辑
- [x] 批量任务队列和并发控制

### 2.4 API路由 ✅
- [x] 实现 `backend/main.py` - FastAPI入口
- [x] 实现 `backend/routers/tasks.py` - 任务管理API
- [x] 实现 `backend/routers/download.py` - 下载API
- [x] 实现 `backend/routers/convert.py` - 转换API

---

## 阶段2.5: CLI工具开发 ✅

**状态**: 已完成
**完成日期**: 2025-12-28
**实际耗时**: <1天

### 2.5.1 下载CLI工具 ✅
- [x] 创建 `cli/download_cli.py` 骨架
- [x] 实现完整下载功能（mc mirror封装）
- [x] 集成mc_executor和进度跟踪
- [x] BOS连接检查
- [x] 错误处理和日志
- [x] 测试验证（18个文件，235MB下载成功）

### 2.5.2 转换CLI工具 ✅
- [x] 创建 `cli/convert_cli.py` 骨架
- [x] 实现批量转换功能
- [x] 并发转换控制（ThreadPoolExecutor）
- [x] 进度显示和统计信息
- [x] 错误处理和超时控制（5分钟/文件）
- [x] 测试验证（3文件并发转换，3.3秒完成）

### 2.5.3 上传CLI工具 ✅
- [x] 创建 `cli/upload_cli.py`
- [x] 实现mc mirror上传功能
- [x] LeRobot目录扫描和验证
- [x] JSON输出解析和进度显示
- [x] 并发上传控制
- [x] 在pixi.toml中注册任务

### 2.5.4 工具模块 ✅
- [x] 创建 `cli/utils/mc_executor.py` 骨架
- [x] 实现mc命令执行和进度解析
- [x] 实现实时输出捕获
- [x] 实现BOS连接检查
- [x] 创建 `cli/utils/progress.py` 骨架
- [x] 实现ProgressTracker进度跟踪器

---

## 阶段2.6: 数据集合并工具 ✅

**状态**: 已完成
**完成日期**: 2025-12-29
**实际耗时**: <0.5天

### 2.6.1 Merge CLI工具 ✅
- [x] 将 `merge_lerobot.py` 整合到项目
- [x] 移动核心脚本到 `scripts/merge_lerobot.py`
- [x] 创建 `cli/merge_cli.py` CLI封装
- [x] 在 `pixi.toml` 中注册 merge 任务
- [x] 支持多数据集合并为单个LeRobot数据集
- [x] 自动处理维度对齐（state/action向量填充）
- [x] 视频文件复制和重索引
- [x] 元数据合并和统计信息计算

### 功能特性
- **批量合并**: 支持合并任意数量的独立LeRobot episode
- **维度自适应**: 自动检测并统一state/action向量维度
- **数据完整性**: 自动合并元数据、统计信息、任务列表
- **索引重排**: 自动重新编号episode索引和帧索引
- **视频复制**: 复制所有相机视频文件并重新命名

### 测试结果
- ✅ 成功合并232个独立episode为单个数据集
- ✅ 总帧数: 365,518 帧
- ✅ 总视频数: 696 个（3相机 × 232 episodes）
- ✅ 数据集大小: 644 MB
- ✅ State/Action维度: 14 维（双臂机器人）

---

## 阶段2.7: Web前端 QC质检 + Merge集成 ✅

**状态**: 已完成
**目标版本**: v0.2.1
**完成日期**: 2026-01-07
**实际耗时**: <1天

### 功能需求
将现有的 CLI merge 工具集成到 Web 前端 Pipeline 页面，并新增 QC 质检功能。

### 2.7.1 后端服务 - Merge API ✅
- [x] 扩展 `backend/models/task.py` - 添加 MERGE 任务类型
- [x] 创建 `backend/services/merge_service.py` - Merge 服务
- [x] 创建 `backend/routers/merge.py` - Merge API 路由
- [x] 扩展 `backend/routers/upload.py` - 添加视频流端点
- [x] 添加 QC 结果保存/加载 API

### 2.7.2 前端组件 - QC质检 ✅
- [x] 创建 `QCInspector.vue` - 质检组件
  - 左侧: Episode 列表 (状态图标 + 点击选中)
  - 右侧: 视频播放器 (`<video>` 标签)
  - 底部: 通过/不通过按钮
  - 统计: 已通过/不通过/待检查数量
- [x] 三相机切换支持 (环境/左腕/右腕)
- [x] 键盘快捷键 (↑↓导航, P通过, F不通过, 1/2/3切换相机)
- [x] QC 结果持久化 (保存到 qc_result.json)
- [x] 恢复上次进度并自动定位

### 2.7.3 Pipeline页面集成 ✅
- [x] 扩展 `frontend/src/api/pipeline.ts` - 添加 QC/Merge API
- [x] 修改 `frontend/src/views/Pipeline.vue`
  - 添加 QC 按钮 (在 Convert 和 Merge 之间)
  - 添加 Merge 按钮 (显示通过数量)
  - 添加 Upload 按钮 (上传 merged 目录)
  - 引入 QCInspector 组件
- [x] 操作确认对话框 (Download/Convert/Merge/Upload)
- [x] 状态检查栏 (BOS下载前/数据转换前/数据上传前)
- [x] 路径说明 (H5原始文件/LeRobot转换后/合并后数据集)

### 工作流程
```
Download → Convert → QC 质检 → Merge → Upload
                        ↓
              视频播放器 → 标记通过/不通过
                        ↓
              只合并「通过」的 episode
```

### 目录结构
```
local_dir/
  ├── raw/           # H5原始文件 (Download)
  ├── lerobot/       # LeRobot转换后 (Convert)
  ├── merged/        # 合并后数据集 (Merge)
  └── qc_result.json # QC结果记录
```

---

## 阶段2.8: 配置重构 - 统一配置管理 ✅

**状态**: 已完成
**目标版本**: v0.2.2
**完成日期**: 2026-01-09
**实际耗时**: <0.5天

### 问题背景
- 项目中存在大量硬编码路径（如 `/home/maozan/mc`）
- 魔法数字分散在各个文件中（端口、超时、默认值）
- 不同文件中相同参数使用不同默认值（如 state_max_dim: 14 vs 32）
- 新环境部署需要手动修改多处代码

### 2.8.1 后端配置模块 ✅
- [x] 创建 `backend/config/__init__.py` - 配置模块入口
- [x] 创建 `backend/config/settings.py` - 统一配置管理类
  - 使用 `@property` 实现懒加载
  - 支持环境变量覆盖默认值
  - mc路径智能检测（MC_PATH → ~/bin/mc → PATH）
- [x] 创建 `.env.example` - 环境变量模板文件

### 2.8.2 后端服务重构 ✅
- [x] 重构 `backend/models/task.py` - 使用配置模块默认值
- [x] 重构 `backend/main.py` - 端口和CORS配置
- [x] 重构 `backend/services/database.py` - 数据库路径配置
- [x] 重构 `backend/services/download_service.py` - mc路径和超时配置
- [x] 重构 `backend/services/upload_service.py` - mc路径和BOS配置
- [x] 重构 `backend/services/convert_service.py` - 超时和默认参数配置
- [x] 重构 `backend/services/merge_service.py` - 维度和fps默认值配置

### 2.8.3 CLI工具重构 ✅
- [x] 重构 `cli/download_cli.py` - 移除硬编码路径，改为必填参数
- [x] 重构 `cli/convert_cli.py` - 使用环境变量默认值
- [x] 重构 `cli/upload_cli.py` - 移除硬编码路径，改为必填参数

### 2.8.4 前端配置重构 ✅
- [x] 重构 `frontend/vite.config.ts` - 支持环境变量配置端口
- [x] 重构 `frontend/src/api/index.ts` - API超时配置
- [x] 重构 `frontend/src/views/Pipeline.vue` - 默认并发数配置
- [x] 重构 `frontend/src/views/Download.vue` - 默认并发数配置
- [x] 重构 `frontend/src/views/Upload.vue` - 默认并发数配置
- [x] 创建 `frontend/.env.example` - 前端环境变量模板

### 2.8.5 文档更新 ✅
- [x] 更新 `README.md` - 添加配置说明章节
- [x] 更新 `USER_GUIDE.md` - 添加环境变量配置章节
- [x] 更新 `PROGRESS.md` - 添加配置重构里程碑
- [x] 创建 `INSTALL.md` - 完整环境安装指南

### 配置项汇总

**后端配置项（19项）：**
- API服务器：`API_HOST`, `API_PORT`, `CORS_ORIGINS`
- mc工具：`MC_PATH`, `BOS_ALIAS`, `BOS_TEST_PATH`
- 默认参数：`DEFAULT_CONCURRENCY`, `DEFAULT_FPS`, `DEFAULT_ROBOT_TYPE`, `DEFAULT_TASK_NAME`, `DEFAULT_PARALLEL_JOBS`, `STATE_MAX_DIM`, `ACTION_MAX_DIM`
- 超时设置：`TIMEOUT_MC_CHECK`, `TIMEOUT_CONVERT_FILE`
- 存储路径：`DB_PATH`

**前端配置项（4项）：**
- `VITE_API_PORT`, `VITE_DEV_PORT`, `VITE_DEFAULT_CONCURRENCY`, `VITE_API_TIMEOUT`

---

## 阶段2.9: Bug修复与QC优化 ✅

**状态**: 已完成
**目标版本**: v0.2.3
**完成日期**: 2026-01-09
**实际耗时**: <0.5天

### 问题背景
- 前端默认值与后端配置不同步
- 后端未加载 `.env` 文件
- 代码审查发现多处潜在 bug
- QC 视频查看器需要同时查看多相机

### 2.9.1 配置同步机制 ✅
- [x] 添加 `/api/config/defaults` 端点返回后端配置
- [x] 前端 Pipeline 页面启动时获取默认配置
- [x] 添加 `python-dotenv` 依赖到 `pixi.toml`
- [x] 后端 `settings.py` 自动加载 `.env` 文件
- [x] `.env` 文件配置值正确生效

### 2.9.2 Bug修复 - Critical ✅
- [x] `task.py`: 添加 `exclude_episodes` 字段到 UploadConfig
- [x] `pipeline.ts`: 修复 `ready: dirs.length > 0 || true` 逻辑错误
- [x] `download_cli.py`: 使用 `settings.BOS_ALIAS` 替代硬编码 "bos"
- [x] `mc_executor.py`: 使用配置的 BOS 测试路径

### 2.9.3 Bug修复 - High ✅
- [x] `convert_service.py`: 使用 `sys.executable` 替代硬编码 Python 路径
- [x] `convert.py` router: 添加输入目录验证
- [x] `merge.py` router: 添加源目录验证
- [x] `upload_service.py`: 添加 `cancel_task` 异常处理
- [x] `Pipeline.vue`: 修复 `runAllChecks()` 竞态条件
- [x] `pipeline.ts`: 修复 upload 使用 `merged_dir` 而非 `lerobot_dir`

### 2.9.4 Bug修复 - Medium ✅
- [x] `convert_cli.py`: 使用 `settings.TIMEOUT_CONVERT` 替代硬编码 300
- [x] `merge_service.py`: 添加 `shutil.rmtree()` 异常处理
- [x] `download.py` router: 添加任务 None 检查
- [x] `Pipeline.vue`: 修复 QC 按钮加载状态使用 `qcLoading`
- [x] `Pipeline.vue`: 添加 `handleQCConfirm` 错误通知
- [x] `Pipeline.vue`: 修复 `handleMerge` 过滤器空安全检查

### 2.9.5 Bug修复 - Low ✅
- [x] `merge_cli.py`: 修复文档注释默认值 32 → 14

### 2.9.6 QC视频布局优化 ✅
- [x] 修改 `QCInspector.vue` 模板：三相机并排显示
- [x] 添加 CSS 样式：`.video-grid`, `.video-cell`, `.camera-label`, `.video-player-small`
- [x] 三个相机视频同步播放（环境/左腕/右腕）
- [x] 每个视频带相机名称标签

### 改进效果
- 前端默认值与 `.env` 配置自动同步
- 用户可通过修改 `.env` 自定义所有默认参数
- 修复 18 个潜在 bug，提高系统稳定性
- QC 质检可同时查看三个相机视角，提高效率

---

## 阶段2.10: 前端代码质量优化 ✅

**状态**: 已完成
**目标版本**: v0.2.4
**完成日期**: 2026-01-12
**实际耗时**: <0.5天

### 问题背景
- 代码审查发现多处潜在 bug 和不规范写法
- 详细问题记录在 `docs/FRONTEND_BUGFIX.md`

### 2.10.1 P0 严重问题修复 ✅
- [x] `Dashboard.vue`: 修复 `el-radio-button` 属性错误 (`:value` → `:label`)
- [x] `TaskTable.vue`: 修复 Icon 组件用法错误 (`:icon` 函数调用 → slot 插入)

### 2.10.2 P1 中等问题修复 ✅
- [x] `Layout.vue`: 整合分散的 import 语句到文件顶部
- [x] `api/index.ts`: 增大默认 API 超时时间 (30s → 120s)

### 2.10.3 P2 轻微问题修复 ✅
- [x] `Dashboard.vue`: 移除冗余的双重 `stopPolling()` 调用

### 2.10.4 额外发现并修复 ✅
- [x] `TaskPreviewBar.vue`: 修复 stats 计算属性访问路径错误 (`stats.running` → `stats.tasks.running`)

### 2.10.5 防御性编程改进 ✅
- [x] `QCInspector.vue`: 添加数组访问空值检查
- [x] `templates.ts`: 添加 `splice()[0]` 和数组索引空值检查
- [x] `pipeline.ts`: 添加 API 响应类型定义和 `Array.isArray` 检查

### 2.10.6 类型系统优化 ✅
- [x] `pipeline.ts`: 新增 `ScanBosResponse` 和 `ScanDirsResponse` 接口
- [x] `pipeline.ts`: 使用泛型 `api.get<T>()` 替代类型断言 `as T`

### 2.10.7 UI 样式优化 ✅
- [x] `style.css`: 更新暗色主题配色为 GitHub 风格
- [x] `style.css`: 添加 Tailwind CSS v4 `@theme` 变量定义
- [x] `style.css`: 扩展 Element Plus 暗色主题组件样式

### 改进效果
- 修复 6 处文档记录的 bug + 1 处隐藏 bug
- 增强代码健壮性，防止运行时空值错误
- 统一 API 响应类型管理，提高代码可维护性
- 优化暗色主题视觉效果

---

## 阶段2.11: 数据质量与转换优化 ✅

**状态**: 已完成
**目标版本**: v0.2.5
**开始日期**: 2026-01-15
**完成日期**: 2026-01-26

### 2.11.1 转换工具增强 ✅
- [x] 线性插值对齐方法 (`--alignment-method linear`)
- [x] 自适应边界裁剪（自动计算头帧时延，裁剪超出范围的帧）
- [x] 新增 `scipy` 依赖
- [x] 新增 `DEFAULT_ALIGNMENT_METHOD` 配置项

### 2.11.2 Merge工具增强 ✅
- [x] 支持 glob 模式（如 `/path/to/episode_*`）
- [x] 自动展开通配符路径

### 2.11.3 Frame-State 对齐分析工具重构 ✅
- [x] **模块化重构**: 将 1138 行单文件脚本重构为 8 个模块
  - `scripts/alignment/__init__.py` - 模块导出
  - `scripts/alignment/config.py` - 集中配置管理
  - `scripts/alignment/data_loader.py` - 数据集加载（支持 v2.0/v3.0）
  - `scripts/alignment/video_tracker.py` - 策略模式视频追踪器
  - `scripts/alignment/signal_processing.py` - 信号处理与去噪
  - `scripts/alignment/visualization.py` - 可视化生成
  - `scripts/alignment/analyzer.py` - 核心分析逻辑
  - `scripts/alignment/cli.py` - 命令行接口
- [x] **新增黑色区域检测**: 针对 ALOHA 等黑色夹爪机器人优化
  - 相比 ROI 模式提升 21% 相关性（0.460 vs 0.379）
- [x] **新增状态引导去噪**: 利用 State 波形指导 Video 信号去噪
  - 相关性提升 34.1%（0.617 vs 0.460）
- [x] **删除废弃代码**: 移除 `scripts/filter_lerobot/` 目录及相关文件
- [x] **CLI 参数扩展**:
  - `--black-detection`: 启用黑色区域检测模式
  - `--color-detection`: 启用颜色检测模式（橙色夹爪）
  - `--denoise`: 启用状态引导去噪
  - `--denoise-method`: 去噪方法选择（state_guided/weighted/adaptive）

### 数据集分析结果汇总
| 数据集 | 平均偏移(帧) | 平均偏移(ms) | 评估 |
|--------|--------------|--------------|------|
| 0115_qz2_plant/merged | +0.41 | 16ms | ✅ 优秀 |
| 1226_qz2/merged | +1.23 | 49ms | ⚠️ 正常 |
| 1226_qz2/merged_nearest | +1.93 | 77ms | ⚠️ 需关注 |
| aloha_mobile_cabinet | +1.55 | 31ms | ⚠️ 正常 |

---

## 阶段2.12: 转换管线健壮性增强 ✅

**状态**: 已完成
**目标版本**: v0.2.6
**开始日期**: 2026-02-08
**完成日期**: 2026-02-11

### 2.12.1 跳帧检测与片段切割 ✅
- [x] 新增 `detect_gap_segments()` 函数
  - 检测所有相机的严重跳帧（帧间隔 > 中位数 × gap_factor）
  - 合并重叠跳帧区间，切割 reference_timestamps 为有效片段
  - 过滤帧数不足的片段（min_segment_frames=30）
- [x] 重写 `load_episode_v1_format()` 返回 `List[Dict]`
  - 每个片段独立对齐（图像 + 关节数据）
  - 一次解码图像，按片段时间范围分配
- [x] 更新 `convert_hdf5_to_lerobot_v21()` 支持多片段输出
  - 每个片段作为独立 episode 输出
  - 更新 info.json、episodes.jsonl 生成逻辑
- [x] CLI 新增参数: `--gap-factor`, `--min-segment-frames`

### 2.12.2 三相机视频对比可视化工具 ✅
- [x] 新增 `scripts/visualize_video_sync.py`
  - 将 convert 后的三个相机 MP4 并排拼接为合成视频
  - 每帧标注帧号和相机名称（bitmap 字体，无 GUI 依赖）
  - 支持单 episode 和全量 episode 模式
  - 自动识别 per-episode 和 merged 两种目录结构
  - 适配无头服务器环境（无 tkinter/matplotlib 依赖）

### 2.12.3 新数据集适配 ✅
- [x] 更新 CLI 工具默认路径适配 `0203_qz2_pants` 数据集
- [x] 默认对齐方法从 `nearest` 改为 `linear`
- [x] 更新 robot_config 配置
- [x] 更新对齐分析文档

### 数据分析结果（0203_qz2_pants, 158 episodes）
- **跳帧分析**: 157/158 episodes 无跳帧，仅 episode_0060 有 1 处 gap（168ms，损失 1 帧）
- **相机帧率**: cam_env ~31fps (32.02ms), 腕部相机 ~25fps (40.00ms)
- **时间戳偏移**: 三相机无系统性偏移

---

## 阶段3: 日志和监控 ⏸️

**状态**: 暂缓（合并到阶段9）
**说明**: 原计划内容已合并到阶段9，优先进行UI/UX优化

---

## 阶段4: 前端开发 ✅

**状态**: 已完成
**开始日期**: 2025-12-28
**完成日期**: 2025-12-28
**实际耗时**: <0.5天

### 4.1 项目初始化 ✅
- [x] 初始化Vite + Vue3 + TypeScript项目
- [x] 安装Element Plus、Tailwind CSS、Axios
- [x] 配置Vue Router和Pinia状态管理
- [x] 配置vite.config.ts代理后端API

### 4.2 任务看板页 ✅
- [x] 实现 `Dashboard.vue` - 统计卡片和任务列表
- [x] 实现 `TaskTable.vue` - 任务表格组件
- [x] 实现 `TaskDetail.vue` - 任务详情抽屉
- [x] 实现 `StatCard.vue` - 统计卡片组件
- [x] 状态筛选和自动刷新（3秒轮询）

### 4.3 下载管理页 ✅
- [x] 实现 `Download.vue`
- [x] BOS路径和本地路径配置
- [x] 并发数滑块
- [x] BOS连接检查

### 4.4 转换管理页 ✅
- [x] 实现 `Convert.vue`
- [x] 文件扫描预览
- [x] 转换参数配置（robot_type, fps, task）
- [x] 并发数设置

### 4.5 上传管理页 ✅
- [x] 实现 `Upload.vue`
- [x] 目录扫描预览
- [x] 上传选项（包含视频、上传后删除）
- [x] 后端 `upload_service.py` 和 `upload.py` 路由

### 4.6 系统状态页 ✅
- [x] 实现 `Status.vue`
- [x] 健康检查卡片
- [x] 任务统计图表

### 技术栈
- Vue 3 + TypeScript + Vite
- Element Plus UI组件库
- Tailwind CSS 样式
- Pinia 状态管理
- Axios HTTP客户端
- @iconify/vue 图标库

### 测试结果
- ✅ 前端编译成功
- ✅ 开发服务器启动正常 (http://localhost:5173)
- ✅ API代理配置正确
- ✅ 暗色主题生效

### 功能测试 (2025-12-29)
- ✅ **下载功能**: BOS文件下载测试通过
- ✅ **转换功能**: HDF5批量转换测试通过
- ✅ **上传功能**: LeRobot目录上传测试通过
  - 修复BOS路径前缀问题 (`bos/` 前缀)
  - 修复mc mirror并发参数 (`--max-workers`)

---

## 阶段5: 集成测试 ✅

**状态**: 已完成（CLI工具测试通过）
**完成日期**: 2025-12-28

- [x] 完整流程测试（下载18个HDF5 → 批量转换）✅ 通过
- [x] 并发任务测试（4并发转换）✅ 通过
- [x] 异常处理测试（left/right时间戳不一致处理）✅ 通过
- [ ] 性能测试（待Web界面完成后进行压力测试）

**测试结果**:
- 下载：18个文件，246MB，16秒，15.22 MB/s
- 转换：18个文件全部成功，17秒，平均1.0秒/文件

---

## 阶段6: 文档和发布 ✅

**状态**: 已完成
**完成日期**: 2025-12-28
**实际耗时**: <0.5天

- [x] 完善README.md
  - 聚焦CLI工具功能
  - 更新命令示例和参数说明
  - 添加数据格式详细说明
  - 添加测试结果和性能数据
- [x] 编写USER_GUIDE.md
  - 快速入门指南
  - CLI完整参数说明
  - 数据格式详解
  - 故障排除指南
- [x] 更新PROGRESS.md
- [x] 发布v0.1.0

---

## 阶段7: UI/UX优化 ⏳

**状态**: 待开始
**预计时间**: 1-2天
**目标版本**: v0.3.0

### 7.1 配置持久化 ⭐⭐⭐
- [ ] 实现 `stores/settings.ts` - 配置状态管理
- [ ] localStorage 保存用户输入的路径参数
- [ ] 页面加载时自动恢复上次配置
- [ ] 支持清除保存的配置

### 7.2 表单验证 ⭐⭐⭐
- [ ] 路径存在性检查（调用后端API验证）
- [ ] 参数范围验证（并发数、fps等）
- [ ] 实时错误提示和表单状态反馈
- [ ] 提交前完整性校验

### 7.3 进度展示优化 ⭐⭐
- [ ] 实时进度条组件
- [ ] 显示已完成/总数
- [ ] 预计剩余时间计算
- [ ] 任务速度统计

### 7.4 快捷操作 ⭐⭐
- [ ] 一键复制路径按钮
- [ ] 常用配置模板（预设场景）
- [ ] 智能默认值（基于历史记录）
- [ ] 快速操作按钮（重试、取消等）

### 7.5 布局优化 ⭐
- [ ] 侧边栏折叠功能
- [ ] 页面结构调整
- [ ] 响应式适配（移动端）
- [ ] 暗色/亮色主题切换

---

## 阶段8: 功能增强 ⏳

**状态**: 待开始
**预计时间**: 2-3天
**目标版本**: v0.3.1

### 8.1 任务链（Pipeline）
- [ ] 设计任务链数据模型
- [ ] 实现 下载→转换→上传 一键流水线
- [ ] 任务链进度展示
- [ ] 链中任务失败处理策略

### 8.2 批量操作
- [ ] 任务多选功能
- [ ] 批量启动任务
- [ ] 批量取消任务
- [ ] 批量删除历史记录

### 8.3 任务管理增强
- [ ] 失败任务一键重试
- [ ] 任务克隆（复制配置创建新任务）
- [ ] 任务优先级设置
- [ ] 任务标签和分类

### 8.4 配置模板系统
- [ ] 保存当前配置为模板
- [ ] 模板管理（列表、删除、重命名）
- [ ] 快速应用模板
- [ ] 导入/导出模板

---

## 阶段9: 日志和监控 ⏳

**状态**: 待开始
**预计时间**: 2天
**目标版本**: v0.3.2

### 9.1 实时日志系统
- [ ] 实现 `backend/services/log_streamer.py`
- [ ] WebSocket 日志推送
- [ ] 前端日志查看组件
- [ ] 日志级别过滤（info/warning/error）

### 9.2 任务日志详情
- [ ] 任务执行完整日志存储
- [ ] 历史日志查看
- [ ] 日志搜索和过滤
- [ ] 日志导出功能

### 9.3 系统监控面板
- [ ] 实现 `backend/routers/monitor.py`
- [ ] CPU/内存使用率监控
- [ ] 磁盘空间监控
- [ ] 网络状态监控
- [ ] 实时图表展示

### 9.4 告警通知
- [ ] 任务失败告警
- [ ] 磁盘空间不足告警
- [ ] 系统资源告警阈值配置

---

## 阶段10: 稳定性增强 ⏳

**状态**: 待开始
**预计时间**: 2-3天
**目标版本**: v0.4.0

### 10.1 断点续传
- [ ] 下载断点记录和恢复
- [ ] 上传断点记录和恢复
- [ ] 进度持久化存储

### 10.2 错误恢复机制
- [ ] 自动重试策略（指数退避）
- [ ] 可配置重试次数
- [ ] 网络异常自动恢复
- [ ] 部分失败继续执行

### 10.3 数据校验
- [ ] 文件完整性校验（MD5/SHA256）
- [ ] 下载后自动验证
- [ ] 上传前后校验对比
- [ ] 校验失败自动重传

### 10.4 容错处理
- [ ] 优雅降级策略
- [ ] 服务健康自检
- [ ] 异常自动恢复
- [ ] 详细错误报告

---

## 当前待办

### 已完成 ✅
- v0.1.0: CLI工具版本发布（download + convert）
- v0.2.0: Web管理界面 + 后端API服务 + CLI工具链完整（download + convert + upload + merge）
- v0.2.1: Pipeline QC质检 + Merge功能（QC组件、结果持久化、三相机预览、快捷键）
- v0.2.2: 配置重构（统一配置模块、环境变量支持、移除硬编码）
- v0.2.3: Bug修复与QC优化（配置同步、python-dotenv、18处bug修复、三相机并排布局）
- v0.2.4: 前端代码质量优化（7处bug修复、防御性编程、类型优化、暗色主题改进）
- v0.2.5: 数据质量与转换优化（转换工具增强、对齐分析重构、QC实时同步、robot_config多机器人支持）
- v0.2.6: 转换管线健壮性增强（跳帧检测与片段切割、三相机视频对比工具、新数据集适配）

### 规划中 ⏳
- **阶段7**: UI/UX优化 → v0.3.0
- **阶段8**: 功能增强 → v0.3.1
- **阶段9**: 日志和监控 → v0.3.2
- **阶段10**: 稳定性增强 → v0.4.0

---

## 已知问题

### ✅ 已解决
1. **HDF5数据格式不匹配** (发现日期: 2025-12-28，解决日期: 2025-12-28)
   - **问题**: `scripts/convert.py` 脚本期望的数据结构与BOS上的实际数据格式不一致
   - **影响**: 无法转换 `online_test_hdf5_v1` 目录下的HDF5文件
   - **原因**:
     - 脚本期望: `observations/images_color/head`, `observations/jointstate/q` 等
     - 实际格式: `images/cam_env/frames_jpeg`, `joints/left_master/joint1_pos` 等
     - 图像存储: 脚本期望数组，实际为JPEG压缩格式
     - 多相机帧数不一致（52/44/44帧）
     - Master/Slave数据使用各自时间戳
   - **解决方案**:
     - 实现 `load_episode_v1_format()` 函数适配v1格式
     - 使用PIL解码JPEG图像
     - 实现多相机时间对齐（以最少帧数相机为基准）
     - 关节数据从250Hz对齐到~26fps图像
     - 分别处理 left_master 和 right_master 时间戳
   - **测试结果**: ✅ 通过
     - 44帧数据正确生成（State/Action各14维）
     - 时间对齐精度优秀（平均误差1-9ms）
     - 输出符合LeRobot v2.1标准
   - **状态**: ✅ 已完成

### 🔴 高优先级
- 无

---

## 技术债务

- 无

---

## 里程碑

- ✅ **2025-12-26**: 项目初始化完成，骨架搭建完成
- ✅ **2025-12-28 上午**: HDF5格式适配完成，转换功能测试通过
  - 实现v1格式加载器（JPEG解码、多相机对齐、时间同步）
  - 修复master时间戳bug和元数据维度不匹配
  - 测试结果：44帧，时间对齐误差<30ms，符合LeRobot v2.1标准
- ✅ **2025-12-28 下午**: CLI工具开发完成（阶段2.5完成） 🎉
  - **转换CLI工具**: 批量转换、并发控制、进度显示、错误处理
  - **下载CLI工具**: mc封装、BOS连接检查、进度跟踪
  - **Bug修复**: left/right slave时间戳对齐bug
  - **测试结果**:
    - 下载：18个HDF5文件，246MB，16秒
    - 转换：18个文件全部成功，17秒
- ✅ **2025-12-28**: Git版本控制初始化
  - 首次提交：c5b9ce4
  - 主分支：main
- ✅ **2025-12-28**: 🎉 v0.1.0发布！
  - 完善README.md和USER_GUIDE.md
  - CLI工具版本正式发布
- ✅ **2025-12-28**: 后端API服务完成（阶段2完成）🎉
  - 数据模型和SQLite存储
  - 下载/转换服务（异步执行、进度跟踪）
  - RESTful API（任务管理、下载、转换）
  - 开发分支：feature/backend-api（已合并到main）
- ✅ **2025-12-28**: Web前端开发完成（阶段4完成）🎉
  - Vue 3 + TypeScript + Vite + Element Plus
  - 任务看板、下载管理、转换管理、上传管理、系统状态
  - 暗色主题、响应式设计
  - 后端上传服务（upload_service.py）
- ✅ **2025-12-29**: 阶段4功能测试通过 🎉
  - 下载、转换、上传三大功能全部测试通过
  - 修复上传服务BOS路径和并发参数问题
- ✅ **2025-12-29**: CLI upload工具完成 🎉
  - 实现 `cli/upload_cli.py` 上传命令行工具
  - 支持LeRobot目录扫描、进度显示、并发上传
  - 修复上传服务logger未导入导致进度不更新的bug
- ✅ **2025-12-29**: v0.2.0 版本发布 🎉
  - Web管理界面 + 后端API服务
  - 完整CLI工具链（download + convert + upload）
- ✅ **2025-12-29**: 数据集合并工具完成（阶段2.6完成）🎉
  - 实现 `cli/merge_cli.py` 和 `scripts/merge_lerobot.py`
  - 支持多个独立LeRobot episode合并为单个数据集
  - 自动维度对齐、索引重排、元数据合并
  - 测试结果：成功合并232个episode（365k帧，696个视频，644MB）
  - 集成到CLI工具链：`pixi run merge`
- ✅ **2025-12-29**: v0.2.0最终版本发布 🎉🎉🎉
  - 完整的数据处理流水线：下载 → 转换 → 合并 → 上传
  - 4个CLI工具：download / convert / merge / upload
  - Web管理界面支持下载/转换/上传
- ✅ **2026-01-07**: CLI工具完善
  - 调整 merge 默认维度参数 (32→14)
  - 完善 CLI 使用文档
  - 新增 visualize_parquet.py 数据验证工具
- ✅ **2026-01-07**: v0.2.1 发布 - Pipeline QC质检 + Merge 功能 🎉🎉
  - **QCInspector 组件**: 三相机视频预览、通过/不通过标记
  - **QC 结果持久化**: 保存到 qc_result.json，支持断点续检
  - **Merge 服务集成**: 后端 API + 服务层，仅合并通过质检的 episode
  - **Pipeline 页面优化**: 完整工作流 Download → Convert → QC → Merge → Upload
  - **操作确认对话框**: 防止误操作
  - **快捷键支持**: ↑↓导航、P通过、F不通过、1/2/3切换相机
- ✅ **2026-01-09**: v0.2.2 发布 - 配置重构 🎉
  - **统一配置模块**: `backend/config/settings.py` 集中管理所有配置
  - **环境变量支持**: 所有参数可通过 `.env` 文件配置
  - **移除硬编码**: 删除所有开发者特定路径和魔法数字
  - **CLI工具重构**: 关键路径参数改为必填，避免误用默认值
  - **文档完善**: 新增 INSTALL.md，更新配置说明
- ✅ **2026-01-09**: v0.2.3 发布 - Bug修复与QC优化 🎉
  - **配置同步机制**: 添加 `/api/config/defaults` 端点，前端启动时获取后端配置
  - **python-dotenv集成**: 后端自动加载 `.env` 文件，配置值正确生效
  - **Bug修复**: 修复 18 处 Critical/High/Medium/Low 级别问题
  - **QC视频布局**: 三相机并排显示，提高质检效率
- ✅ **2026-01-12**: v0.2.4 发布 - 前端代码质量优化 🎉
  - **P0 严重问题**: 修复 Dashboard 筛选按钮和 TaskTable Icon 用法错误
  - **P1 中等问题**: 整合 Layout.vue import、增大 API 超时时间
  - **P2 轻微问题**: 移除冗余代码
  - **隐藏 bug**: 修复 TaskPreviewBar.vue stats 属性访问路径错误
  - **防御性编程**: 添加多处空值检查，增强代码健壮性
  - **类型优化**: 新增 API 响应接口，使用泛型替代类型断言
  - **UI 优化**: 更新暗色主题为 GitHub 风格配色
- ✅ **2026-01-15**: v0.2.5 开发启动 - 数据质量与转换优化
  - ✅ **转换工具增强**: 线性插值对齐、自适应边界裁剪
  - ✅ **Merge工具增强**: 支持 glob 模式
- ✅ **2026-01-22**: v0.2.5 - QC结果实时同步及视频加载优化 (PR #1) 🎉
  - **WebSocket 实时同步**: 多客户端 QC 结果实时广播（`/api/upload/qc/ws`）
  - **乐观锁机制**: 按 episode 粒度更新，防止并发冲突
  - **视频缓存优化**: 304 Not Modified + 缩略图 LRU 缓存
  - **前端集成**: WebSocket 重连、心跳、防抖
- ✅ **2026-01-26**: v0.2.5 - Frame-State 对齐分析工具重构完成 🎉
  - **模块化重构**: 1138行 → 8个模块（config, data_loader, video_tracker, signal_processing, visualization, analyzer, cli）
  - **新增检测模式**: 黑色区域检测（ALOHA优化，+21%相关性）
  - **新增去噪功能**: 状态引导去噪（+34.1%相关性提升）
  - **robot_config 系统**: 多机器人配置（airbot_play/aloha/galaxea_r1_lite）自动检测
  - **代码清理**: 删除废弃的 filter_lerobot 模块
- ⏳ **规划中**: 阶段7-10（UI优化、功能增强、日志监控、稳定性）
- ✅ **2026-02-11**: v0.2.6 发布 - 转换管线健壮性增强 🎉
  - **跳帧检测与片段切割**: `detect_gap_segments()` 自动检测严重跳帧，切割为有效片段
  - **三相机视频对比**: `visualize_video_sync.py` 并排拼接合成视频，帧号/相机名标注
  - **新数据集适配**: 0203_qz2_pants 158 episodes（157 无跳帧，默认 linear 对齐）
  - **数据分析**: 确认三相机无系统性时间戳偏移

---

**更新频率**: 每完成一个子任务更新一次
**最后更新**: 2026-02-11 (v0.2.6 转换管线健壮性增强)
