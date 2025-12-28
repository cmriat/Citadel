# Citadel Release

🚀 BOS下载和HDF5转换管理系统 - 支持Web界面和CLI工具

## 项目简介

Citadel Release 是一个完整的数据管理系统，用于从百度对象存储(BOS)下载机器人数据（HDF5格式），并批量转换为LeRobot v2.1标准格式。

### 核心功能

- ✅ **BOS数据下载**: 使用mc (MinIO Client)高效下载，支持断点续传
- ✅ **HDF5格式转换**: 批量转换为LeRobot v2.1格式（包含meta、data、videos）
- ✅ **Web管理界面**: 可视化任务管理、实时进度监控、日志查看
- ✅ **命令行工具**: 独立CLI工具，无需启动Web服务器，适合自动化脚本

## 快速开始

### 前置要求

1. **Linux环境** (测试于 Ubuntu 20.04+)
2. **mc (MinIO Client)** - 已安装于 `/home/maozan/mc`
3. **pixi** - Python环境管理工具

### 安装

```bash
# 进入项目目录
cd /data/maozan/code/Citadel_release

# 安装依赖
pixi install

# 查看帮助
pixi run help
```

## 使用方式

系统支持三种使用模式：

### 模式1: 命令行工具 (CLI)

**推荐用于：自动化脚本、快速操作**

```bash
# 下载HDF5文件
pixi run download \
  --bos-path "srgdata/robot/raw_data/.../fold_laundry/" \
  --local-path "/home/maozan/data/fold_laundry/raw_hdf5/" \
  --concurrency 10

# 批量转换HDF5文件
pixi run convert \
  --input-dir "/home/maozan/data/fold_laundry/raw_hdf5/" \
  --output-dir "/home/maozan/data/fold_laundry/lerobot_v21/" \
  --robot-type "limx Tron2" \
  --fps 30 \
  --parallel-jobs 4

# 查看命令行帮助
pixi run download --help
pixi run convert --help
```

### 模式2: Web界面

**推荐用于：可视化监控、任务管理**

```bash
# 启动开发服务器
pixi run dev

# 或启动生产服务器
pixi run start
```

然后访问 http://localhost:8000

**功能包括：**
- 📥 下载任务管理 - 配置BOS路径，启动/取消下载
- 🔄 转换任务管理 - 选择HDF5文件，批量转换
- 📊 实时监控 - 查看任务进度、系统状态
- 📁 数据浏览 - 浏览下载和转换后的数据

### 模式3: API调用

**推荐用于：系统集成**

```bash
# 启动API服务器
pixi run start

# 调用下载API
curl -X POST http://localhost:8000/api/download/start \
  -H "Content-Type: application/json" \
  -d '{"bos_path": "...", "local_path": "...", "concurrency": 10}'

# 查看任务状态
curl http://localhost:8000/api/download/{task_id}/status
```

## 项目结构

```
Citadel_release/
├── backend/          # FastAPI后端服务
├── frontend/         # Vue3前端界面
├── cli/              # 命令行工具（独立使用）
├── scripts/          # 核心脚本（mc下载、HDF5转换）
├── data/             # 运行时数据（任务状态、日志）
├── pixi.toml         # 依赖配置
├── README.md         # 本文件
└── PROGRESS.md       # 开发进度
```

## 数据流程

```
BOS存储
  ↓ (mc mirror下载)
本地HDF5目录 (/home/maozan/data/fold_laundry/raw_hdf5/)
  ↓ (convert.py转换)
LeRobot v2.1格式 (/home/maozan/data/fold_laundry/lerobot_v21/)
  ├── meta/               # 元数据文件
  ├── data/chunk-000/     # Parquet数据文件
  └── videos/chunk-000/   # MP4视频文件
```

## 配置说明

### 数据路径配置

默认数据路径：
- **BOS源**: `bos/srgdata/robot/raw_data/upload_test/online_test_hdf5/fold_laundry/`
- **本地HDF5**: `/home/maozan/data/fold_laundry/raw_hdf5/`
- **LeRobot输出**: `/home/maozan/data/fold_laundry/lerobot_v21/`

可通过命令行参数或Web界面修改。

### mc工具配置

默认mc路径: `/home/maozan/mc`

如需修改，使用 `--mc-path` 参数。

## 开发

### 运行测试

```bash
pixi run test
```

### 构建前端

```bash
pixi run build-frontend
```

## 常见问题

### Q: mc命令未找到？
A: 确认mc已安装并路径正确。默认路径为 `/home/maozan/mc`。

### Q: pixi install失败？
A: 检查网络连接，确保conda-forge镜像可访问。

### Q: 转换失败？
A: 检查HDF5文件格式是否正确，确保包含必需的数据集（observations/images_color等）。

## 许可证

MIT License

## 开发进度

查看 [PROGRESS.md](./PROGRESS.md) 了解当前开发状态。

---

**开发者**: Citadel Team
**版本**: v0.1.0
**最后更新**: 2025-12-26
