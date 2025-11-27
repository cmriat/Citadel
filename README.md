# LeRobot v2.1 Data Converter

将 airbot_play 双臂机器人采集的数据转换为 LeRobot v2.1 标准格式。支持三种可配置的时间对齐策略。

## 特性

- **三种对齐策略**：
  - **Nearest Neighbor** (最近邻): 简单快速，数据利用率 ~10%
  - **Action Chunking** (动作分块): 预测未来轨迹，数据利用率 100%
  - **Time Window** (时间窗口): 时间窗口内聚合，数据利用率 30-50%

- **多相机支持**: 自动同步不同帧率的相机（25Hz/30Hz）
- **数据过滤**: 自动过滤无效 episodes（时长过短、缺失数据等）
- **灵活配置**: YAML 配置文件，支持命令行参数覆盖
- **LeRobot v2.1 兼容**: 生成标准 Parquet + MP4 + metadata 格式
- **Redis 多数据源**: 支持多机器人并发采集，异步流式转换

## 数据结构

### 输入数据
```
data/
├── joints/quad_arm_task/
│   └── episode_XXXX/
│       ├── left_slave.parquet    # 左臂从端关节数据 (250Hz)
│       ├── left_master.parquet   # 左臂主端关节数据 (250Hz)
│       ├── right_slave.parquet   # 右臂从端关节数据 (250Hz)
│       ├── right_master.parquet  # 右臂主端关节数据 (250Hz)
│       └── metadata.json
└── images/quad_arm_task/
    └── episode_XXXX/
        ├── cam_left/             # 左相机 (25Hz)
        ├── cam_right/            # 右相机 (25Hz)
        ├── cam_head/             # 头部相机 (30Hz)
        └── metadata.json
```

### 输出格式（LeRobot v2.1）
```
lerobot_dataset_dual_chunking/
├── data/chunk-000/
│   └── episode_XXXXXX.parquet    # 对齐后的数据
├── videos/chunk-000/
│   ├── observation.images.cam_left/
│   ├── observation.images.cam_right/
│   └── observation.images.cam_head/
└── meta/
    ├── info.json                 # 数据集元信息
    ├── episodes.jsonl            # Episode 索引
    └── tasks.jsonl               # 任务信息
```

### Schema
- `observation.state.slave`: (14,) - 双臂从端关节位置 [left × 7, right × 7]
- `observation.state.master`: (14,) - 双臂主端关节位置 [left × 7, right × 7]
- `observation.images.*`: 三个相机的视频路径和时间戳
- `action`:
  - Nearest/Window: (14,) - 单步动作
  - Chunking: (10, 14) - 未来 10 步动作序列

## 安装

使用 Pixi 管理依赖：

```bash
# 安装依赖（包括 Redis Python 客户端）
pixi install

# 或者使用 pip（需要手动创建虚拟环境）
pip install numpy pandas pyarrow opencv-python pyyaml tqdm redis
```

**如需使用 Redis 多数据源功能，还需安装 Redis 服务器：**

```bash
# Ubuntu/Debian
sudo apt install redis-server

# macOS
brew install redis

# Docker（推荐）
docker run -d -p 6379:6379 --name redis redis:latest
```

## 使用方法

### 1. 快速开始（使用 Pixi 快捷命令）

```bash
# Action Chunking 策略（推荐，100% 数据利用率）
pixi run convert-chunking

# Nearest Neighbor 策略（快速，约 10% 数据利用率）
pixi run convert-nearest

# Time Window 策略（平衡，30-50% 数据利用率）
pixi run convert-window
```

### 2. 自定义转换

```bash
# 使用指定配置文件
python scripts/convert.py --config config/dual_arm_chunking.yaml

# 转换单个 episode
python scripts/convert.py --config config/dual_arm_nearest.yaml --episode-id episode_0001

# 覆盖配置参数
python scripts/convert.py --config config/dual_arm_chunking.yaml \
    --strategy window \
    --chunk-size 15 \
    --output ./my_output

# 完整参数列表
python scripts/convert.py --help
```

### 3. 配置文件示例

`config/dual_arm_chunking.yaml`:
```yaml
robot:
  type: "dual_arm"
  arms:
    - name: "left_slave"
      file: "left_slave.parquet"
    - name: "left_master"
      file: "left_master.parquet"
    - name: "right_slave"
      file: "right_slave.parquet"
    - name: "right_master"
      file: "right_master.parquet"
  joints_per_arm: 7

cameras:
  - name: "cam_left"
    role: "base"         # 基准时间轴
    target_fps: 25
  - name: "cam_right"
    role: "sync"
    target_fps: 25
  - name: "cam_head"
    role: "downsample"   # 从 30Hz 降采样到 25Hz
    target_fps: 25

alignment:
  strategy: "chunking"   # nearest | chunking | window
  chunk_size: 10         # Chunking 专用
  window_ms: 20          # Window 专用
  tolerance_ms: 20       # 时间容差

filtering:
  min_duration_sec: 0.5
  require_all_cameras: true
```

## Redis 多数据源流式转换

支持多台机器人并发采集数据，通过 Redis 消息队列实现异步转换。

### 使用场景

- **多机器人采集**: 多台机器人同时采集数据写入共享存储（NFS）
- **流式转换**: 采集完成后即刻发布任务，后台异步处理
- **数据源隔离**: 每个机器人独立输出目录，避免冲突
- **去重保障**: Redis 原子操作确保不重复转换

### 组件说明

1. **redis-worker** - 后台服务，监听队列并执行转换
2. **publish-task** - 任务发布工具，将 episode 加入队列
3. **monitor-redis** - 监控工具，查看队列状态和统计信息

### 快速开始

**1. 启动 Redis 服务**

```bash
# 使用 Docker（推荐）
docker run -d -p 6379:6379 --name redis redis:latest

# 或使用系统包管理器
sudo apt install redis-server
sudo systemctl start redis
```

**2. 配置 Redis 连接**

编辑 `config/redis_config.yaml`:

```yaml
redis:
  host: "localhost"      # Redis 服务器地址
  port: 6379
  queue_name: "lerobot:episodes"

sources:
  - robot_1              # 数据源列表
  - robot_2
  - robot_3

output:
  # 输出路径模板：{source}/{episode_id}_{strategy}
  pattern: "./lerobot_datasets/{source}/{episode_id}_{strategy}"

conversion:
  strategy: "chunking"   # 默认对齐策略
  config_template: "config/dual_arm_chunking.yaml"

worker:
  max_workers: 2         # 最大并发转换数
  poll_interval: 1       # 轮询间隔（秒）
```

**3. 启动 Worker 服务**

```bash
# 启动后台转换服务
pixi run redis-worker

# 或指定配置文件
pixi run redis-worker --config config/redis_config.yaml
```

**4. 发布转换任务**

```bash
# 发布单个 episode
pixi run python scripts/publish_task.py --episode episode_0007 --source robot_1

# 使用环境变量指定数据源
export ROBOT_ID=robot_2
pixi run python scripts/publish_task.py --episode episode_0008

# 指定对齐策略
pixi run python scripts/publish_task.py --episode episode_0007 --source robot_1 --strategy nearest
```

**5. 监控队列状态**

```bash
# 查看队列和统计信息
pixi run python scripts/monitor_redis.py

# 查看详细信息（包括失败任务的错误）
pixi run python scripts/monitor_redis.py -v

# 清空失败队列
pixi run python scripts/monitor_redis.py --clear-failed

# 重试失败任务
pixi run python scripts/monitor_redis.py --retry-failed
```

### 工作流程

```
采集程序 (robot_1, robot_2, ...)
    ↓
写入 NFS 共享存储
    ↓
发布任务到 Redis 队列
    ↓
Worker 监听并处理
    ↓
输出到独立目录: lerobot_datasets/robot_1/episode_0001_chunking/
```

### 集成到采集程序

在你的数据采集代码中集成任务发布：

```python
from scripts.publish_task import publish_episode

# 采集完成后发布转换任务
def on_episode_completed(episode_id):
    success = publish_episode(
        episode_id=episode_id,
        source='robot_1',       # 或从环境变量读取
        strategy='chunking'
    )

    if success:
        print(f"Published {episode_id} to conversion queue")
    else:
        print(f"Failed to publish {episode_id}")
```

### 监控输出示例

```
📊 LeRobot Redis Monitor
============================================================

📦 Queue Status
  Name: lerobot:episodes
  Pending tasks: 5
  Failed tasks:  1

🤖 Sources Statistics

  robot_1:
    Completed: 23
    Failed:    1
    Last update: 2025-11-27 14:32:15

  robot_2:
    Completed: 18
    Failed:    0
    Last update: 2025-11-27 14:30:42

✓ Total processed records: 42
```

### 验证转换结果

转换完成后，验证输出数据：

```bash
# 查看输出目录结构
ls -R lerobot_datasets/robot_1/episode_0007_chunking/

# 验证 Parquet 数据
pixi run python -c "
import pyarrow.parquet as pq
table = pq.read_table('lerobot_datasets/robot_1/episode_0007_chunking/data/chunk-000/episode_000000.parquet')
print(f'Total frames: {len(table)}')
print(table.schema)
"

# 验证视频
pixi run python -c "
import cv2
video = cv2.VideoCapture('lerobot_datasets/robot_1/episode_0007_chunking/videos/chunk-000/observation.images.cam_left/episode_000000.mp4')
print(f'Video: {int(video.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {int(video.get(cv2.CAP_PROP_FPS))}fps')
print(f'Frames: {int(video.get(cv2.CAP_PROP_FRAME_COUNT))}')
"

# 示例输出：
# Total frames: 553
# observation.state.slave: fixed_size_list<element: float>[14]
# observation.state.master: fixed_size_list<element: float>[14]
# action: fixed_size_list<element: fixed_size_list<element: float>[14]>[10]
# Video: 224x224 @ 25fps
# Frames: 553
```

## 对齐策略详解

### 1. Nearest Neighbor（最近邻）
- **原理**: 对每个相机帧，寻找时间最近的关节数据
- **优点**: 实现简单，计算快速
- **缺点**: 数据利用率低（~10%），丢失大量关节数据
- **适用**: 快速原型验证

### 2. Action Chunking（动作分块）
- **原理**: 为每个相机帧预测未来 N 步动作序列
- **优点**: 100% 数据利用率，适合模仿学习
- **缺点**: Action 维度更高 (chunk_size × action_dim)
- **适用**: 训练 Diffusion Policy 等需要轨迹预测的模型

### 3. Time Window（时间窗口）
- **原理**: 在时间窗口内聚合关节数据（平均）
- **优点**: 数据利用率适中（30-50%），减少噪声
- **缺点**: 平滑可能损失快速动作细节
- **适用**: 需要平滑轨迹的应用

## 验证输出

```bash
# 验证生成的数据集
python examples/verify_output.py --dataset lerobot_dataset_dual_chunking

# 检查元数据
cat lerobot_dataset_dual_chunking/meta/info.json | jq

# 检查 parquet 文件
python -c "
import pyarrow.parquet as pq
table = pq.read_table('lerobot_dataset_dual_chunking/data/chunk-000/episode_000000.parquet')
print(table.schema)
print(f'Rows: {len(table)}')
"

# 播放视频
mpv lerobot_dataset_dual_chunking/videos/chunk-000/observation.images.cam_left/episode_000000.mp4
```

## 项目结构

```
lerobot_convert/
├── config/                        # 配置文件
│   ├── dual_arm_chunking.yaml
│   ├── dual_arm_nearest.yaml
│   ├── dual_arm_window.yaml
│   └── redis_config.yaml          # Redis 多数据源配置
│
├── lerobot_converter/             # 核心代码（库模块）
│   ├── core/                      # 核心业务抽象
│   │   ├── __init__.py
│   │   └── task.py                # ConversionTask 定义
│   │
│   ├── common/                    # 通用工具
│   │   ├── io.py                  # 文件 I/O
│   │   ├── timestamp.py           # 时间同步
│   │   └── camera.py              # 相机同步
│   │
│   ├── aligners/                  # 对齐策略
│   │   ├── base.py
│   │   ├── nearest.py
│   │   ├── chunking.py
│   │   └── window.py
│   │
│   ├── writers/                   # 数据写入
│   │   ├── parquet.py
│   │   ├── video.py
│   │   └── metadata.py
│   │
│   ├── pipeline/                  # 转换流程
│   │   ├── config.py
│   │   ├── cleaner.py
│   │   └── converter.py
│   │
│   └── redis/                     # Redis 模块
│       ├── __init__.py
│       ├── client.py              # Redis 客户端封装
│       ├── task_queue.py          # 任务队列管理
│       ├── worker.py              # Worker 核心逻辑
│       └── monitoring.py          # 监控功能
│
├── scripts/                       # CLI 入口
│   ├── convert.py                 # 单机批量转换
│   ├── redis_worker.py            # Redis Worker 服务
│   ├── publish_task.py            # 任务发布工具
│   └── monitor_redis.py           # 监控工具
│
├── examples/
│   └── verify_output.py           # 验证脚本
│
├── pixi.toml                      # Pixi 配置
└── README.md
```

### 架构设计

**分层架构：**
- **core/** - 核心业务抽象（任务定义、策略枚举）
- **redis/** - Redis 模块（解耦业务逻辑与 Redis 交互）
- **scripts/** - CLI 入口层（仅负责参数解析和调用核心模块）

**优点：**
- ✅ Redis 逻辑与业务逻辑分离，易于测试
- ✅ 核心模块可被其他程序导入使用
- ✅ 便于扩展新的后端（Kubernetes、RabbitMQ 等）


## 常见问题

### 单机转换相关

### Q: 为什么 chunking 策略的帧数更多？
A: Chunking 使用所有相机帧，而 nearest/window 只使用能找到足够近关节数据的帧。

### Q: 如何调整 chunk_size？
A: chunk_size 决定预测的未来步数。推荐值：
- 10 (default): 覆盖 40ms 未来轨迹
- 5: 更短期预测，适合快速动作
- 20: 更长期预测，适合慢速任务

### Q: 相机帧率不一致怎么办？
A: 转换器自动将所有相机统一到 25Hz（降采样 cam_head 从 30Hz）。

### Q: 如何添加新的对齐策略？
A:
1. 在 `lerobot_converter/aligners/` 创建新文件
2. 继承 `BaseAligner` 并实现 `align()` 和 `get_action_shape()`
3. 在 `converter.py` 的 `_create_aligner()` 中注册

### Redis 多数据源相关

### Q: Redis Worker 是否需要常驻运行？
A: 是的。建议使用 systemd、supervisor 或 Docker 保持 worker 服务运行。

### Q: 如何避免重复转换？
A: Worker 使用 Redis SETNX 原子操作自动去重，相同 source + episode_id 只会处理一次。

### Q: Worker 崩溃后任务会丢失吗？
A: 不会。任务保存在 Redis 队列中，重启 Worker 后会继续处理。

### Q: 如何处理失败的任务？
A:
```bash
# 查看失败任务详情
pixi run redis-monitor -- -v

# 重试所有失败任务
pixi run redis-monitor -- --retry-failed

# 清空失败队列（不再重试）
pixi run redis-monitor -- --clear-failed
```

### Q: 多个 Worker 可以并发运行吗？
A: 可以。多个 Worker 会自动通过 Redis 队列协调，避免重复处理。

### Q: Redis 数据会占用多少空间？
A: 很少。只存储任务元数据和统计信息，实际数据存在 NFS 上。处理记录默认 30 天后自动过期。

## 性能优化

- **并行处理**: 未来可支持多进程处理 episodes
- **内存优化**: 大 episodes 可分批加载图像
- **视频编码**: 调整 CRF 和 preset 平衡质量和速度

## 引用

基于 LeRobot v2.1 格式规范：
- https://github.com/huggingface/lerobot
- https://huggingface.co/datasets/lerobot/pusht

## License

MIT
