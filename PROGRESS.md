# Citadel_release 开发进度

## 项目信息

- **开始日期**: 2025-12-26
- **当前版本**: v0.2.0
- **项目状态**: ✅ 阶段4完成
- **当前分支**: feature/backend-api

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
- ✅ `/data/maozan/code/Citadel_release/pixi.toml`
- ✅ `/data/maozan/code/Citadel_release/scripts/download.sh`
- ✅ `/data/maozan/code/Citadel_release/scripts/convert.py` (已适配v1格式)
- ✅ `/data/maozan/code/Citadel_release/cli/download_cli.py`
- ✅ `/data/maozan/code/Citadel_release/cli/convert_cli.py`

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

### 2.5.3 工具模块 ✅
- [x] 创建 `cli/utils/mc_executor.py` 骨架
- [x] 实现mc命令执行和进度解析
- [x] 实现实时输出捕获
- [x] 实现BOS连接检查
- [x] 创建 `cli/utils/progress.py` 骨架
- [x] 实现ProgressTracker进度跟踪器

---

## 阶段3: 日志和监控 ⏳

**状态**: 未开始
**预计时间**: 1天

- [ ] 实现日志流服务 (`backend/services/log_streamer.py`)
- [ ] WebSocket日志推送
- [ ] 实现监控API (`backend/routers/monitor.py`)
- [ ] 系统状态检测

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

## 当前待办

### 已完成 ✅
所有计划的CLI版本功能已完成，v0.1.0已发布。

### 后续规划（可选）
**选项A: 继续开发后端+前端（完整系统）**
- 阶段2: 后端核心服务（2天）
- 阶段3: 日志和监控（1天）
- 阶段4: Web前端（3天）

**选项B: 功能扩展**
- 添加数据验证工具
- 统计报告生成
- 多种输出格式支持

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
  - 分支：feature/backend-api
- ✅ **2025-12-28**: Web前端开发完成（阶段4完成）🎉
  - Vue 3 + TypeScript + Vite + Element Plus
  - 任务看板、下载管理、转换管理、上传管理、系统状态
  - 暗色主题、响应式设计
  - 后端上传服务（upload_service.py）
- ✅ **2025-12-29**: 阶段4功能测试通过 🎉
  - 下载、转换、上传三大功能全部测试通过
  - 修复上传服务BOS路径和并发参数问题
  - v0.2.0 版本发布
- ⏳ **下一步**: UI/UX优化、日志监控（可选）

---

**更新频率**: 每完成一个子任务更新一次
**最后更新**: 2025-12-29 (阶段4测试通过，v0.2.0发布)
