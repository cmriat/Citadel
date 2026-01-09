# Citadel Release 环境安装指南

本文档详细说明如何在新环境中部署 Citadel Release 项目。

## 目录

1. [系统要求](#系统要求)
2. [安装 pixi](#安装-pixi)
3. [安装 mc (MinIO Client)](#安装-mc-minio-client)
4. [安装 Node.js 和 npm](#安装-nodejs-和-npm)
5. [项目安装](#项目安装)
6. [环境变量配置](#环境变量配置)
7. [验证安装](#验证安装)
8. [常见问题](#常见问题)

---

## 系统要求

- **操作系统**: Linux (Ubuntu 20.04+ 推荐)
- **Python**: 3.10+ (由 pixi 管理)
- **Node.js**: 18+ (用于前端开发)
- **磁盘空间**: 至少 10GB 可用空间
- **网络**: 能够访问 BOS 存储服务

---

## 安装 pixi

[pixi](https://pixi.sh/) 是一个现代化的 Python 包管理工具，用于管理项目依赖。

### 方法一：官方安装脚本（推荐）

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

安装完成后，重新加载 shell 配置：

```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

### 方法二：手动安装

```bash
# 下载最新版本
curl -fsSL https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-unknown-linux-musl -o ~/bin/pixi
chmod +x ~/bin/pixi

# 添加到 PATH（如果 ~/bin 不在 PATH 中）
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 验证安装

```bash
pixi --version
# 输出示例: pixi 0.x.x
```

---

## 安装 mc (MinIO Client)

[mc](https://min.io/docs/minio/linux/reference/minio-mc.html) 是 MinIO 官方客户端，用于与 BOS 等 S3 兼容存储进行交互。

### 方法一：下载预编译二进制（推荐）

```bash
# 创建 bin 目录（如果不存在）
mkdir -p ~/bin

# 下载 mc
curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o ~/bin/mc
chmod +x ~/bin/mc

# 添加到 PATH（如果 ~/bin 不在 PATH 中）
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 方法二：使用包管理器

```bash
# Ubuntu/Debian
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/
```

### 验证安装

```bash
mc --version
# 输出示例: mc version RELEASE.2025-xx-xx
```

### 配置 BOS 别名

配置 mc 以访问百度对象存储（BOS）：

```bash
# 添加 BOS 别名
mc alias set bos <endpoint> <access-key> <secret-key>

# 示例（请替换为实际值）：
# mc alias set bos https://bj.bcebos.com YOUR_ACCESS_KEY YOUR_SECRET_KEY
```

**参数说明**：
- `<endpoint>`: BOS 服务端点（如 `https://bj.bcebos.com`）
- `<access-key>`: 您的 BOS Access Key
- `<secret-key>`: 您的 BOS Secret Key

### 验证 BOS 连接

```bash
mc ls bos/
# 应该能列出您有权限访问的 bucket
```

---

## 安装 Node.js 和 npm

Node.js 和 npm 用于前端开发。如果只使用 CLI 工具，可以跳过此步骤。

### 方法一：使用 nvm（推荐）

```bash
# 安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载 shell
source ~/.bashrc

# 安装 Node.js 18 LTS
nvm install 18
nvm use 18

# 设置为默认版本
nvm alias default 18
```

### 方法二：使用包管理器

```bash
# Ubuntu/Debian - 添加 NodeSource 仓库
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 验证安装

```bash
node --version
# 输出示例: v18.x.x

npm --version
# 输出示例: 9.x.x
```

---

## 项目安装

### 1. 克隆项目

```bash
git clone <repository-url>
cd Citadel
```

### 2. 安装后端依赖

```bash
pixi install
```

这将自动安装所有 Python 依赖，包括：
- FastAPI
- h5py
- pandas
- pyarrow
- pillow
- ffmpeg-python
- 其他依赖...

### 3. 安装前端依赖（可选）

如果需要使用 Web 管理界面：

```bash
cd frontend
npm install
cd ..
```

### 4. 配置环境变量

```bash
# 复制后端环境变量模板
cp .env.example .env

# 复制前端环境变量模板
cp frontend/.env.example frontend/.env
```

根据您的环境修改 `.env` 文件，详见下一节。

---

## 环境变量配置

### 后端配置 (.env)

编辑项目根目录下的 `.env` 文件：

```bash
# =============================================================================
# Citadel Release 配置文件
# =============================================================================

# -----------------------------------------------------------------------------
# API 服务器配置
# -----------------------------------------------------------------------------
API_HOST=0.0.0.0
API_PORT=8000

# -----------------------------------------------------------------------------
# mc 工具配置
# -----------------------------------------------------------------------------
# mc 可执行文件路径（留空则自动检测）
# MC_PATH=/usr/local/bin/mc

# BOS 别名（mc alias 配置的名称）
BOS_ALIAS=bos

# BOS 连接测试路径
BOS_TEST_PATH=srgdata/

# -----------------------------------------------------------------------------
# 默认参数
# -----------------------------------------------------------------------------
DEFAULT_CONCURRENCY=10
DEFAULT_FPS=25
DEFAULT_ROBOT_TYPE=airbot_play
DEFAULT_TASK_NAME=Fold the laundry
DEFAULT_PARALLEL_JOBS=4

# -----------------------------------------------------------------------------
# 数据维度配置
# -----------------------------------------------------------------------------
STATE_MAX_DIM=14
ACTION_MAX_DIM=14

# -----------------------------------------------------------------------------
# 超时配置（秒）
# -----------------------------------------------------------------------------
TIMEOUT_MC_CHECK=30
TIMEOUT_CONVERT_FILE=300

# -----------------------------------------------------------------------------
# 存储配置
# -----------------------------------------------------------------------------
DB_PATH=backend/data/tasks.db

# -----------------------------------------------------------------------------
# CORS 配置
# -----------------------------------------------------------------------------
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 前端配置 (frontend/.env)

编辑 `frontend/.env` 文件：

```bash
# API 后端端口
VITE_API_PORT=8000

# 前端开发服务器端口
VITE_DEV_PORT=5173

# 默认并发数
VITE_DEFAULT_CONCURRENCY=10

# API 请求超时（毫秒）
VITE_API_TIMEOUT=30000
```

### 配置优先级

系统按以下顺序读取配置：

1. 环境变量 > `.env` 文件 > 代码默认值

mc 路径查找优先级：
1. `MC_PATH` 环境变量
2. `~/bin/mc`
3. 系统 PATH 中的 `mc`

---

## 验证安装

### 1. 验证 CLI 工具

```bash
# 查看帮助信息
pixi run download --help
pixi run convert --help
pixi run merge --help
pixi run upload --help
```

### 2. 验证配置模块

```bash
pixi run python -c "
from backend.config import settings
print('API_PORT:', settings.API_PORT)
print('DEFAULT_FPS:', settings.DEFAULT_FPS)
print('MC_PATH:', settings.get_mc_path())
"
```

### 3. 验证 BOS 连接

```bash
# 使用 CLI 工具测试
mc ls bos/srgdata/
```

### 4. 启动服务（可选）

```bash
# 终端1：启动后端
pixi run dev

# 终端2：启动前端
cd frontend && npm run dev
```

访问 http://localhost:5173 验证 Web 界面。

---

## 常见问题

### Q1: pixi 命令未找到

**解决方案**：
1. 确认安装脚本已执行成功
2. 重新加载 shell 配置：`source ~/.bashrc`
3. 检查 PATH：`echo $PATH | grep pixi`

### Q2: mc 命令未找到

**解决方案**：
1. 确认 mc 已下载到正确位置
2. 检查文件权限：`ls -la ~/bin/mc`
3. 在 `.env` 中指定完整路径：`MC_PATH=/path/to/mc`

### Q3: BOS 连接失败

**解决方案**：
1. 验证 mc 别名配置：`mc alias list`
2. 检查网络连接
3. 确认 Access Key 和 Secret Key 正确
4. 检查 BOS 端点是否正确

### Q4: pixi install 失败

**解决方案**：
1. 检查网络连接（需要访问 conda-forge）
2. 清除缓存重试：`pixi clean && pixi install`
3. 检查磁盘空间

### Q5: npm install 失败

**解决方案**：
1. 检查 Node.js 版本：`node --version`（需要 18+）
2. 清除 npm 缓存：`npm cache clean --force`
3. 删除 node_modules 重试：`rm -rf node_modules && npm install`

### Q6: 前端无法连接后端 API

**解决方案**：
1. 确认后端服务已启动：`pixi run dev`
2. 检查端口配置一致性：
   - 后端 `.env` 中的 `API_PORT`
   - 前端 `.env` 中的 `VITE_API_PORT`
3. 检查 CORS 配置

### Q7: 转换超时

**解决方案**：
1. 增加超时时间：在 `.env` 中设置 `TIMEOUT_CONVERT_FILE=600`
2. 减少并发数：`--parallel-jobs 2`
3. 检查系统资源使用情况

---

## 快速检查清单

安装完成后，请确认以下项目：

- [ ] `pixi --version` 正常输出
- [ ] `mc --version` 正常输出
- [ ] `node --version` 输出 v18.x.x 或更高（如需前端）
- [ ] `mc ls bos/` 能列出存储内容
- [ ] `.env` 文件已配置
- [ ] `pixi run download --help` 正常输出
- [ ] `pixi run dev` 能启动后端服务（如需 Web 界面）

---

**文档版本**: v0.2.2
**最后更新**: 2026-01-09
