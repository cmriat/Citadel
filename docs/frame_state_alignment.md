# Frame-State 时间对齐分析

## 概述

本文档介绍如何分析 LeRobot 数据集中视频帧（Frame）与关节数据（State/Action）的时间对齐情况。

**相关脚本**: [`scripts/analyze_frame_state_alignment.py`](../scripts/analyze_frame_state_alignment.py)

**模块结构**: [`scripts/alignment/`](../scripts/alignment/)
- `config.py` - 配置管理（ROI区域、颜色阈值、夹爪维度）
- `data_loader.py` - 数据集加载（支持 v2.0/v3.0 格式）
- `video_tracker.py` - 视频追踪器（ROI/黑色区域/颜色检测）
- `signal_processing.py` - 信号处理与去噪
- `visualization.py` - 可视化生成
- `analyzer.py` - 核心分析逻辑
- `cli.py` - 命令行接口

---

## 背景

在机器人数据采集系统中，视频帧和关节数据的采集可能存在时间偏移：

- **关节传感器**：采样率通常较高（如 250Hz）
- **相机**：采样率较低（如 25-30Hz）
- **对齐方式**：两者通过时间戳对齐到同一帧

由于硬件延迟、时间戳精度等因素，实际对齐可能存在偏差。

---

## 偏移检测原理

### 核心思想

当夹爪开合时，会同时产生两个信号：

1. **State 信号**：关节传感器记录的夹爪位置值变化
2. **Video 信号**：相机画面中夹爪的视觉变化

理论上，这两个信号应该**同时发生**。通过比较它们的峰值位置，可以估算时间偏移。

### 算法流程

```
时间轴:  ----[State变化]----[Video变化]---->
                 ↑              ↑
              frame=100     frame=102

         偏移 = 102 - 100 = +2 帧（Video滞后）
```

#### 第1步：检测 State 变化事件

**代码位置**: `scripts/alignment/signal_processing.py:SignalProcessor.find_state_events()`

```python
def find_state_events(self, state: np.ndarray, gripper_dim: int = LEFT_GRIPPER_DIM,
                      threshold: float = 0.01) -> np.ndarray:
    """
    找出夹爪 state 值发生显著变化的帧。

    参数:
        state: State 数组 [N, 14]
        gripper_dim: 夹爪维度索引 (左=6, 右=13)
        threshold: 最小变化阈值 (默认 0.01)
    """
    gripper_state = state[:, gripper_dim]
    state_diff = np.abs(np.diff(gripper_state))

    # 找出差异 > threshold 的帧
    significant_frames = np.where(state_diff > threshold)[0]
    return significant_frames
```

**原理说明**:
- 夹爪 state 值域：小值(~0) = 闭合，大值(~0.07) = 张开
- 当夹爪开合时，相邻帧的 state 差异会超过阈值
- 例如：frame=100 时 state 从 0.01 → 0.05（张开动作）

#### 第2步：计算 Video 帧差

**代码位置**: `scripts/alignment/video_tracker.py`

本工具支持三种视频追踪模式，通过策略模式实现：

##### ROI 模式（默认）

```python
class ROITracker(BaseTracker):
    """基于感兴趣区域的帧差追踪"""
    def compute_diffs(self, video_path: Path, frame_range: tuple) -> np.ndarray:
        # 提取 ROI 区域（腕部相机夹爪位置）
        # ROI 区域: y: 60%-95%, x: 25%-75%
        roi = img[y_start:y_end, x_start:x_end]
        # 计算相邻帧的灰度像素差异
        diff = np.abs(roi - prev_roi).mean()
```

##### 黑色区域检测模式（ALOHA 优化）⭐ 新增

针对 ALOHA 等黑色夹爪机器人优化，追踪黑色区域的变化：

```python
class BlackRegionTracker(BaseTracker):
    """基于黑色区域检测的追踪（适用于 ALOHA 等黑色夹爪）"""
    def compute_diffs(self, video_path: Path, frame_range: tuple) -> np.ndarray:
        # 黑色检测条件: 所有通道值 < 80
        black_mask = (gray < 80)
        diff = np.abs(black_mask - prev_mask).mean()
```

**性能对比**：黑色区域检测相比 ROI 模式提升 21% 相关性（0.460 vs 0.379）。

##### 颜色检测模式（橙色夹爪）

```python
class ColorTracker(BaseTracker):
    """基于颜色检测的追踪（适用于橙色夹爪）"""
    def compute_diffs(self, video_path: Path, frame_range: tuple) -> np.ndarray:
        # 橙色检测条件 (RGB):
        # R > 120, G ∈ [40, 180], B < 120, R > G > B
        orange_mask = (r > 120) & (g > 40) & (g < 180) & (b < 120) & (r > g) & (g > b)
        diff = np.abs(orange_mask - prev_mask).mean()
```

**为什么聚焦夹爪区域？**

如果用整张图像计算帧差，会受到干扰：
- 手臂移动
- 背景变化
- 光线波动

聚焦夹爪区域可以：
- 只捕捉夹爪的开合动作
- 与 State 中的夹爪值变化直接对应
- 提高偏移估计的准确性

#### 第3步：匹配峰值计算偏移

**代码位置**: `scripts/alignment/analyzer.py:AlignmentAnalyzer._compute_alignment()`

```python
def _compute_alignment(self, state_diff: np.ndarray, video_diff: np.ndarray,
                       significant_frames: np.ndarray,
                       search_window: int = 5) -> list[AlignmentResult]:
    """
    对于每个 State 变化事件，在其附近 ±5 帧窗口内搜索 Video 帧差峰值。
    """
    for state_peak in significant_frames:
        # 搜索窗口
        start = max(0, state_peak - search_window)
        end = min(len(video_diff), state_peak + search_window + 1)

        # 找到 video_diff 最大值的位置
        local_video = video_diff[start:end]
        video_peak = start + np.argmax(local_video)

        # 计算偏移
        offset = video_peak - state_peak
```

#### 第4步（可选）：状态引导去噪 ⭐ 新增

**代码位置**: `scripts/alignment/signal_processing.py:SignalProcessor.denoise()`

当 Video 信号噪声较大时，可使用 State 波形指导去噪，提高检测准确性：

```python
class SignalProcessor:
    def denoise(self, video_diff: np.ndarray, state_diff: np.ndarray,
                method: str = "state_guided", window_size: int = None) -> np.ndarray:
        """
        使用 State 波形指导 Video 信号去噪。

        方法:
        - state_guided: 在 State 事件周围使用高斯加权窗口
        - weighted: 使用 State 包络加权
        - adaptive: 自适应阈值
        """
        # state_guided 方法：在 State 峰值周围创建高斯权重
        for event_frame in state_events:
            weights[start:end] = np.maximum(
                weights[start:end],
                scipy.signal.windows.gaussian(end - start, std=window_size / 4)
            )
        return video_diff * weights
```

**性能提升**：状态引导去噪可将相关性提升 34.1%（0.617 vs 0.460）。

**图示说明**:

```
Frame:     95   96   97   98   99  100  101  102  103  104  105
           |    |    |    |    |    |    |    |    |    |    |
State:     ─────────────────────█████────────────────────────
                                 ↑
                           State变化峰值
                           (frame=100)

Video:     ────────────────────────────█████─────────────────
                                        ↑
                                  Video变化峰值
                                  (frame=102)

偏移 = 102 - 100 = +2 帧
含义: Video 比 State 滞后 2 帧 (80ms @25fps)
```

---

## 偏移值含义

| 偏移值 | 含义 | 物理解释 |
|--------|------|----------|
| **> 0** | Video 滞后 | 传感器先记录到动作，相机后捕捉到画面 |
| **= 0** | 完美对齐 | 传感器和相机同步 |
| **< 0** | Video 提前 | 相机先捕捉到画面，传感器后记录（较少见） |

### 典型结果解读

| 偏移范围 | 评估 | 建议 |
|----------|------|------|
| ±1 帧 (0-40ms) | ✅ 优秀 | 可直接用于训练 |
| +1~2 帧 (40-80ms) | ⚠️ 正常 | 轻微延迟，通常可接受 |
| > 3 帧 (>120ms) | ❌ 需关注 | 可能需要时间补偿 |

---

## 使用方法

### 基本用法

```bash
# 分析单个 episode
python scripts/analyze_frame_state_alignment.py /path/to/dataset

# 指定 episode
python scripts/analyze_frame_state_alignment.py /path/to/dataset --episode 5

# 分析所有 episodes
python scripts/analyze_frame_state_alignment.py /path/to/dataset --all-episodes
```

### 检测模式选择

```bash
# ROI 模式（默认，速度快）
python scripts/analyze_frame_state_alignment.py /path/to/dataset

# 黑色区域检测模式（ALOHA 等黑色夹爪机器人优化）⭐ 推荐
python scripts/analyze_frame_state_alignment.py /path/to/dataset --black-detection

# 颜色检测模式（橙色夹爪）
python scripts/analyze_frame_state_alignment.py /path/to/dataset --color-detection
```

### 启用状态引导去噪 ⭐ 新增

```bash
# 启用去噪（默认使用 state_guided 方法）
python scripts/analyze_frame_state_alignment.py /path/to/dataset --black-detection --denoise

# 指定去噪方法
python scripts/analyze_frame_state_alignment.py /path/to/dataset --black-detection --denoise --denoise-method weighted
```

### 指定相机和夹爪

```bash
# 分析右腕相机 + 右夹爪
python scripts/analyze_frame_state_alignment.py /path/to/dataset \
    --camera cam_right_wrist \
    --gripper right
```

### 完整示例

```bash
# ALOHA 机器人完整分析（黑色检测 + 去噪 + 所有 episodes）
python scripts/analyze_frame_state_alignment.py /path/to/aloha \
    --black-detection \
    --denoise \
    --all-episodes \
    -o output/alignment_results/
```

### 完整参数列表

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `dataset_dir` | LeRobot 数据集路径 | (必填) |
| `--episode, -e` | Episode 索引 | 0 |
| `--output, -o` | 输出目录 | dataset_dir/alignment_analysis |
| `--all-episodes, -a` | 分析所有 episodes | False |
| `--camera, -c` | 相机名称 | cam_left_wrist |
| `--gripper, -g` | 夹爪 (left/right) | left |
| `--black-detection` | 黑色区域检测模式（ALOHA 优化）⭐ | False |
| `--color-detection` | 颜色检测模式（橙色夹爪） | False |
| `--denoise` | 启用状态引导去噪 ⭐ | False |
| `--denoise-method` | 去噪方法 (state_guided/weighted/adaptive) | state_guided |

---

## 输出文件

运行脚本后会生成以下文件：

```
output_dir/
├── episode_000000_alignment.png   # 可视化图表
├── episode_000000_report.json     # 详细 JSON 报告
└── summary_report.json            # 汇总报告 (--all-episodes)
```

### 可视化图表说明

生成的 PNG 图表包含三个子图：

1. **Full Timeline**: 整个 episode 的 State diff 和 Video diff 对比
2. **Zoomed View**: 放大显示某个活跃区域的细节
3. **Offset Distribution**: 偏移值的直方图分布

### JSON 报告字段

```json
{
  "dataset_dir": "/path/to/dataset",
  "episode": 0,
  "total_frames": 1206,
  "total_events": 32,
  "mean_offset_frames": 0.41,
  "mean_offset_ms": 16.2,
  "median_offset_frames": 0.0,
  "std_offset_frames": 1.0,
  "min_offset": -1,
  "max_offset": 2,
  "conclusion": "✓ Frame and State/Action are well synchronized",
  "events": [...]
}
```

---

## 实际案例

### 数据集分析汇总

| 数据集 | 平均偏移(帧) | 平均偏移(ms) | 检测事件数 | 评估 |
|--------|--------------|--------------|------------|------|
| 0115_qz2_plant/merged | +0.41 | 16ms | 32 | ✅ 优秀 |
| 1226_qz2/merged | +1.23 | 49ms | 26 | ⚠️ 正常 |
| 1226_qz2/merged_nearest | +1.93 | 77ms | 28 | ⚠️ 需关注 |
| aloha_mobile_cabinet | +1.55 | 31ms | 18 | ⚠️ 正常 |

### 案例 1: 对齐良好的数据集

```
数据集: 0115_qz2_plant/merged
检测模式: 黑色区域检测 + 状态引导去噪
平均偏移: +0.4 帧 (16ms)
中位数: 0 帧
偏移分布: {-1: 7, 0: 10, 1: 10, 2: 5}
结论: ✅ 优秀，可直接用于训练
```

### 案例 2: 存在轻微滞后的数据集

```
数据集: 1226_qz2/merged_nearest
检测模式: 黑色区域检测 + 状态引导去噪
平均偏移: +1.93 帧 (77ms)
中位数: 2 帧
偏移分布: {0: 3, 1: 8, 2: 10, 3: 5, 4: 2}
结论: ⚠️ Video 滞后约 2 帧，训练时可能需要考虑
```

### 案例 3: ALOHA 机器人数据集

```
数据集: aloha_mobile_cabinet
检测模式: 黑色区域检测（针对黑色夹爪优化）
平均偏移: +1.55 帧 (31ms @50fps)
中位数: 2 帧
结论: ⚠️ 正常，在可接受范围内
```

---

## 相关文件

| 文件 | 说明 |
|------|------|
| [`scripts/analyze_frame_state_alignment.py`](../scripts/analyze_frame_state_alignment.py) | 入口脚本 |
| [`scripts/alignment/`](../scripts/alignment/) | 对齐分析模块目录 |
| [`scripts/alignment/config.py`](../scripts/alignment/config.py) | 配置管理（ROI区域、颜色阈值、夹爪维度） |
| [`scripts/alignment/data_loader.py`](../scripts/alignment/data_loader.py) | 数据集加载（v2.0/v3.0 格式） |
| [`scripts/alignment/video_tracker.py`](../scripts/alignment/video_tracker.py) | 视频追踪器（ROI/黑色区域/颜色检测） |
| [`scripts/alignment/signal_processing.py`](../scripts/alignment/signal_processing.py) | 信号处理与状态引导去噪 |
| [`scripts/alignment/visualization.py`](../scripts/alignment/visualization.py) | 可视化图表生成 |
| [`scripts/alignment/analyzer.py`](../scripts/alignment/analyzer.py) | 核心分析逻辑 |
| [`scripts/alignment/cli.py`](../scripts/alignment/cli.py) | 命令行接口 |
| [`docs/alignment_analysis_summary.md`](./alignment_analysis_summary.md) | 数据集分析汇总报告 |
