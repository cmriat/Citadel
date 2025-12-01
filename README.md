# LeRobot v2.1 Data Converter

将机器人采集的数据转换为 LeRobot v2.1 标准格式，支持本地转换和云端自动化流程。

## 核心特性

- **三种对齐策略**: Nearest Neighbor, Action Chunking, Time Window
- **多相机支持**: 自动同步不同帧率相机（25Hz/30Hz）
- **云端自动化**: BOS扫描 → 下载 → 转换 → 上传全流程自动化
- **分布式处理**: Redis任务队列支持多数据源并发处理
- **统一CLI**: 一个命令行工具管理所有功能

## 快速开始

### 安装

```bash
# 使用 pixi 安装依赖
pixi install
```

### 本地数据转换

```bash
# Action Chunking 策略（推荐，100% 数据利用率）
pixi run convert-chunking

# Nearest Neighbor 策略（快速，~10% 数据利用率）
pixi run convert-nearest

# Time Window 策略（平衡，30-50% 数据利用率）
pixi run convert-window

# 转换单个episode
pixi run python -m lerobot_converter.cli convert \
  -c config/strategies/chunking.yaml \
  -e episode_0001
```

### BOS云端自动化流程

```bash
# 1. 设置BOS凭证
export BOS_ACCESS_KEY="your-access-key"
export BOS_SECRET_KEY="your-secret-key"

# 2. 配置 config/storage.yaml
# 设置BOS bucket、路径、Redis连接等

# 3. 启动Scanner（扫描BOS新数据并发布任务）
pixi run scanner

# 4. 启动Worker（处理转换任务）
pixi run worker

# 5. 监控队列状态（可选）
pixi run monitor
```

### 完整命令
```bash
1️⃣ 本地数据转换
# 转换所有 episodes
pixi run python -m lerobot_converter.cli convert -c
config/demo_test.yaml

# 转换单个 episode
pixi run python -m lerobot_converter.cli convert -c
config/demo_test.yaml -e episode_0001

# 覆盖输出路径
pixi run python -m lerobot_converter.cli convert -c
config/demo_test.yaml -o ./custom_output

2️⃣ BOS 云端数据转换（需要3个终端）
# 设置 BOS 凭证（所有终端都需要）
export BOS_ACCESS_KEY=xxx
export BOS_SECRET_KEY=xxx

终端1 - 启动 Scanner（扫描新 episodes 并发布到队列）
# 持续扫描（每120秒）
pixi run python -m lerobot_converter.cli scanner -c
config/storage.yaml

# 或：只扫描一次
pixi run python -m lerobot_converter.cli scanner -c
config/storage.yaml --once

# 或：完整扫描（忽略增量位置）
pixi run python -m lerobot_converter.cli scanner -c
config/storage.yaml --full-scan

终端2 - 启动 Worker（消费队列并转换）
# 启动 worker（默认2个并发）
pixi run python -m lerobot_converter.cli worker -c
config/storage.yaml

# 或：指定并发数
pixi run python -m lerobot_converter.cli worker -c
config/storage.yaml --max-workers 4

终端3 - 监控队列（可选）
# 实时监控队列状态
pixi run python -m lerobot_converter.cli monitor -c
config/storage.yaml --refresh 5

3️⃣ 手动发布单个任务到队列
export BOS_ACCESS_KEY=xxx
export BOS_SECRET_KEY=xxx

# 发布 BOS 上的 episode
pixi run python -m lerobot_converter.cli publish -e
episode_0001 -s bos --strategy chunking
```

## CLI命令一览

```bash
# 本地转换
pixi run python -m lerobot_converter.cli convert -c CONFIG_PATH

# BOS自动化
pixi run python -m lerobot_converter.cli scanner     # 扫描BOS新数据
pixi run python -m lerobot_converter.cli worker      # 处理转换任务
pixi run python -m lerobot_converter.cli monitor     # 监控队列状态
pixi run python -m lerobot_converter.cli publish     # 手动发布任务

# 查看帮助
pixi run python -m lerobot_converter.cli --help
```

## 数据格式

### 输入数据结构
```
data/
├── joints/quad_arm_task/episode_XXXX/
│   ├── left_slave.parquet    # 左臂从端 (250Hz)
│   ├── left_master.parquet   # 左臂主端 (250Hz)
│   ├── right_slave.parquet   # 右臂从端 (250Hz)
│   └── right_master.parquet  # 右臂主端 (250Hz)
└── images/quad_arm_task/episode_XXXX/
    ├── cam_left_wrist/       # 左手腕相机 (25Hz)
    ├── cam_right_wrist/      # 右手腕相机 (25Hz)
    └── cam_env/              # 环境相机 (30Hz)
```

### 输出格式（LeRobot v2.1）
```
lerobot_dataset/
├── data/chunk-000/
│   └── episode_XXXXXX.parquet    # 对齐后的数据
├── videos/chunk-000/
│   ├── observation.images.cam_left_wrist/
│   ├── observation.images.cam_right_wrist/
│   └── observation.images.cam_env/
└── meta/
    ├── info.json                 # 数据集元信息
    ├── episodes.jsonl            # Episode索引
    └── tasks.jsonl               # 任务信息
```

## 配置文件

项目使用两类配置文件：

- **策略配置** (`config/strategies/*.yaml`): 定义对齐策略、机器人参数、相机设置
  - `chunking.yaml`: Action Chunking策略
  - `nearest.yaml`: Nearest Neighbor策略
  - `window.yaml`: Time Window策略

- **存储配置** (`config/storage.yaml`): 定义Redis、BOS连接和路径配置

详细配置说明见 [`config/README.md`](config/README.md)

## 架构概览

```
┌──────────┐     ┌───────────┐     ┌──────────┐     ┌─────────┐
│   BOS    │────▶│  Scanner  │────▶│  Redis   │────▶│ Worker  │
│ Storage  │     │ (扫描新数据) │     │  Queue   │     │(转换处理)│
└──────────┘     └───────────┘     └──────────┘     └─────────┘
                                                           │
                                                           ▼
                                                     ┌──────────┐
                                                     │   BOS    │
                                                     │ (上传结果)│
                                                     └──────────┘
```

## 对齐策略说明

| 策略 | 数据利用率 | 适用场景 | Action Shape |
|------|-----------|---------|--------------|
| **Nearest Neighbor** | ~10% | 快速验证、简单任务 | (14,) |
| **Action Chunking** | 100% | 生产环境、复杂任务 | (10, 14) |
| **Time Window** | 30-50% | 需要降噪的场景 | (14,) |

## 开发与测试

```bash
# 运行测试
pixi run test

# 代码检查
pixi run lint

# 代码格式化
pixi run format

# 启动Jupyter Lab
pixi run jupyter
```

## 文档

- [完整使用指南](USER_GUIDE.md) - 详细配置、架构说明、最佳实践
- [配置文件说明](config/README.md) - 配置文件结构和迁移指南

## 项目结构

```
lerobot_convert/
├── lerobot_converter/          # 核心包
│   ├── pipeline/               # 转换流程
│   ├── aligners/               # 对齐策略
│   ├── bos/                    # BOS集成
│   ├── redis/                  # Redis任务队列
│   └── cli.py                  # 统一CLI入口
├── config/                     # 配置文件
│   ├── strategies/             # 策略配置
│   └── storage.yaml            # 存储配置
├── scripts/                    # 辅助脚本
└── tests/                      # 测试用例
```

## 版本

当前版本: **v2.1.0**

## License

MIT
