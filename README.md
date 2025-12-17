# LeRobot v2.1 Data Converter

将机器人采集的数据转换为 LeRobot v2.1 标准格式，支持本地转换和云端自动化流程。

## 核心特性

- **三种对齐策略**: Nearest Neighbor, Action Chunking, Time Window
- **多相机支持**: 自动同步不同帧率相机（25Hz/30Hz）
- **云端自动化**: BOS扫描 → 下载 → 转换 → 上传全流程自动化
- **高并发处理**: 多线程Worker支持（单进程可配置多个worker线程）
- **分布式支持**: Redis任务队列支持多数据源、多机器并发处理
- **统一CLI**: 一个命令行工具管理所有功能
- **一键启动**: Pixi集成，无需Docker即可启动Redis服务

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
# 1. 启动 Redis（使用 pixi）
pixi run start-redis

# 验证 Redis 启动成功（在另一个终端）
pixi run check-redis  # 应该输出 PONG

# 2. 设置BOS凭证
export BOS_ACCESS_KEY="your-access-key"
export BOS_SECRET_KEY="your-secret-key"

# 3. 配置 config/storage.yaml
# 设置BOS bucket、路径、Redis连接等

# 4. 启动Scanner（扫描BOS新数据并发布任务）
# 在新终端运行，此进程会持续运行，每 120 秒扫描一次 BOS
pixi run scanner

# 5. 启动Worker（处理转换任务）
# 在新终端运行，此进程会持续运行，自动从队列拉取任务并处理
# 现在支持多线程并发处理（默认8个线程，可在 config/storage.yaml 中配置）
pixi run worker

# 6. 监控队列状态（可选）
pixi run monitor

# 停止服务
# - Redis: 按 Ctrl+C 退出
# - Scanner/Worker: 按 Ctrl+C 退出
```
---
### 最佳实践命令

#### 本地数据转换
```bash
# 转换所有 episodes
pixi run python -m lerobot_converter.cli convert -c config/demo_test.yaml

# 转换单个 episode
pixi run python -m lerobot_converter.cli convert -c config/demo_test.yaml -e episode_0001

# 覆盖输出路径
pixi run python -m lerobot_converter.cli convert -c config/demo_test.yaml -o ./custom_output
```

#### BOS 云端数据转换
需要3个终端同时运行：

**终端1 - Scanner（扫描新 episodes）**
```bash
export BOS_ACCESS_KEY=xxx
export BOS_SECRET_KEY=xxx

# 持续扫描（每120秒）
pixi run python -m lerobot_converter.cli scanner -c config/storage.yaml

# 只扫描一次
pixi run python -m lerobot_converter.cli scanner -c config/storage.yaml --once

# 完整扫描（忽略增量位置）
pixi run python -m lerobot_converter.cli scanner -c config/storage.yaml --full-scan
```

**终端2 - Worker（消费队列并转换）**
```bash
export BOS_ACCESS_KEY=xxx
export BOS_SECRET_KEY=xxx

# 启动 worker（默认配置为8个并发线程）
pixi run worker

# 指定并发数（会覆盖配置文件中的设置）
pixi run worker --max-workers 4
```

**终端3 - Monitor（监控队列，可选）**
```bash
# 实时监控队列状态
pixi run python -m lerobot_converter.cli monitor -c config/storage.yaml --refresh 5
```

#### 手动发布任务
```bash
export BOS_ACCESS_KEY=xxx
export BOS_SECRET_KEY=xxx

# 发布 BOS 上的 episode
pixi run python -m lerobot_converter.cli publish -e episode_0001 -s bos --strategy chunking
```

#### 重新处理所有 episodes（清除处理记录）
```bash
# 方式1：使用 --full-scan 参数（推荐）
pixi run python -m lerobot_converter.cli scanner -c config/storage.yaml --full-scan

# 方式2：手动清除 Redis 记录
redis-cli DEL bos:last_scanned_key
redis-cli --scan --pattern "lerobot:processed:bos:*" | xargs -r redis-cli DEL

# 然后正常启动 Scanner
pixi run scanner
```

#### 提高并发处理速度
```bash
# 方式1：配置多个worker线程（推荐）
# 单个Worker进程内使用多个线程并发处理
pixi run worker --max-workers 8

# 或在 config/storage.yaml 中配置 max_workers: 8
pixi run worker

# 方式2：启动多个Worker进程（适用于多机分布式场景）
# 在不同终端或不同机器上分别启动多个Worker进程
# 终端2
pixi run worker

# 终端3
pixi run worker

# 终端4
pixi run worker

# 注意：方式1和方式2可以结合使用，例如3个进程 × 8个线程 = 24个并发任务
```

## CLI命令一览

```bash
# Redis服务管理
pixi run start-redis                                  # 启动Redis服务
pixi run check-redis                                  # 检查Redis服务状态

# 本地转换
pixi run convert-nearest                              # Nearest策略快捷命令
pixi run convert-chunking                             # Chunking策略快捷命令
pixi run convert-window                               # Window策略快捷命令
pixi run python -m lerobot_converter.cli convert -c CONFIG_PATH

# BOS自动化
pixi run scanner                                      # 扫描BOS新数据
pixi run worker                                       # 处理转换任务（多线程）
pixi run monitor                                      # 监控队列状态
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
│   ├── writers/                # 数据输出
│   ├── utils/                  # 工具函数
│   └── cli.py                  # 统一CLI入口
├── config/                     # 配置文件
│   ├── strategies/             # 策略配置
│   └── storage.yaml            # 存储配置
└── tests/                      # 测试用例
```

## 版本

当前版本: **v2.1.0**

## License

MIT
