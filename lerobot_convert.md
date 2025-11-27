# LeRobot v2.1 数据转换设计文档

> 本文档记录 airbot_play_ws 数据集转换为 LeRobot v2.1 格式的完整设计方案。
>
> **注意**: 转换工具应作为独立项目实现，不集成到 airbot_play_ws 中，以保持项目职责单一。

---

## 目录

1. [项目背景](#1-项目背景)
2. [数据探索结果](#2-数据探索结果)
3. [LeRobot v2.1 格式要求](#3-lerobot-v21-格式要求)
4. [时间对齐策略设计](#4-时间对齐策略设计)
5. [转换工具架构设计](#5-转换工具架构设计)
6. [独立项目实现建议](#6-独立项目实现建议)
7. [参考资源](#7-参考资源)

---

## 1. 项目背景

### 1.1 airbot_play_ws 数据格式

**目录结构**:
```
data/dual_arm_task/
├── episode_0001/
│   ├── metadata.json          # episode 元数据
│   ├── left_slave.parquet     # 执行端机器人关节数据 (250 Hz)
│   └── left_master.parquet    # 示教端遥操作数据 (250 Hz)
├── episode_0002/
└── ...

images/dual_arm_task/
├── episode_0001/
│   ├── metadata.json          # 图像元数据
│   ├── cam0/                  # 相机0图像 (25 Hz)
│   │   ├── {timestamp_ns}.jpg
│   │   └── ...
│   └── cam1/                  # 相机1图像 (25 Hz)
│       └── ...
└── ...
```

**数据特点**:
- 关节数据采样率: **250 Hz** (4ms 间隔)
- 图像数据采样率: **25 Hz** (40ms 间隔)
- 采样率比例: **10:1** (每 10 帧关节数据对应 1 帧图像)
- 时间戳精度: 纳秒级 (ROS2 timestamp)

### 1.2 LeRobot v2.1 格式

LeRobot 是 HuggingFace 开发的机器人学习数据集标准格式，v2.1 是当前推荐版本。

**关键特性**:
- 统一的 Parquet 数据格式
- 视频存储为 MP4 (减少存储空间)
- 标准化的元数据 schema
- 支持 action chunking (多步动作预测)

---

## 2. 数据探索结果

### 2.1 完整的 Episode 数据结构

#### Parquet 文件结构

每个 parquet 文件包含 **26 列数据**:

| 列名 | 类型 | 描述 |
|------|------|------|
| `timestamp_sec` | int64 | 秒部分 |
| `timestamp_nanosec` | int64 | 纳秒部分 |
| `joint1_pos` | float64 | 关节1位置 |
| `joint1_vel` | float64 | 关节1速度 |
| `joint1_effort` | float64 | 关节1力矩 |
| ... | ... | joint2-6 类似 |
| `eef_gripper_joint_pos` | float64 | 夹爪位置 |
| `eef_gripper_joint_vel` | float64 | 夹爪速度 |
| `eef_gripper_joint_effort` | float64 | 夹爪力矩 |
| `gripper_mapping_controller_*` | float64 | 夹爪映射控制器 (3列) |

**关键发现**:
- **left_master**: 示教端遥操作设备 → **action** (期望动作)
- **left_slave**: 执行端机器人 → **observation** (实际状态)
- master 的 `gripper_mapping_controller` vel/effort 字段存在 **100% NaN**，需忽略

### 2.2 时间戳对齐分析

#### 关节数据时间戳 (episode_0001)

**LEFT_SLAVE (执行端)**:
- 总帧数: 1058
- 持续时间: 4.2281 秒
- **采样频率: 250.23 Hz**
- 帧间隔: 平均 4.00 ms (std: 0.05 ms)

**LEFT_MASTER (示教端)**:
- 总帧数: 1058
- 持续时间: 4.2280 秒
- **采样频率: 250.24 Hz**
- 帧间隔: 平均 4.00 ms (std: 0.04 ms)

#### 图像数据时间戳 (episode_0001)

**CAM0**:
- 总帧数: 107
- 持续时间: 4.2391 秒
- **采样频率: 25.24 Hz**
- 帧间隔: 平均 39.99 ms (std: 1.05 ms)

**CAM1**:
- 总帧数: 106
- 持续时间: 4.2050 秒
- **采样频率: 25.21 Hz**
- 帧间隔: 平均 40.05 ms (std: 0.72 ms)

#### 时间对齐关系

```
Joint data (slave) 开始: 1762838885177044890
Camera 0 开始:           1762838885164685964  (提前 12.36 ms)
Camera 1 开始:           1762838885198990583  (延后 21.95 ms)
Camera sync offset:      cam1 - cam0 = 34.30 ms
```

**关键结论**:
- 采样率比例: 关节数据 ~250Hz : 图像数据 ~25Hz = **10:1**
- 每 10 帧关节数据对应 1 帧图像
- 相机之间存在 ~34ms 的时间偏移（约 0.86 帧）

### 2.3 数据集统计

- **总 episodes**: 109
- **有效图像 episodes**: 106 (3个缺少图像数据)
- **总关节数据帧数**: ~292,000 帧
- **总图像帧数**: ~213,000 帧
- **总时长**: ~4491 秒 (74.85 分钟)

**Episode 统计**:
- 平均时长: 41.20 秒
- 中位数时长: 5.77 秒
- 最短: 0.03 秒 (异常短)
- 最长: 1359.29 秒 (异常长，可能是测试数据)

### 2.4 数据质量问题

1. **缺失图像数据**: 3 个 episodes 没有图像
   - `episode_0012, 0013, 0014`
   - **转换策略**: 跳过这些 episodes

2. **NaN 值问题**:
   - Master 端: `gripper_mapping_controller_vel/effort` 100% NaN
   - 建议: 转换时忽略这些字段

3. **异常 episodes**:
   - 极短 episodes (< 0.5 秒)
   - **转换策略**: 实施数据质量过滤，过滤时长 < 0.5 秒的 episodes

### 2.5 多臂数据扩展支持

**当前数据结构（单臂）**:
```
episode_XXXX/
├── left_slave.parquet
├── left_master.parquet
└── metadata.json
```

**双臂数据结构**:
```
episode_XXXX/
├── left_slave.parquet
├── left_master.parquet
├── right_slave.parquet      # 新增
├── right_master.parquet     # 新增
└── metadata.json

images/episode_XXXX/
├── cam0/
├── cam1/
└── cam2/                    # 可能新增
```

**设计原则**:
- ✅ 配置化设计，支持任意数量的臂
- ✅ 自动检测数据结构（单臂/双臂）
- ✅ 分层特征表示：`observation.state.left`, `observation.state.right`
- ✅ 向后兼容单臂数据

---

## 3. LeRobot v2.1 格式要求

### 3.1 目录结构

```
lerobot_dataset/
├── data/
│   └── chunk-000/
│       ├── episode_000000.parquet
│       ├── episode_000001.parquet
│       └── ...
├── videos/
│   └── chunk-000/
│       ├── observation.images.cam0/
│       │   ├── episode_000000.mp4
│       │   └── ...
│       └── observation.images.cam1/
│           ├── episode_000000.mp4
│           └── ...
└── meta/
    ├── info.json          # 数据集 schema 和统计信息
    ├── episodes.jsonl     # 每个 episode 的元数据
    └── tasks.jsonl        # 任务描述
```

### 3.2 Parquet 数据 Schema

#### 单臂配置

| 特征名 | 类型 | Shape | 描述 |
|--------|------|-------|------|
| `observation.state.left` | float32 | `(7,)` | 左臂状态 (6 joints + gripper) |
| `observation.images.cam0` | VideoFrame | - | 相机0视频帧引用 |
| `observation.images.cam1` | VideoFrame | - | 相机1视频帧引用 |
| `action.left` | float32 | `(7,)` 或 `(N, 7)` | 左臂动作 (单步或 chunk) |
| `episode_index` | int64 | - | Episode 索引 |
| `frame_index` | int64 | - | 帧索引 (在 episode 内) |
| `timestamp` | int64 | - | 时间戳 (纳秒) |
| `index` | int64 | - | 全局索引 |
| `next.done` | bool | - | Episode 结束标志 |

#### 双臂配置（扩展）

| 特征名 | 类型 | Shape | 描述 |
|--------|------|-------|------|
| `observation.state.left` | float32 | `(7,)` | 左臂状态 |
| `observation.state.right` | float32 | `(7,)` | 右臂状态 |
| `observation.images.cam0` | VideoFrame | - | 相机0 |
| `observation.images.cam1` | VideoFrame | - | 相机1 |
| `observation.images.cam2` | VideoFrame | - | 相机2 (可选) |
| `action.left` | float32 | `(7,)` 或 `(N, 7)` | 左臂动作 |
| `action.right` | float32 | `(7,)` 或 `(N, 7)` | 右臂动作 |
| ... | ... | ... | 同上 |

**VideoFrame 结构**:
```python
{
    "path": "videos/chunk-000/observation.images.cam0/episode_000000.mp4",
    "timestamp": 0.04  # 视频中的时间 (秒)
}
```

**设计优势**:
- ✅ 分层特征语义清晰
- ✅ 支持独立控制单臂
- ✅ 扩展性强，支持任意数量的臂

### 3.3 Meta/info.json 结构

#### 单臂配置示例

```json
{
  "codebase_version": "v2.1",
  "robot_type": "airbot_play_single_arm",
  "total_episodes": 106,
  "total_frames": 11342,
  "total_tasks": 1,
  "total_videos": 212,
  "total_chunks": 1,
  "chunks_size": 1000,
  "fps": 25,
  "features": {
    "observation.state.left": {
      "dtype": "float32",
      "shape": [7],
      "names": ["joint_dim"]
    },
    "observation.images.cam0": {
      "dtype": "video",
      "video_info": {
        "video.fps": 25,
        "video.codec": "h264",
        "video.pix_fmt": "yuv420p",
        "video.is_depth_map": false,
        "has_audio": false
      }
    },
    "observation.images.cam1": {
      "dtype": "video",
      "video_info": { /* 同上 */ }
    },
    "action.left": {
      "dtype": "float32",
      "shape": [10, 7],
      "names": ["chunk_step", "joint_dim"]
    },
    "episode_index": {"dtype": "int64"},
    "frame_index": {"dtype": "int64"},
    "timestamp": {"dtype": "int64"},
    "index": {"dtype": "int64"},
    "next.done": {"dtype": "bool"}
  }
}
```

#### 双臂配置示例

```json
{
  "codebase_version": "v2.1",
  "robot_type": "airbot_play_dual_arm",
  "features": {
    "observation.state.left": {
      "dtype": "float32",
      "shape": [7],
      "names": ["joint_dim"]
    },
    "observation.state.right": {
      "dtype": "float32",
      "shape": [7],
      "names": ["joint_dim"]
    },
    "observation.images.cam0": { /* ... */ },
    "observation.images.cam1": { /* ... */ },
    "observation.images.cam2": { /* ... */ },
    "action.left": {
      "dtype": "float32",
      "shape": [10, 7],
      "names": ["chunk_step", "joint_dim"]
    },
    "action.right": {
      "dtype": "float32",
      "shape": [10, 7],
      "names": ["chunk_step", "joint_dim"]
    }
  }
}
```

---

## 4. 时间对齐策略设计

### 核心挑战

- **Action 采样率**: 250 Hz
- **Image 采样率**: 25 Hz
- **比例**: 10:1 (一帧图像对应 10 帧 action)

### 4.1 方案1: 最近邻对齐 (Nearest Neighbor)

**原理**: 为每个图像帧，找到时间上最近的关节数据帧。

```python
for each image_timestamp:
    # 找到时间上最近的关节数据帧
    nearest_slave_idx = argmin(|slave_timestamps - image_timestamp|)
    nearest_master_idx = argmin(|master_timestamps - image_timestamp|)

    observation = slave_data[nearest_slave_idx]  # (7,)
    action = master_data[nearest_master_idx]     # (7,)
```

**数据量**:
- Episode 有 107 帧图像 → 107 行数据
- Action shape: `(7,)` (单步动作)
- 总 action 数据点: 107 × 7 = **749**

**优点**:
- ✅ 简单直接，易于实现
- ✅ 物理意义清晰：图像时刻的实际机器人状态
- ✅ 符合大多数 LeRobot 数据集的做法

**缺点**:
- ❌ 丢弃了 90% 的关节数据
- ❌ 没有利用高频采样的信息

**适用场景**: 快速 baseline，验证数据格式正确性

---

### 4.2 方案2: Action Chunking (推荐)

**原理**: 每个 observation 对应未来的一段 action 序列。

```python
CHUNK_SIZE = 10  # 对应 40ms 的 action 序列

for each image_timestamp:
    # 当前 observation（最近邻）
    obs_idx = argmin(|slave_timestamps - image_timestamp|)
    observation = slave_data[obs_idx]  # (7,)

    # 未来 10 步 action chunk
    action_start_idx = argmin(|master_timestamps - image_timestamp|)
    action_chunk = master_data[action_start_idx : action_start_idx + 10]  # (10, 7)

    # Episode 末尾 padding
    if len(action_chunk) < 10:
        action_chunk = pad_to_size(action_chunk, 10)
```

**数据量**:
- Episode 有 107 帧图像 → 107 行数据
- Action shape: `(10, 7)` (10步chunk，每步7维)
- 总 action 数据点: 107 × 10 × 7 = **7490**

**优点**:
- ✅ **利用了所有高频数据**，不浪费信息
- ✅ 符合现代策略学习范式 (Diffusion Policy, ACT 等)
- ✅ 模型可以学习平滑的动作轨迹
- ✅ 更高的性能表现

**缺点**:
- ❌ 稍复杂，需要处理 episode 边界
- ❌ 训练时需要支持 action chunking 的模型

**Padding 策略**:
- `repeat`: 重复最后一帧 (推荐)
- `zeros`: 填充零
- `none`: 不做 padding

**适用场景**: 追求最佳性能的生产环境

---

### 4.3 方案3: 时间窗口平均 (Window Aggregation)

**原理**: 对图像帧对应的时间窗口内的所有关节数据进行聚合。

```python
WINDOW_SIZE_MS = 40  # 时间窗口大小

for each image_timestamp:
    # 定义时间窗口
    window_start = image_timestamp - 20ms
    window_end = image_timestamp + 20ms

    # 找到窗口内的所有帧
    slave_indices = find_in_window(slave_timestamps, window_start, window_end)
    master_indices = find_in_window(master_timestamps, window_start, window_end)

    # 聚合（均值、中位数或插值）
    observation = aggregate(slave_data[slave_indices])  # (7,)
    action = aggregate(master_data[master_indices])     # (7,)
```

**聚合方法**:
- `mean`: 均值（最平滑）
- `median`: 中位数（对异常值更鲁棒）
- `interpolate`: 线性插值（更精确）

**数据量**:
- Episode 有 107 帧图像 → 107 行数据
- Action shape: `(7,)` (单步动作)
- 总 action 数据点: 107 × 7 = **749**

**优点**:
- ✅ 平滑噪声，鲁棒性好
- ✅ 利用了部分高频信息

**缺点**:
- ❌ 平均会损失动态信息
- ❌ 物理意义不如最近邻清晰

**适用场景**: 数据噪声较大的场景

---

### 4.4 策略对比

| 策略 | Action Shape | 数据利用率 | 实现难度 | 物理意义 | 性能潜力 |
|------|-------------|----------|---------|---------|---------|
| **最近邻** | `(7,)` | 10% | ⭐ 简单 | ⭐⭐⭐ 清晰 | ⭐⭐ 中等 |
| **Action Chunking** | `(10, 7)` | 100% | ⭐⭐ 中等 | ⭐⭐ 较清晰 | ⭐⭐⭐ 最高 |
| **时间窗口** | `(7,)` | 30-50% | ⭐⭐ 中等 | ⭐ 模糊 | ⭐⭐ 中等 |

**推荐顺序**:
1. **先实现最近邻**：快速验证转换流程
2. **再实现 Action Chunking**：追求最佳性能
3. **可选实现时间窗口**：用于对比实验

---

## 5. 转换工具架构设计

### 5.1 整体架构 (Pipeline 模式)

```
lerobot_converter/                   # 项目根目录
├── README.md
├── pixi.toml                        # Pixi 依赖和环境配置
├── pixi.lock                        # 自动生成
│
├── config/                          # 配置文件
│   ├── single_arm_nearest.yaml     # 单臂 + 最近邻策略
│   ├── single_arm_chunking.yaml    # 单臂 + Action Chunking
│   ├── dual_arm_chunking.yaml      # 双臂 + Action Chunking
│   └── window.yaml                 # 时间窗口策略
│
├── lerobot_converter/              # 核心代码包
│   ├── __init__.py
│   │
│   ├── pipeline/                   # 转换流水线模块
│   │   ├── __init__.py
│   │   ├── converter.py            # 主转换器（工厂+编排）
│   │   ├── cleaner.py              # 数据清洗和过滤
│   │   ├── config.py               # 配置加载和管理
│   │   └── validator.py            # 数据验证
│   │
│   ├── aligners/                   # 对齐策略模块
│   │   ├── __init__.py
│   │   ├── base.py                 # 抽象基类
│   │   ├── nearest.py              # 最近邻实现
│   │   ├── chunking.py             # Action Chunking 实现
│   │   └── window.py               # 时间窗口实现
│   │
│   ├── writers/                    # 数据写入器
│   │   ├── __init__.py
│   │   ├── parquet.py              # Parquet 文件写入
│   │   ├── video.py                # 视频编码
│   │   └── metadata.py             # 元数据生成
│   │
│   └── common/                     # 公共工具
│       ├── __init__.py
│       ├── timestamp.py            # 时间戳处理
│       └── io.py                   # 文件读写工具
│
├── scripts/                        # 可执行脚本
│   └── convert.py                  # CLI 入口
│
└── tests/                          # 测试目录
    ├── test_aligners.py
    ├── test_converter.py
    └── test_cleaner.py
```

### 5.2 Pixi 配置

**pixi.toml**:

```toml
[project]
name = "lerobot_converter"
version = "0.1.0"
description = "Convert airbot_play data to LeRobot v2.1 format"
channels = ["conda-forge"]
platforms = ["linux-64"]

[dependencies]
python = ">=3.10"
numpy = ">=1.24.0"
pandas = ">=2.0.0"
pyarrow = ">=14.0.0"
opencv = ">=4.8.0"
pillow = ">=10.0.0"
pyyaml = ">=6.0"
tqdm = ">=4.65.0"

[feature.dev.dependencies]
pytest = ">=7.4.0"
jupyterlab = ">=4.0.0"
ruff = ">=0.1.0"

[tasks]
# 转换命令
convert = "python scripts/convert.py"
convert-single-nearest = "python scripts/convert.py --config config/single_arm_nearest.yaml"
convert-single-chunking = "python scripts/convert.py --config config/single_arm_chunking.yaml"
convert-dual-chunking = "python scripts/convert.py --config config/dual_arm_chunking.yaml"

# 测试命令
test = "pytest tests/ -v"
lint = "ruff check lerobot_converter/"
format = "ruff format lerobot_converter/"
```

### 5.3 抽象基类设计（支持多臂）

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple
import numpy as np

class BaseAligner(ABC):
    """时间对齐策略的抽象基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.tolerance_ms = config.get('tolerance_ms', 20)

    @abstractmethod
    def align(
        self,
        image_timestamps: np.ndarray,
        arm_data: Dict[str, Dict],  # {'left': {timestamps, states, actions}, ...}
    ) -> List[Dict]:
        """
        对齐图像和关节数据（支持多臂）

        Args:
            image_timestamps: 图像时间戳数组
            arm_data: 字典，包含每个臂的数据
                {
                    'left': {
                        'slave_timestamps': np.ndarray,
                        'slave_states': np.ndarray,  # (N, 7)
                        'master_timestamps': np.ndarray,
                        'master_actions': np.ndarray  # (N, 7)
                    },
                    'right': { ... }  # 可选
                }

        Returns:
            List[Dict]: 每个元素包含:
                - timestamp: int
                - observation.state.left: np.ndarray
                - observation.state.right: np.ndarray (可选)
                - action.left: np.ndarray
                - action.right: np.ndarray (可选)
        """
        pass

    @abstractmethod
    def get_action_shape(self, arm_name: str) -> Tuple:
        """返回指定臂的 action shape"""
        pass

    def _find_nearest(self, timestamps: np.ndarray, target: int) -> int:
        """找到最近的时间戳索引"""
        return int(np.argmin(np.abs(timestamps - target)))
```

### 5.4 策略实现示例（支持多臂）

#### 最近邻对齐器

```python
class NearestAligner(BaseAligner):
    """最近邻对齐策略（支持多臂）"""

    def align(self, image_timestamps, arm_data) -> List[Dict]:
        aligned_frames = []
        tolerance_ns = self.tolerance_ms * 1_000_000

        for img_ts in image_timestamps:
            frame = {'timestamp': img_ts}

            # 对齐每个臂
            for arm_name, data in arm_data.items():
                slave_idx = self._find_nearest(data['slave_timestamps'], img_ts)
                master_idx = self._find_nearest(data['master_timestamps'], img_ts)

                # 检查时间容差
                if abs(data['slave_timestamps'][slave_idx] - img_ts) > tolerance_ns:
                    continue

                frame[f'observation.state.{arm_name}'] = data['slave_states'][slave_idx]  # (7,)
                frame[f'action.{arm_name}'] = data['master_actions'][master_idx]         # (7,)

            aligned_frames.append(frame)

        return aligned_frames

    def get_action_shape(self, arm_name: str) -> Tuple:
        return (7,)  # (joint_dim,)
```

#### Action Chunking 对齐器

```python
class ChunkingAligner(BaseAligner):
    """Action Chunking 对齐策略（支持多臂）"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.chunk_size = config.get('chunk_size', 10)
        self.padding_mode = config.get('padding_mode', 'repeat')

    def align(self, image_timestamps, arm_data) -> List[Dict]:
        aligned_frames = []

        for img_ts in image_timestamps:
            frame = {'timestamp': img_ts}

            # 对齐每个臂
            for arm_name, data in arm_data.items():
                # 当前 observation
                slave_idx = self._find_nearest(data['slave_timestamps'], img_ts)
                frame[f'observation.state.{arm_name}'] = data['slave_states'][slave_idx]  # (7,)

                # 未来 chunk_size 步的 action
                master_idx = self._find_nearest(data['master_timestamps'], img_ts)
                action_chunk = data['master_actions'][master_idx : master_idx + self.chunk_size]

                # 处理 episode 末尾的 padding
                if len(action_chunk) < self.chunk_size:
                    action_chunk = self._pad_chunk(action_chunk)

                frame[f'action.{arm_name}'] = action_chunk  # (chunk_size, 7)

            aligned_frames.append(frame)

        return aligned_frames

    def _pad_chunk(self, chunk: np.ndarray) -> np.ndarray:
        """处理 episode 末尾的 padding"""
        if self.padding_mode == 'repeat':
            padding = np.repeat(chunk[-1:], self.chunk_size - len(chunk), axis=0)
            return np.vstack([chunk, padding])
        elif self.padding_mode == 'zeros':
            padding = np.zeros((self.chunk_size - len(chunk), chunk.shape[1]))
            return np.vstack([chunk, padding])
        else:
            return chunk

    def get_action_shape(self, arm_name: str) -> Tuple:
        return (self.chunk_size, 7)  # (chunk_size, joint_dim)
```

### 5.5 主转换器（支持多臂配置化）

```python
class LeRobotConverter:
    """主转换器（策略无关，支持多臂）"""

    def __init__(self, config: Dict):
        self.config = config
        self.arms = config['robot']['arms']  # 列表，支持任意数量的臂
        self.cameras = config['cameras']      # 列表，支持任意数量的相机

        # 工厂方法：根据配置创建对齐器
        self.aligner = self._create_aligner()

        # 初始化其他组件
        self.cleaner = DataCleaner(config)
        self.parquet_writer = ParquetWriter(config)
        self.video_encoder = VideoEncoder(config)
        self.metadata_generator = MetadataGenerator(config)

    def _create_aligner(self) -> BaseAligner:
        """工厂方法：根据配置创建对齐器"""
        strategy = self.config['alignment']['strategy']

        if strategy == 'nearest':
            return NearestAligner(self.config['alignment'])
        elif strategy == 'chunking':
            return ChunkingAligner(self.config['alignment'])
        elif strategy == 'window':
            return WindowAligner(self.config['alignment'])
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def convert(self):
        """执行完整转换流程"""
        # 1. 数据清洗
        valid_episodes = self.cleaner.scan_and_filter()
        print(f"Found {len(valid_episodes)} valid episodes")

        # 2. 逐 episode 转换
        for episode_id in tqdm(valid_episodes):
            self._convert_episode(episode_id)

        # 3. 生成元数据
        self.metadata_generator.generate(
            arms=self.arms,
            cameras=self.cameras,
            aligner=self.aligner
        )

    def _convert_episode(self, episode_id: str):
        """转换单个 episode（支持多臂）"""
        # 1. 加载所有臂的关节数据
        arm_data = {}
        for arm in self.arms:
            slave = self._load_joint_data(episode_id, arm['slave_file'])
            master = self._load_joint_data(episode_id, arm['master_file'])

            arm_data[arm['name']] = {
                'slave_timestamps': slave['timestamps'],
                'slave_states': slave['states'],      # (N, 7)
                'master_timestamps': master['timestamps'],
                'master_actions': master['actions']   # (N, 7)
            }

        # 2. 加载图像元数据
        image_meta = self._load_image_metadata(episode_id)
        cam0_timestamps = image_meta['cameras']['cam0']['timestamps']

        # 3. 时间对齐（策略模式）
        aligned_frames = self.aligner.align(
            image_timestamps=cam0_timestamps,  # 使用 cam0 作为基准
            arm_data=arm_data
        )

        # 4. 对齐其他相机
        for frame in aligned_frames:
            for cam in self.cameras:
                cam_name = cam['name']
                if cam_name == 'cam0':
                    continue  # cam0 已经是基准

                cam_ts_list = image_meta['cameras'][cam_name]['timestamps']
                cam_idx = self.aligner._find_nearest(
                    np.array(cam_ts_list),
                    frame['timestamp']
                )
                frame[f'observation.images.{cam_name}'] = {
                    'cam_index': cam_idx,
                    'timestamp': cam_ts_list[cam_idx]
                }

        # 5. 写入 Parquet
        self.parquet_writer.save_episode(episode_id, aligned_frames)

        # 6. 编码视频
        self.video_encoder.encode_episode(episode_id, image_meta)

    def _load_joint_data(self, episode_id: str, parquet_file: str) -> Dict:
        """加载关节数据"""
        df = pd.read_parquet(f"{self.config['input']['data_path']}/{episode_id}/{parquet_file}")

        timestamps = df['timestamp_sec'] * 1e9 + df['timestamp_nanosec']
        states = df[[
            'joint1_pos', 'joint2_pos', 'joint3_pos',
            'joint4_pos', 'joint5_pos', 'joint6_pos',
            'eef_gripper_joint_pos'
        ]].to_numpy()

        return {
            'timestamps': timestamps.to_numpy(),
            'states': states
        }

    def _load_image_metadata(self, episode_id: str) -> Dict:
        """加载图像元数据"""
        with open(f"{self.config['input']['images_path']}/{episode_id}/metadata.json") as f:
            return json.load(f)
```

### 5.6 配置文件示例

#### 单臂 + Action Chunking

```yaml
# config/single_arm_chunking.yaml
robot:
  type: "single_arm"
  arms:
    - name: "left"
      slave_file: "left_slave.parquet"
      master_file: "left_master.parquet"
      joints_dim: 7

cameras:
  - name: "cam0"
  - name: "cam1"

input:
  data_path: "/home/admin01/maoz/airbot_play_ws/data/dual_arm_task"
  images_path: "/home/admin01/maoz/airbot_play_ws/images/dual_arm_task"

output:
  base_path: "./lerobot_dataset_single_chunking"
  dataset_name: "airbot_play_single_arm"

alignment:
  strategy: "chunking"
  tolerance_ms: 20
  chunk_size: 10
  padding_mode: "repeat"

filtering:
  min_duration_sec: 0.5
  require_images: true
  skip_episodes: ["episode_0012", "episode_0013", "episode_0014"]

video:
  fps: 25
  codec: "h264"
  crf: 23
  preset: "medium"
```

#### 双臂 + Action Chunking

```yaml
# config/dual_arm_chunking.yaml
robot:
  type: "dual_arm"
  arms:
    - name: "left"
      slave_file: "left_slave.parquet"
      master_file: "left_master.parquet"
      joints_dim: 7
    - name: "right"
      slave_file: "right_slave.parquet"
      master_file: "right_master.parquet"
      joints_dim: 7

cameras:
  - name: "cam0"
  - name: "cam1"
  - name: "cam2"

input:
  data_path: "/home/admin01/maoz/airbot_play_ws_dual/data/dual_arm_task"
  images_path: "/home/admin01/maoz/airbot_play_ws_dual/images/dual_arm_task"

output:
  base_path: "./lerobot_dataset_dual_chunking"
  dataset_name: "airbot_play_dual_arm"

alignment:
  strategy: "chunking"
  tolerance_ms: 20
  chunk_size: 10
  padding_mode: "repeat"

filtering:
  min_duration_sec: 0.5
  require_images: true

video:
  fps: 25
  codec: "h264"
  crf: 23
  preset: "medium"
```

#### 最近邻策略

```yaml
# config/single_arm_nearest.yaml
robot:
  type: "single_arm"
  arms:
    - name: "left"
      slave_file: "left_slave.parquet"
      master_file: "left_master.parquet"
      joints_dim: 7

cameras:
  - name: "cam0"
  - name: "cam1"

input:
  data_path: "/home/admin01/maoz/airbot_play_ws/data/dual_arm_task"
  images_path: "/home/admin01/maoz/airbot_play_ws/images/dual_arm_task"

output:
  base_path: "./lerobot_dataset_single_nearest"
  dataset_name: "airbot_play_single_arm"

alignment:
  strategy: "nearest"
  tolerance_ms: 20

filtering:
  min_duration_sec: 0.5
  require_images: true
  skip_episodes: ["episode_0012", "episode_0013", "episode_0014"]

video:
  fps: 25
  codec: "h264"
  crf: 23
  preset: "medium"
```

### 5.7 CLI 接口

```bash
# 使用 pixi 运行

# 1. 单臂 + 最近邻策略
pixi run convert-single-nearest

# 2. 单臂 + Action Chunking
pixi run convert-single-chunking

# 3. 双臂 + Action Chunking
pixi run convert-dual-chunking

# 4. 自定义参数
pixi run convert \
  --config config/single_arm_chunking.yaml \
  --output ./custom_output

# 5. 测试单个 episode
pixi run convert \
  --config config/single_arm_nearest.yaml \
  --episode-id episode_0001 \
  --output ./test_output

# 6. 命令行覆盖配置
pixi run convert \
  --config config/single_arm_chunking.yaml \
  --chunk-size 15 \
  --output ./lerobot_chunk15
```

---

## 6. 独立项目实现建议

### 6.1 为什么独立实现？

airbot_play_ws 项目职责:
- ✅ 硬件适配 (ROS2 drivers)
- ✅ 实时控制
- ✅ 数据采集
- ❌ 数据格式转换（应独立）

**独立项目的好处**:
1. **职责单一**: airbot_play_ws 专注硬件控制
2. **易于维护**: 转换逻辑独立迭代
3. **复用性强**: 可适配其他机器人数据集
4. **依赖隔离**: 不污染主项目依赖

### 6.2 项目结构

```
lerobot_converter/                   # 当前目录（已存在）
├── README.md                        # 项目说明
├── lerobot_convert.md              # 本设计文档
├── pixi.toml                        # Pixi 配置
├── pixi.lock                        # 自动生成
│
├── config/
│   ├── single_arm_nearest.yaml
│   ├── single_arm_chunking.yaml
│   └── dual_arm_chunking.yaml
│
├── lerobot_converter/
│   ├── pipeline/
│   ├── aligners/
│   ├── writers/
│   └── common/
│
├── scripts/
│   └── convert.py
│
└── tests/
    └── ...
```

### 6.3 依赖管理 (Pixi)

**pixi.toml** (已在 5.2 节详细说明):

```bash
# 初始化 Pixi 环境
pixi install

# 运行转换
pixi run convert-single-chunking

# 开发测试
pixi run test
pixi run lint
```

### 6.4 与 airbot_play_ws 的关系

```
/home/admin01/maoz/
├── airbot_play_ws/
│   ├── data/dual_arm_task/          # 数据采集输出
│   └── images/dual_arm_task/
│
└── lerobot_convert/                 # 独立转换项目（当前目录）
    ├── lerobot_converter/
    ├── config/
    └── scripts/convert.py

使用流程:
1. airbot_play_ws 采集数据 → data/ + images/
2. lerobot_convert 读取数据 → 转换 → lerobot_dataset/
3. lerobot_dataset/ 用于训练模型
```

### 6.5 数据映射建议

```python
# 单臂配置
observation = {
    "observation.state.left": left_slave[joint1-6 positions + eef_gripper_joint_pos],  # (7,)
    "observation.images.cam0": VideoFrame(path, timestamp),
    "observation.images.cam1": VideoFrame(path, timestamp),
}

action = {
    "action.left": left_master[joint1-6 positions + eef_gripper_joint_pos],  # (7,) or (10, 7)
}

# 双臂配置
observation = {
    "observation.state.left": left_slave[...],   # (7,)
    "observation.state.right": right_slave[...], # (7,)
    "observation.images.cam0": VideoFrame(...),
    "observation.images.cam1": VideoFrame(...),
    "observation.images.cam2": VideoFrame(...),  # 可选
}

action = {
    "action.left": left_master[...],   # (7,) or (10, 7)
    "action.right": right_master[...], # (7,) or (10, 7)
}

# 字段选择
✅ 使用: joint1-6 的 position
✅ 使用: eef_gripper_joint_pos
❌ 忽略: gripper_mapping_controller (master 端 100% NaN)
⚠️ 可选: velocity, effort (可能不稳定)
```

### 6.6 实施步骤

#### Phase 1: 项目初始化
```bash
# 1. 确认当前目录
pwd  # /home/admin01/maoz/lerobot_convert

# 2. 创建 pixi.toml
# (使用 5.2 节的配置)

# 3. 初始化环境
pixi install

# 4. 创建目录结构
mkdir -p lerobot_converter/{pipeline,aligners,writers,common}
mkdir -p config scripts tests
```

#### Phase 2: 核心模块实现（按优先级）

**优先级 1: 基础框架**
- [ ] `pipeline/config.py` - 配置加载
- [ ] `common/io.py` - 文件读写工具
- [ ] `common/timestamp.py` - 时间戳处理

**优先级 2: 数据清洗**
- [ ] `pipeline/cleaner.py` - 扫描和过滤 episodes
  - 实现过滤规则：缺失图像、时长 < 0.5秒
  - 生成有效 episodes 列表

**优先级 3: 对齐器（最近邻优先）**
- [ ] `aligners/base.py` - 抽象基类
- [ ] `aligners/nearest.py` - 最近邻实现（先验证流程）
- [ ] 测试单个 episode

**优先级 4: 写入器**
- [ ] `writers/parquet.py` - Parquet 文件写入
- [ ] `writers/video.py` - JPG → MP4 编码
- [ ] `writers/metadata.py` - 生成 meta/info.json 等

**优先级 5: 主转换器**
- [ ] `pipeline/converter.py` - 主转换器（工厂+编排）
- [ ] `scripts/convert.py` - CLI 入口

**优先级 6: 其他对齐策略**
- [ ] `aligners/chunking.py` - Action Chunking（推荐）
- [ ] `aligners/window.py` - 时间窗口（可选）

#### Phase 3: 测试验证

```bash
# 1. 测试单个 episode（最近邻）
pixi run convert \
  --config config/single_arm_nearest.yaml \
  --episode-id episode_0001 \
  --output ./test_output

# 2. 验证 LeRobot 格式
python -c "
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
dataset = LeRobotDataset('./test_output')
print(f'Total frames: {len(dataset)}')
print(f'First frame keys: {dataset[0].keys()}')
print(f'Action shape: {dataset[0][\"action.left\"].shape}')
"

# 3. 批量转换（3种策略）
pixi run convert-single-nearest      # 输出到 ./lerobot_dataset_single_nearest
pixi run convert-single-chunking     # 输出到 ./lerobot_dataset_single_chunking
pixi run convert-dual-chunking       # 输出到 ./lerobot_dataset_dual_chunking (需双臂数据)

# 4. 生成转换报告
# - 总 episodes 数
# - 过滤掉的 episodes
# - 转换耗时
# - 输出数据集大小
```

#### Phase 4: 文档和发布

- [ ] 完善 README.md
  - 安装说明
  - 使用示例
  - 配置说明
- [ ] 添加示例 notebook
- [ ] 编写测试用例

---

## 7. 参考资源

### 7.1 LeRobot 官方资源

- **GitHub**: https://github.com/huggingface/lerobot
- **文档**: https://huggingface.co/docs/lerobot
- **数据集格式文档**: https://huggingface.co/docs/lerobot/en/lerobot-dataset-v3
  - 注: v3.0 文档也适用于 v2.1，核心格式类似
- **加载数据集示例**: https://github.com/huggingface/lerobot/blob/main/examples/1_load_lerobot_dataset.py

### 7.2 转换工具示例

- **pusht_zarr_format.py**: https://github.com/huggingface/lerobot/blob/main/lerobot/common/datasets/push_dataset_to_hub/pusht_zarr_format.py
- **aloha_hdf5_format.py**: https://github.com/huggingface/lerobot/blob/main/lerobot/common/datasets/push_dataset_to_hub/aloha_hdf5_format.py
- **umi_zarr_format.py**: https://github.com/huggingface/lerobot/blob/main/lerobot/common/datasets/push_dataset_to_hub/umi_zarr_format.py

### 7.3 相关讨论

- **自定义数据集转换**: https://github.com/huggingface/lerobot/issues/547
- **v2.1 格式说明**: https://github.com/huggingface/lerobot/pull/461
- **Action Chunking 实现**: https://github.com/huggingface/lerobot/issues/761

### 7.4 数据探索工具

在 airbot_play_ws 中可以使用 Jupyter 探索数据:

```bash
pixi run -e ros2 launch_jupyter_lab
```

然后创建 notebook 加载 parquet:

```python
import pandas as pd
import pyarrow.parquet as pq

# 读取关节数据
df = pd.read_parquet("data/dual_arm_task/episode_0001/left_slave.parquet")
print(df.head())
print(df.columns)
print(df.describe())

# 读取元数据
import json
with open("data/dual_arm_task/episode_0001/metadata.json") as f:
    metadata = json.load(f)
print(metadata)
```

---

## 总结

本文档提供了从 airbot_play_ws 数据转换到 LeRobot v2.1 格式的完整设计方案:

1. **数据探索**: 深入分析了数据结构、采样率、时间戳对齐关系
2. **格式要求**: 详细说明了 LeRobot v2.1 的目录结构、数据 schema、元数据规范
3. **对齐策略**: 设计了三种时间对齐策略（最近邻、Action Chunking、时间窗口）
4. **架构设计**: Pipeline 模式，模块化、可扩展的转换工具架构
5. **多臂支持**: 配置化设计，支持单臂/双臂自动切换，使用分层特征表示
6. **实施建议**: 独立项目实现，使用 Pixi 管理依赖，详细的实施步骤

**关键特性**:
- ✅ 三种对齐策略都实现，作为可选参数
- ✅ 支持单臂和双臂配置（通过 YAML 配置）
- ✅ 数据质量过滤（过滤缺失图像、时长 < 0.5秒的 episodes）
- ✅ 支持自定义输出路径
- ✅ 使用 Pixi 进行依赖管理
- ✅ Pipeline 模式的清晰代码组织

**下一步行动**:
1. 初始化 Pixi 环境和项目结构
2. 实现基础框架和数据清洗模块
3. 先实现最近邻策略，快速验证流程
4. 再实现 Action Chunking 策略，追求最佳性能
5. 等待双臂数据后，验证多臂配置功能
6. 使用转换后的数据集训练 VLA 模型

---

**文档维护**:
- 创建日期: 2025-01-26
- 最后更新: 2025-01-26 (更新：Pipeline 模式、Pixi 管理、多臂支持)
- 维护者: airbot_play_ws 项目组
