# 配置文件结构说明

## 新的配置文件组织

```
config/
├── storage.yaml              # 统一的存储配置（Redis + BOS）
├── strategies/               # 策略配置目录
│   ├── chunking.yaml        # Action Chunking 策略
│   ├── nearest.yaml         # Nearest Neighbor 策略
│   └── window.yaml          # Time Window 策略
└── (旧配置文件保留以兼容)
```

## 使用方式

### 1. 使用新的统一配置

```bash
# BOS Scanner 使用 storage.yaml
python scripts/bos_scanner.py --config config/storage.yaml

# Redis Worker 使用 storage.yaml
python scripts/redis_worker.py --config config/storage.yaml

# 本地转换使用策略配置
python scripts/convert.py --config config/strategies/chunking.yaml
```

### 2. 配置文件说明

#### storage.yaml
统一管理 Redis 和 BOS 相关配置：
- Redis 连接和队列配置
- BOS 连接和路径配置
- 扫描、下载、上传配置
- 数据源和输出配置

#### strategies/*.yaml
各种对齐策略的具体配置：
- 机器人配置（arms, joints）
- 相机配置（fps, role）
- 输入输出路径
- 对齐参数
- 过滤和视频编码配置

## 配置优势

1. **避免重复**：Redis 配置只在 storage.yaml 中定义一次
2. **清晰分离**：存储配置 vs 策略配置分离
3. **易于切换**：快速切换不同的对齐策略
4. **向后兼容**：旧配置文件保留，现有脚本仍可使用

## 迁移指南

### 从旧配置迁移

旧配置：
```bash
# 使用 bos_config.yaml 和 redis_config.yaml
python scripts/bos_scanner.py --config config/bos_config.yaml
```

新配置：
```bash
# 使用统一的 storage.yaml
python scripts/bos_scanner.py --config config/storage.yaml
```

### 策略配置迁移

旧配置：
```bash
python scripts/convert.py --config config/dual_arm_chunking.yaml
```

新配置：
```bash
python scripts/convert.py --config config/strategies/chunking.yaml
```
