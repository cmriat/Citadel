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
# 安装依赖
pixi install

# 或者使用 pip（需要手动创建虚拟环境）
pip install numpy pandas pyarrow opencv-python pyyaml tqdm
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
│   └── dual_arm_window.yaml
├── lerobot_converter/             # 核心代码
│   ├── common/                    # 通用工具
│   │   ├── io.py                  # 文件 I/O
│   │   ├── timestamp.py           # 时间同步
│   │   └── camera.py              # 相机同步
│   ├── aligners/                  # 对齐策略
│   │   ├── base.py
│   │   ├── nearest.py
│   │   ├── chunking.py
│   │   └── window.py
│   ├── writers/                   # 数据写入
│   │   ├── parquet.py
│   │   ├── video.py
│   │   └── metadata.py
│   └── pipeline/                  # 转换流程
│       ├── config.py
│       ├── cleaner.py
│       └── converter.py
├── scripts/
│   └── convert.py                 # CLI 入口
├── examples/
│   └── verify_output.py           # 验证脚本
├── pixi.toml                      # Pixi 配置
└── README.md
```

## 常见问题

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
