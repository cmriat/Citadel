# LeRobot v2.1 Converter - 完整使用指南

详细的配置、架构说明和最佳实践。

## 目录

- [系统架构](#系统架构)
- [安装和配置](#安装和配置)
- [本地数据转换](#本地数据转换)
- [BOS云端自动化](#bos云端自动化)
- [Redis任务队列](#redis任务队列)
- [对齐策略详解](#对齐策略详解)
- [配置文件详解](#配置文件详解)
- [故障排除](#故障排除)
- [最佳实践](#最佳实践)

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         数据源层                                  │
├─────────────────────────────────────────────────────────────────┤
│  本地文件系统          BOS云存储           其他数据源              │
│  real_datas/          srgdata/           ...                    │
└──────┬──────────────────┬──────────────────────────────────────┘
       │                  │
       │                  ▼
       │            ┌──────────┐
       │            │  Scanner │  ← 定时扫描BOS新数据
       │            └────┬─────┘
       │                 │
       │                 ▼
       │            ┌──────────┐
       │            │  Redis   │  ← 任务队列（支持多数据源）
       │            │  Queue   │
       │            └────┬─────┘
       │                 │
       ▼                 ▼
┌─────────────────────────────────┐
│         LeRobot Converter        │
│  ┌─────────────────────────┐   │
│  │  Data Loader             │   │  ← 读取关节/图像数据
│  └─────────┬───────────────┘   │
│            ▼                     │
│  ┌─────────────────────────┐   │
│  │  Aligner                 │   │  ← 时间对齐（3种策略）
│  │  - Nearest Neighbor      │   │
│  │  - Action Chunking       │   │
│  │  - Time Window           │   │
│  └─────────┬───────────────┘   │
│            ▼                     │
│  ┌─────────────────────────┐   │
│  │  Writer                  │   │  ← 生成Parquet + MP4
│  └─────────┬───────────────┘   │
└────────────┼───────────────────┘
             │
             ▼
     ┌───────────────┐
     │ LeRobot v2.1  │  ← 标准格式输出
     │   Dataset     │
     └───────┬───────┘
             │
             ▼
     ┌───────────────┐
     │  BOS Upload   │  ← 上传到云存储（可选）
     └───────────────┘
```

### 核心模块

#### 1. Pipeline (流程控制)
- **LeRobotConverter**: 主转换器，协调整个流程
- **DataLoader**: 加载关节和图像数据
- **Writer**: 生成LeRobot格式输出

#### 2. Aligners (对齐策略)
- **NearestAligner**: 最近邻匹配
- **ChunkingAligner**: Action Chunking
- **WindowAligner**: 时间窗口聚合

#### 3. BOS (云存储集成)
- **BosClient**: BOS连接客户端
- **BosDownloader**: 下载BOS数据
- **BosUploader**: 上传转换结果
- **EpisodeScanner**: 扫描新episodes

#### 4. Redis (任务队列)
- **RedisClient**: Redis连接客户端
- **TaskQueue**: 任务发布/消费
- **RedisWorker**: Worker进程

#### 5. CLI (统一命令行接口)
- **cli.py**: 统一的命令行入口，集成所有功能

---

## 安装和配置

### 系统要求

- Python >= 3.10
- Redis Server (如使用Redis功能)
- BOS凭证 (如使用BOS功能)

### 安装步骤

#### 1. 使用Pixi（推荐）

```bash
# 克隆项目
git clone <repo-url>
cd lerobot_convert

# 安装依赖
pixi install

# 验证安装
pixi run python -m lerobot_converter.cli --version
```

#### 2. 使用pip

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install numpy pandas pyarrow opencv-python pyyaml tqdm redis boto3 click

# 安装项目（开发模式）
pip install -e .
```

### Redis安装

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis

# Docker（推荐）
docker run -d -p 6379:6379 --name redis redis:latest

# 验证Redis连接
redis-cli ping  # 应返回 PONG
```

### BOS凭证配置

```bash
# 设置环境变量
export BOS_ACCESS_KEY="your-access-key"
export BOS_SECRET_KEY="your-secret-key"

# 或在 ~/.bashrc 或 ~/.zshrc 中添加
echo 'export BOS_ACCESS_KEY="your-access-key"' >> ~/.bashrc
echo 'export BOS_SECRET_KEY="your-secret-key"' >> ~/.bashrc
source ~/.bashrc
```

---

## 本地数据转换

### 基本用法

```bash
# 使用预定义策略转换所有episodes
pixi run convert-chunking
pixi run convert-nearest
pixi run convert-window

# 转换单个episode
pixi run python -m lerobot_converter.cli convert \
  -c config/strategies/chunking.yaml \
  -e episode_0001

# 覆盖策略和输出路径
pixi run python -m lerobot_converter.cli convert \
  -c config/strategies/chunking.yaml \
  --strategy window \
  --output ./custom_output
```

### 输入数据要求

#### 目录结构

```
data_root/
├── joints/
│   └── task_name/
│       └── episode_XXXX/
│           ├── left_slave.parquet
│           ├── left_master.parquet
│           ├── right_slave.parquet
│           ├── right_master.parquet
│           └── metadata.json (可选)
└── images/
    └── task_name/
        └── episode_XXXX/
            ├── cam_left_wrist/
            │   ├── 1234567890.jpg
            │   └── ...
            ├── cam_right_wrist/
            └── cam_env/
```

#### Parquet文件格式

关节数据Parquet文件必须包含以下列：
- `timestamps`: int64，微秒时间戳
- `joint_0` 到 `joint_6`: float64，关节位置

```python
# 示例：验证Parquet文件
import pandas as pd
df = pd.read_parquet("left_slave.parquet")
print(df.columns)  # ['timestamps', 'joint_0', ..., 'joint_6']
print(df['timestamps'].dtype)  # int64
```

#### 图像文件要求

- 格式: JPEG (.jpg)
- 命名: `<timestamp>.jpg` (微秒时间戳)
- 分辨率: 任意（推荐640x480或更高）

### 输出数据结构

```
lerobot_dataset/
├── data/
│   └── chunk-000/
│       ├── episode_000000.parquet
│       ├── episode_000001.parquet
│       └── ...
├── videos/
│   └── chunk-000/
│       ├── observation.images.cam_left_wrist/
│       │   ├── episode_000000.mp4
│       │   └── ...
│       ├── observation.images.cam_right_wrist/
│       └── observation.images.cam_env/
└── meta/
    ├── info.json           # 数据集元信息
    ├── episodes.jsonl      # Episode索引
    └── tasks.jsonl         # 任务信息
```

#### info.json示例

```json
{
  "codebase_version": "v2.0",
  "robot_type": "dual_arm",
  "total_episodes": 100,
  "total_frames": 98650,
  "total_tasks": 1,
  "fps": 30,
  "features": {
    "observation.state.slave": {
      "dtype": "float32",
      "shape": [14],
      "names": ["left_joint_0", ..., "right_joint_6"]
    },
    "action": {
      "dtype": "float32",
      "shape": [10, 14]  // Chunking策略
    }
  }
}
```

---

## BOS云端自动化

### 工作流程

```
1. Scanner扫描BOS → 2. 发布任务到Redis → 3. Worker消费任务 → 4. 上传结果到BOS
     (定期)              (去重)                (并发)            (自动)
```

### 配置BOS

编辑 `config/storage.yaml`:

```yaml
bos:
  endpoint: "https://bd.bcebos.com"
  bucket: "srgdata"

  # 路径配置
  paths:
    raw_data_prefix: "raw_datas/"           # 原始数据前缀
    converted_prefix: "converted_datas/"    # 转换后数据前缀

  # 扫描配置
  scanner:
    interval: 120                           # 扫描间隔（秒）
    incremental_key: "bos:last_scanned_key" # Redis增量扫描键
    min_episode_files: 10                   # 最小文件数判断

  # 下载配置
  download:
    temp_dir: "${LEROBOT_TEMP_DIR}"         # 临时目录（支持环境变量）
    batch_size: 100                         # 批量下载大小

  # 上传配置
  upload:
    parallel_uploads: 4                     # 并发上传数
```

### 启动BOS自动化

#### 1. 启动Scanner（扫描器）

```bash
# 使用默认配置
pixi run scanner

# 自定义扫描间隔
pixi run python -m lerobot_converter.cli scanner \
  -c config/storage.yaml \
  --interval 300

# 单次扫描（不循环）
pixi run python -m lerobot_converter.cli scanner --once

# 完整扫描（忽略增量位置）
pixi run python -m lerobot_converter.cli scanner --full-scan
```

Scanner输出示例:
```
🚀 Starting BOS Scanner
Interval: 120s
Prefix: raw_datas/
Press Ctrl+C to stop

[Scan #1] Scanning BOS...
✓ Found 3 ready episodes
  → Published: episode_0001
  → Published: episode_0002
  → Published: episode_0003
Waiting 120s until next scan...
```

#### 2. 启动Worker（工作进程）

```bash
# 使用默认配置
pixi run worker

# 指定数据源
pixi run python -m lerobot_converter.cli worker \
  -c config/storage.yaml \
  -s robot_1

# 设置最大并发数
pixi run python -m lerobot_converter.cli worker --max-workers 4
```

Worker输出示例:
```
🚀 Starting Redis Worker...
Queue: lerobot:episodes
Press Ctrl+C to stop

[2025-11-28 10:00:00] Processing task: episode_0001 (source: bos)
  ↓ Downloading from BOS... (3156 files)
  ⚙ Converting... (986 frames)
  ↑ Uploading to BOS... (7 files)
✓ Task completed in 45.2s

[2025-11-28 10:00:45] Processing task: episode_0002 (source: bos)
...
```

#### 3. 监控队列状态

```bash
# 启动监控
pixi run monitor

# 自定义刷新间隔
pixi run python -m lerobot_converter.cli monitor --refresh 10
```

监控输出示例:
```
============================================================
Queue Status (updated every 5s)
============================================================
Pending Tasks: 12
Failed Tasks: 1

Source Statistics:
  local: ✓ 45  ✗ 2
  bos: ✓ 120  ✗ 1
  robot_1: ✓ 30  ✗ 0
============================================================

Press Ctrl+C to exit
```

### BOS数据格式

#### BOS上的原始数据格式

```
raw_datas/
└── episode_XXXX/
    ├── images/
    │   ├── cam_left_wrist/
    │   │   ├── 1234567890.jpg
    │   │   └── ...
    │   ├── cam_right_wrist/
    │   └── cam_env/
    └── joints/
        ├── left_slave.parquet
        ├── left_master.parquet
        ├── right_slave.parquet
        └── right_master.parquet
```

#### BOS上的转换后数据格式

```
converted_datas/
└── episode_XXXX_chunking/      # 策略名称后缀
    ├── data/
    ├── videos/
    └── meta/
```

---

## Redis任务队列

### 架构说明

```
┌───────────┐     ┌─────────────┐     ┌──────────┐
│ Publisher │────▶│ Redis Queue │────▶│  Worker  │
│(Scanner等)│     │(lerobot:...)│     │(多个实例)│
└───────────┘     └─────────────┘     └──────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ Deduplication│ ← processed:{source}:{episode}
                  │ Failed Queue │ ← lerobot:failed
                  │ Statistics   │ ← stats:{source}:{metric}
                  └──────────────┘
```

### Redis键说明

- `lerobot:episodes`: 主任务队列（List）
- `lerobot:failed`: 失败任务队列（List）
- `lerobot:processed:{source}:{episode_id}`: 去重标记（Key, TTL=7天）
- `lerobot:stats:{source}:completed`: 完成计数（String）
- `lerobot:stats:{source}:failed`: 失败计数（String）
- `bos:last_scanned_key`: Scanner增量扫描位置（String）

### 手动发布任务

```bash
# 发布本地转换任务
pixi run python -m lerobot_converter.cli publish \
  -c config/storage.yaml \
  -e episode_0001 \
  -s local \
  --strategy chunking

# 发布BOS转换任务
pixi run python -m lerobot_converter.cli publish \
  -e episode_0002 \
  -s bos \
  --strategy nearest
```

### 任务数据格式

```json
{
  "episode_id": "episode_0001",
  "source": "bos",
  "strategy": "chunking",
  "config_overrides": {},
  "timestamp": 1764564821.036
}
```

### 多数据源配置

在 `config/storage.yaml` 中配置多个数据源:

```yaml
sources:
  - robot_1    # 机器人1
  - robot_2    # 机器人2
  - robot_3    # 机器人3

output:
  pattern: "./lerobot_datasets/{source}/{episode_id}_{strategy}"
```

每个数据源的任务独立统计和处理。

---

## 对齐策略详解

### 1. Nearest Neighbor（最近邻）

#### 原理
为每个相机帧时间戳，找到时间上最接近的关节数据点。

#### 数学描述
```
对于相机时间戳 t_cam:
  选择关节时间戳 t_joint 满足:
    |t_joint - t_cam| = min(|t_joints - t_cam|)
    且 |t_joint - t_cam| <= tolerance_ms
```

#### 优点
- 实现简单，计算快速
- 适合数据探索和快速验证

#### 缺点
- 数据利用率低（~10%），大量关节数据被丢弃
- 动作是单步的，无法表达运动趋势

#### 配置示例
```yaml
alignment:
  strategy: "nearest"
  tolerance_ms: 20    # 最大时间差容忍（毫秒）
```

#### 输出Schema
```python
{
  "action": (14,),  # 单步动作
  "observation.state.slave": (14,),
  "observation.state.master": (14,)
}
```

### 2. Action Chunking（动作分块）

#### 原理
从每个相机帧时间戳开始，生成未来N步的动作序列。

#### 数学描述
```
对于相机时间戳 t_cam 和 chunk_size=10:
  action[i] = joints at timestamp closest to (t_cam + i * Δt)
  其中 Δt = 1000ms / joints_fps (如 1000/250 = 4ms)
```

#### 优点
- **100%数据利用率**：每个关节数据点都被使用
- 包含运动轨迹信息，有利于策略学习
- 适合需要预测未来动作的任务

#### 缺点
- Action维度较高 (chunk_size × joint_dim)
- 需要padding处理episode末尾

#### 配置示例
```yaml
alignment:
  strategy: "chunking"
  chunk_size: 10          # 未来步数
  padding_mode: "repeat"  # episode末尾padding方式: repeat/edge/constant
  tolerance_ms: 20
```

#### 输出Schema
```python
{
  "action": (10, 14),     # 10步未来动作序列
  "observation.state.slave": (14,),
  "observation.state.master": (14,)
}
```

### 3. Time Window（时间窗口）

#### 原理
在时间窗口内聚合多个关节数据点（平均或中位数），降低噪声。

#### 数学描述
```
对于相机时间戳 t_cam 和 window_ms=20:
  选择所有满足的关节时间戳:
    |t_joint - t_cam| <= window_ms

  action = mean(selected_joints) 或 median(selected_joints)
```

#### 优点
- 平滑降噪，鲁棒性好
- 数据利用率中等（30-50%）
- 适合噪声较大的传感器数据

#### 缺点
- 可能丢失高频运动细节
- 计算复杂度略高于Nearest

#### 配置示例
```yaml
alignment:
  strategy: "window"
  window_ms: 20           # 时间窗口大小（毫秒）
  aggregation: "mean"     # 聚合方法: mean | median
  tolerance_ms: 20
```

#### 输出Schema
```python
{
  "action": (14,),        # 聚合后的单步动作
  "observation.state.slave": (14,),
  "observation.state.master": (14,)
}
```

### 策略选择指南

| 场景 | 推荐策略 | 理由 |
|------|---------|------|
| 生产环境训练 | **Chunking** | 100%数据利用，轨迹信息丰富 |
| 快速原型验证 | Nearest | 简单快速 |
| 传感器噪声大 | Window | 降噪效果好 |
| 计算资源受限 | Nearest | 计算量最小 |
| 需要预测未来 | **Chunking** | 包含未来轨迹 |

---

## 配置文件详解

### 策略配置文件（config/strategies/*.yaml）

#### chunking.yaml完整示例

```yaml
# ============================================================
# 机器人配置
# ============================================================
robot:
  type: "dual_arm"
  arms:
    - name: "left_slave"
      file: "left_slave.parquet"
      role: "slave"
    - name: "left_master"
      file: "left_master.parquet"
      role: "master"
    - name: "right_slave"
      file: "right_slave.parquet"
      role: "slave"
    - name: "right_master"
      file: "right_master.parquet"
      role: "master"
  joints_per_arm: 7

# ============================================================
# 相机配置
# ============================================================
cameras:
  - name: "cam_left_wrist"
    role: "base"          # base: 基准相机，其他相机向它对齐
    target_fps: 25
  - name: "cam_right_wrist"
    role: "sync"          # sync: 同步到base相机
    target_fps: 25
  - name: "cam_env"
    role: "downsample"    # downsample: 降采样（如30Hz → 25Hz）
    target_fps: 30

# ============================================================
# 输入路径配置
# ============================================================
input:
  data_path: "./real_datas/qurd_arm_task"
  images_path: "./real_datas/qurd_arm_task"

# ============================================================
# 输出配置
# ============================================================
output:
  base_path: "./lerobot_dataset_chunking"
  dataset_name: "airbot_play_dual_arm"

# ============================================================
# 对齐策略配置
# ============================================================
alignment:
  strategy: "chunking"
  chunk_size: 10
  padding_mode: "repeat"
  tolerance_ms: 20

# ============================================================
# 过滤配置
# ============================================================
filtering:
  min_duration_sec: 0.5     # 过滤时长 < 0.5秒的episodes
  require_all_cameras: true # 要求所有相机数据完整

# ============================================================
# 视频编码配置
# ============================================================
video:
  fps: 30
  codec: "h264"
  crf: 23                   # 质量（0-51，越小越好）
  preset: "medium"          # 编码速度: ultrafast|fast|medium|slow
```

### 存储配置文件（config/storage.yaml）

```yaml
# ============================================================
# Redis配置
# ============================================================
redis:
  host: "localhost"
  port: 6379
  password: null
  db: 0
  queue_name: "lerobot:episodes"
  max_workers: 2
  poll_interval: 1          # Worker轮询间隔（秒）

# ============================================================
# BOS配置
# ============================================================
bos:
  endpoint: "https://bd.bcebos.com"
  bucket: "srgdata"

  paths:
    raw_data_prefix: "raw_datas/"
    converted_prefix: "converted_datas/"

  scanner:
    interval: 120
    incremental_key: "bos:last_scanned_key"
    min_episode_files: 10

  download:
    temp_dir: "${LEROBOT_TEMP_DIR}"
    batch_size: 100

  upload:
    parallel_uploads: 4

# ============================================================
# 数据源配置
# ============================================================
sources:
  - local
  - bos

# ============================================================
# 输出配置
# ============================================================
output:
  pattern: "./lerobot_datasets/{source}/{episode_id}_{strategy}"

# ============================================================
# 转换配置
# ============================================================
conversion:
  strategy: "chunking"
  config_template: "config/strategies/chunking.yaml"

# ============================================================
# 日志配置
# ============================================================
logging:
  level: "INFO"           # DEBUG | INFO | WARNING | ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

## 故障排除

### 常见问题

#### 1. ModuleNotFoundError: No module named 'lerobot_converter'

**原因**: Python路径配置问题

**解决方案**:
```bash
# 方案1: 使用pixi运行
pixi run python -m lerobot_converter.cli --help

# 方案2: 设置PYTHONPATH
export PYTHONPATH=/path/to/lerobot_convert:$PYTHONPATH
python -m lerobot_converter.cli --help

# 方案3: 安装为包（开发模式）
pip install -e .
```

#### 2. Redis连接失败

**错误信息**: `ConnectionError: Error connecting to Redis`

**解决方案**:
```bash
# 检查Redis是否运行
redis-cli ping

# 如未运行，启动Redis
# Docker
docker start redis
# 或
docker run -d -p 6379:6379 --name redis redis:latest

# 系统服务
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

#### 3. BOS Access Denied

**错误信息**: `BceServerException: Access denied to bucket 'srgdata'`

**解决方案**:
```bash
# 检查环境变量
echo $BOS_ACCESS_KEY
echo $BOS_SECRET_KEY

# 重新设置凭证
export BOS_ACCESS_KEY="your-access-key"
export BOS_SECRET_KEY="your-secret-key"

# 测试BOS连接
pixi run python -c "
from lerobot_converter.bos import BosClient
client = BosClient('config/storage.yaml')
print('✓ BOS连接成功' if client.test_connection() else '✗ BOS连接失败')
"
```

#### 4. KeyError: 'timestamps'

**错误信息**: `KeyError: 'timestamps'`

**原因**: Parquet文件缺少timestamps列

**解决方案**:
```python
# 验证Parquet文件格式
import pandas as pd
df = pd.read_parquet("left_slave.parquet")
print(df.columns)  # 应包含 'timestamps', 'joint_0', ..., 'joint_6'

# 如果缺少timestamps，需要重新生成数据
```

#### 5. 缺失图像文件警告

**警告信息**: `WARNING - Missing image file: cam_left/1234567890.jpg`

**原因**:
- 图像文件命名不匹配时间戳
- 部分图像文件丢失

**解决方案**:
```bash
# 检查图像文件命名格式
ls real_datas/images/quad_arm_task/episode_0001/cam_left/ | head

# 应为: 1234567890.jpg (纯数字时间戳)

# 如果缺失大量图像，检查原始采集数据
```

#### 6. 内存不足

**错误信息**: `MemoryError` 或系统卡顿

**原因**: 大型episode或多worker并发

**解决方案**:
```bash
# 减少worker数量
pixi run python -m lerobot_converter.cli worker --max-workers 1

# 或分批转换
pixi run python -m lerobot_converter.cli convert \
  -c config/strategies/chunking.yaml \
  -e episode_0001  # 单个episode
```

---

## 最佳实践

### 1. 生产环境部署

#### 推荐架构
```
┌─────────────────────────────────────────────┐
│          多台采集机器人                       │
│  ┌──────┐  ┌──────┐  ┌──────┐              │
│  │Robot1│  │Robot2│  │Robot3│              │
│  └──┬───┘  └──┬───┘  └──┬───┘              │
└─────┼─────────┼─────────┼───────────────────┘
      │         │         │
      ▼         ▼         ▼
┌────────────────────────────────────┐
│         BOS云存储（raw_datas/）      │
└─────────────┬──────────────────────┘
              │
              ▼
       ┌──────────────┐
       │   Scanner    │ ← 单实例，定时扫描
       │  (cronjob)   │
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │ Redis Queue  │ ← 集中式任务队列
       └──────┬───────┘
              │
       ┌──────┴────────┬────────┐
       ▼               ▼         ▼
  ┌─────────┐    ┌─────────┐  ┌─────────┐
  │Worker 1 │    │Worker 2 │  │Worker 3 │ ← 多实例并发
  └────┬────┘    └────┬────┘  └────┬────┘
       │              │            │
       └──────────────┴────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │  BOS (converted_/)   │
            └─────────────────────┘
```

#### 部署步骤

```bash
# 1. 配置环境变量（所有机器）
export BOS_ACCESS_KEY="xxx"
export BOS_SECRET_KEY="xxx"
export LEROBOT_TEMP_DIR="/data/lerobot_temp"

# 2. 启动Redis（单实例，推荐云Redis）
docker run -d \
  --name redis \
  -p 6379:6379 \
  -v /data/redis:/data \
  redis:latest redis-server --appendonly yes

# 3. 启动Scanner（单实例，cronjob或systemd）
# systemd示例: /etc/systemd/system/lerobot-scanner.service
[Unit]
Description=LeRobot BOS Scanner
After=network.target

[Service]
Type=simple
User=lerobot
WorkingDirectory=/opt/lerobot_convert
ExecStart=/usr/local/bin/pixi run scanner
Restart=always

[Install]
WantedBy=multi-user.target

# 启动服务
sudo systemctl start lerobot-scanner
sudo systemctl enable lerobot-scanner

# 4. 启动多个Worker实例
# Worker 1
pixi run worker &

# Worker 2
pixi run worker &

# Worker 3
pixi run worker &
```

### 2. 性能优化

#### 提升转换速度

```yaml
# config/storage.yaml

# 优化BOS下载
bos:
  download:
    batch_size: 200        # 增加批量下载（默认100）

# 优化BOS上传
bos:
  upload:
    parallel_uploads: 8    # 增加并发上传（默认4）

# 增加Worker数量
redis:
  max_workers: 4           # 默认2
```

```yaml
# config/strategies/chunking.yaml

# 优化视频编码
video:
  codec: "h264"
  preset: "ultrafast"      # 最快编码（文件略大）
  crf: 28                  # 降低质量（减小文件）
```

#### 监控性能

```bash
# 监控队列处理速度
pixi run monitor

# 查看Worker日志
tail -f /var/log/lerobot/worker.log

# Redis队列长度
redis-cli llen lerobot:episodes

# 系统资源
htop
iotop
```

### 3. 数据质量检查

#### 自动过滤配置

```yaml
# config/strategies/chunking.yaml

filtering:
  min_duration_sec: 1.0          # 最小时长（秒）
  max_duration_sec: 300.0        # 最大时长（秒）
  require_all_cameras: true      # 要求所有相机
  min_frames: 10                 # 最小帧数
  max_timestamp_gap_ms: 100      # 最大时间戳间隔
```

#### 手动验证

```bash
# 验证输出数据
pixi run python examples/verify_output.py \
  --dataset-path ./lerobot_dataset_chunking \
  --episode-id episode_000000

# 检查视频
ffprobe videos/chunk-000/observation.images.cam_left_wrist/episode_000000.mp4

# 检查Parquet
pixi run python -c "
import pandas as pd
df = pd.read_parquet('data/chunk-000/episode_000000.parquet')
print(df.shape)
print(df.columns)
print(df.head())
"
```

### 4. 备份和恢复

#### 定期备份

```bash
# 备份BOS数据（增量）
aws s3 sync s3://srgdata/raw_datas/ /backup/raw_datas/ \
  --endpoint-url https://bd.bcebos.com

# 备份Redis状态
redis-cli --rdb /backup/redis_dump.rdb

# 备份配置文件
tar -czf /backup/config_$(date +%Y%m%d).tar.gz config/
```

#### 灾难恢复

```bash
# 恢复Redis
redis-cli --rdb /backup/redis_dump.rdb
redis-cli BGREWRITEAOF

# 重新扫描BOS（完整扫描）
pixi run scanner --full-scan --once

# 重新发布失败任务
redis-cli lrange lerobot:failed 0 -1 | while read task; do
  redis-cli rpush lerobot:episodes "$task"
done
```

### 5. 安全性

```bash
# 使用密钥管理工具（推荐）
# 例如: AWS Secrets Manager, HashiCorp Vault

# 限制Redis访问
# redis.conf
bind 127.0.0.1
requirepass your-strong-password

# 更新config/storage.yaml
redis:
  password: "${REDIS_PASSWORD}"  # 从环境变量读取

# BOS凭证轮换
# 定期更新BOS_ACCESS_KEY和BOS_SECRET_KEY
```

### 6. 日志管理

```yaml
# config/storage.yaml

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "/var/log/lerobot/converter.log"  # 日志文件
  max_bytes: 10485760    # 10MB
  backup_count: 5        # 保留5个备份
```

```bash
# 日志轮转（logrotate）
# /etc/logrotate.d/lerobot
/var/log/lerobot/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 lerobot lerobot
}
```

---

## 附录

### A. CLI命令速查表

```bash
# 本地转换
pixi run convert-chunking                    # 使用chunking策略
pixi run python -m lerobot_converter.cli convert -c CONFIG -e EPISODE

# BOS自动化
pixi run python -m lerobot_converter.cli scanner     # 扫描BOS新数据
pixi run python -m lerobot_converter.cli worker      # 处理转换任务
pixi run python -m lerobot_converter.cli monitor     # 监控队列状态
pixi run python -m lerobot_converter.cli publish     # 手动发布任务

# 查看帮助
pixi run python -m lerobot_converter.cli --help
pixi run python -m lerobot_converter.cli convert --help
pixi run python -m lerobot_converter.cli scanner --help
```

### B. 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `BOS_ACCESS_KEY` | BOS访问密钥 | 必需 |
| `BOS_SECRET_KEY` | BOS密钥密钥 | 必需 |
| `LEROBOT_TEMP_DIR` | 临时目录 | 系统temp |
| `REDIS_PASSWORD` | Redis密码 | null |

### C. 性能基准

基于单worker，i7-12700K，32GB RAM，SSD:

| Episode大小 | 策略 | 处理时间 | 吞吐量 |
|------------|------|---------|--------|
| 1000帧 | Nearest | ~15s | ~66 fps |
| 1000帧 | Chunking | ~25s | ~40 fps |
| 1000帧 | Window | ~20s | ~50 fps |
| 5000帧 | Chunking | ~90s | ~55 fps |

### D. 版本历史

- **v2.1.0** (2025-11-28): 统一CLI、配置重构、文档简化
- **v2.0.0** (2025-11-27): Redis多数据源、BOS集成
- **v1.0.0** (2025-11-25): 初始版本，三种对齐策略

---

## 支持

- 问题反馈: [GitHub Issues](https://github.com/your-repo/issues)
- 文档主页: [README.md](README.md)
- 配置说明: [config/README.md](config/README.md)
