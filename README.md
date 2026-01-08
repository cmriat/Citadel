# Citadel Release

BOS数据管理系统 - 用于机器人数据下载、转换和上传

## 项目简介

Citadel Release 是一套完整的机器人数据管理工具，包含命令行工具(CLI)和Web管理界面，用于从百度对象存储(BOS)下载机器人数据（HDF5格式），批量转换为LeRobot v2.1标准格式，并上传回BOS。

### 核心功能

- **BOS数据下载**: 使用mc (MinIO Client)高效下载，支持并发控制和进度显示
- **HDF5格式转换**: 批量转换为LeRobot v2.1格式（包含meta、data、videos）
- **数据集合并**: 将多个独立episode合并为单个LeRobot数据集
- **LeRobot数据上传**: 将转换后的数据上传回BOS存储
- **Web管理界面**: 现代化Vue 3界面，支持任务管理、进度监控
- **并发处理**: 支持多文件并发转换，提高处理效率
- **进度监控**: 实时显示下载、转换和上传进度

## 快速开始

### 前置要求

1. **Linux环境** (测试于 Ubuntu 20.04+)
2. **mc (MinIO Client)** - 需要预先配置BOS别名
3. **pixi** - Python环境管理工具

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd Citadel_release

# 安装依赖
pixi install

# 验证安装
pixi run download --help
pixi run convert --help
```

## 使用方式

### 方式一：Web管理界面（推荐）

启动后端和前端服务：

```bash
# 终端1：启动后端API服务
pixi run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 终端2：启动前端开发服务器
cd frontend && npm run dev
```

访问 **http://localhost:5173** 即可使用Web界面。

**功能页面：**
| 页面 | 功能 |
|------|------|
| 任务看板 | 查看所有任务状态、进度、统计 |
| 下载管理 | 配置BOS路径，启动下载任务 |
| 转换管理 | 扫描HDF5文件，批量转换 |
| 上传管理 | 扫描LeRobot目录，上传到BOS |
| **Pipeline** | 一站式流水线：下载 → 转换 → QC质检 → 合并 → 上传 |
| 系统状态 | 查看系统健康状态和任务统计 |

#### Pipeline 页面特性

**一站式数据处理流水线**：
```
Download → Convert → QC 质检 → Merge → Upload
                        ↓
              视频播放器 → 标记通过/不通过
                        ↓
              只合并「通过」的 episode
```

**QC 质检功能**：
- 三相机视频预览（环境、左腕、右腕）
- 通过/不通过标记，支持批量操作
- 质检结果自动保存和恢复
- 支持断点续检（自动定位到上次进度）

**快捷键**：
| 按键 | 功能 |
|------|------|
| ↑/↓ 或 j/k | 导航 episode |
| P / Enter | 标记通过 |
| F / Backspace | 标记不通过 |
| 空格 | 播放/暂停视频 |
| 1/2/3 | 切换相机视角 |

### 方式二：命令行工具（CLI）

#### 1. 下载HDF5文件

从BOS下载机器人数据：

```bash
pixi run download \
  --bos-path "srgdata/robot/raw_data/upload_test/online_test_hdf5_v1/fold_laundry/" \
  --local-path "/home/user/data/fold_laundry/raw_hdf5/" \
  --concurrency 10
```

**参数说明：**
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--bos-path` | BOS远程路径（不含bos:前缀） | `srgdata/robot/raw_data/...` |
| `--local-path` | 本地保存路径 | `test_data/download_test/` |
| `--concurrency` | 并发下载数 | `10` |
| `--mc-path` | mc可执行文件路径 | `/home/maozan/mc` |

#### 2. 批量转换HDF5文件

将下载的HDF5文件转换为LeRobot v2.1格式：

```bash
pixi run convert \
  --input-dir "/home/user/data/fold_laundry/raw_hdf5/" \
  --output-dir "/home/user/data/fold_laundry/lerobot_v21/" \
  --robot-type "airbot_play" \
  --fps 25 \
  --task "Fold the laundry" \
  --parallel-jobs 4
```

**参数说明：**
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--input-dir` | 输入HDF5目录 | `test_data/download_test/` |
| `--output-dir` | 输出LeRobot目录 | `test_data/convert_test/` |
| `--robot-type` | 机器人类型 | `airbot_play` |
| `--fps` | 视频帧率 | `25` |
| `--task` | 任务描述 | `Fold the laundry` |
| `--parallel-jobs` | 并发转换数 | `4` |
| `--file-pattern` | 文件匹配模式 | `episode_*.h5` |

#### 3. 上传LeRobot数据

将转换后的LeRobot数据上传到BOS：

```bash
pixi run upload \
  --local-dir "/home/user/data/fold_laundry/lerobot_v21/" \
  --bos-path "srgdata/robot/lerobot_data/fold_laundry/" \
  --concurrency 10
```

**参数说明：**
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--local-dir` | 本地LeRobot目录 | `./data/lerobot/` |
| `--bos-path` | BOS目标路径（不含bos/前缀） | `srgdata/robot/lerobot_data/` |
| `--concurrency` | 并发上传数 | `10` |
| `--mc-path` | mc可执行文件路径 | `/home/maozan/mc` |

#### 4. 合并LeRobot数据集

将多个独立的LeRobot episode合并为单个数据集：

```bash
pixi run merge \
  --sources "./output/episode_0001/" "./output/episode_0002/" "./output/episode_0003/" \
  --output "./merged_dataset/" \
  --state-max-dim 14 \
  --action-max-dim 14 \
  --fps 25
```

**参数说明：**
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--sources` | 源数据集路径列表（支持通配符） | 必填 |
| `--output` | 输出合并数据集路径 | 必填 |
| `--state-max-dim` | 状态向量最大维度 | `32` |
| `--action-max-dim` | 动作向量最大维度 | `32` |
| `--fps` | 视频帧率 | `25` |
| `--copy-images` | 是否复制图像文件 | `False` |

**使用场景：**
- 将HDF5转换后的多个独立episode合并为单个训练集
- 统一不同维度的state/action向量
- 自动重新编号episode索引和帧索引
- 合并元数据、统计信息和任务列表

**示例（使用通配符）：**
```bash
# 合并所有 episode_* 目录
pixi run merge --sources ./converted/episode_* --output ./merged/
```

## 项目结构

```
Citadel_release/
├── cli/                      # 命令行工具
│   ├── download_cli.py       # 下载CLI
│   ├── convert_cli.py        # 转换CLI
│   ├── upload_cli.py         # 上传CLI
│   ├── merge_cli.py          # 合并CLI
│   └── utils/                # 工具模块
│       ├── mc_executor.py    # mc命令封装
│       └── progress.py       # 进度跟踪
├── scripts/                  # 核心脚本
│   ├── download.sh           # 下载脚本
│   ├── convert.py            # 转换脚本
│   └── merge_lerobot.py      # 合并脚本
├── backend/                  # 后端API服务
│   ├── main.py               # FastAPI入口
│   ├── models/               # 数据模型
│   │   └── task.py           # 任务模型
│   ├── routers/              # API路由
│   │   ├── tasks.py          # 任务管理API
│   │   ├── download.py       # 下载API
│   │   ├── convert.py        # 转换API
│   │   ├── upload.py         # 上传API（含QC结果、视频流）
│   │   └── merge.py          # 合并API
│   └── services/             # 业务服务
│       ├── database.py       # SQLite数据库
│       ├── download_service.py
│       ├── convert_service.py
│       ├── upload_service.py
│       └── merge_service.py  # 合并服务
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── views/            # 页面组件
│   │   │   └── Pipeline.vue  # Pipeline流水线页面
│   │   ├── components/       # 通用组件
│   │   │   └── QCInspector.vue  # QC质检组件
│   │   ├── api/              # API封装
│   │   ├── stores/           # Pinia状态
│   │   └── router/           # 路由配置
│   ├── package.json
│   └── vite.config.ts
├── pixi.toml                 # Python依赖配置
├── README.md                 # 本文件
├── USER_GUIDE.md             # 用户指南
└── PROGRESS.md               # 开发进度
```

## 数据格式

### 输入格式（HDF5）

支持的HDF5文件结构：

```
episode_XXXX.h5
├── images/
│   ├── cam_env/frames_jpeg      # 环境相机（JPEG压缩）
│   ├── cam_left/frames_jpeg     # 左手相机（JPEG压缩）
│   └── cam_right/frames_jpeg    # 右手相机（JPEG压缩）
├── joints/
│   ├── left_master/             # 左臂主控关节
│   │   ├── joint1_pos ~ joint6_pos
│   │   ├── eef_gripper_joint_pos
│   │   ├── timestamp_sec
│   │   └── timestamp_nanosec
│   ├── right_master/            # 右臂主控关节
│   ├── left_slave/              # 左臂从控关节
│   └── right_slave/             # 右臂从控关节
└── metadata
```

**特点：**
- 双臂机器人：左右各6关节 + 1夹爪
- State/Action维度：14（6+1+6+1）
- 图像：JPEG压缩存储，~26fps
- 关节数据：250Hz采样

### 输出格式（LeRobot v2.1）

转换后的标准LeRobot v2.1格式：

```
episode_XXXX/
├── meta/
│   ├── info.json           # 数据集信息
│   └── tasks.json          # 任务描述
├── data/
│   └── chunk-000/
│       └── episode_000000.parquet  # 状态/动作数据
└── videos/
    └── chunk-000/
        └── episode_000000/
            ├── cam_env.mp4
            ├── cam_left.mp4
            └── cam_right.mp4
```

## 数据流程

```
BOS存储 (百度对象存储)
  ↓ (pixi run download - mc mirror下载)
本地HDF5目录
  ↓ (pixi run convert - convert.py转换)
多个独立LeRobot Episode
  ├── episode_0001/
  ├── episode_0002/
  └── ...
  ↓ (pixi run merge - 合并为单个数据集)
单个LeRobot v2.1数据集
  ├── meta/               # 元数据
  ├── data/chunk-000/     # Parquet数据
  └── videos/chunk-000/   # MP4视频
  ↓ (pixi run upload - mc mirror上传)
BOS存储 (LeRobot格式)
```

## 测试结果

在测试环境下的性能表现：

| 操作 | 文件数 | 数据量 | 耗时 | 速度 |
|------|--------|--------|------|------|
| 下载 | 18个 | 246MB | 16秒 | 15.22 MB/s |
| 转换 | 232个 | 16GB | 198秒 | 0.9秒/文件 |
| 合并 | 232个 episodes | 644MB | <1分钟 | - |
| 上传 | 1856个文件 | 640MB | ~10秒 | 220 files/s |

## 配置说明

### mc工具配置

确保mc已配置BOS别名：

```bash
# 检查mc版本
/home/maozan/mc --version

# 配置BOS别名（如尚未配置）
mc alias set bos <endpoint> <access-key> <secret-key>

# 验证连接
mc ls bos/
```

## 常见问题

### Q: mc命令未找到？
A: 确认mc已安装并路径正确。使用 `--mc-path` 参数指定路径。

### Q: pixi install失败？
A: 检查网络连接，确保conda-forge镜像可访问。

### Q: 转换失败？
A: 常见原因：
1. HDF5文件格式不匹配 - 确保文件包含正确的数据结构
2. 时间戳数据异常 - 检查joints数据中的timestamp_sec/timestamp_nanosec
3. 图像解码失败 - 检查frames_jpeg是否为有效JPEG数据

### Q: 如何查看详细日志？
A: 转换脚本会在控制台输出详细进度，包括每帧的时间对齐信息。

## 开发路线

- [x] **v0.1.0** - CLI工具版本（download + convert）
- [x] **v0.2.0** - 完整数据处理流水线
  - 后端API服务 + Web管理界面
  - 完整CLI工具链：download + convert + **merge** + upload
  - 数据集合并功能：支持多episode合并、维度自适应对齐
- [x] **v0.2.1** - Pipeline QC质检 + Merge 功能（当前）
  - Pipeline 页面：一站式流水线操作
  - QC 质检组件：三相机视频预览、通过/不通过标记
  - QC 结果持久化：自动保存和恢复进度
  - Merge 集成：仅合并通过质检的 episode
  - 操作确认对话框：防止误操作
- [ ] **v0.3.0** - 功能增强、日志监控

## 许可证

MIT License

## 开发进度

查看 [PROGRESS.md](./PROGRESS.md) 了解当前开发状态。
查看 [USER_GUIDE.md](./USER_GUIDE.md) 了解详细使用指南。

---

**版本**: v0.2.1
**最后更新**: 2026-01-07
