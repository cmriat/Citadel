"""
三相机视频逐帧对比可视化工具。

将 convert 后的三个相机 MP4 并排拼接为一个合成视频，每帧左上角标注帧号，
输出单个 MP4 文件，用任意播放器逐帧查看即可验证时间对齐质量。

Usage:
    pixi run python scripts/visualize_video_sync.py /path/to/lerobot --episode 141
    pixi run python scripts/visualize_video_sync.py /path/to/lerobot --episode 141 --output /tmp/sync.mp4
    pixi run python scripts/visualize_video_sync.py /path/to/lerobot --episode 141 --fps 25

逐帧查看提示 (播放器快捷键):
    mpv:   .  下一帧    ,  上一帧    空格 播放/暂停
    VLC:   E  下一帧    Shift+← 回退    空格 播放/暂停
    ffplay: S  下一帧    左右方向键 跳跃
"""

import argparse
from pathlib import Path
from typing import List

import av
import numpy as np


# 相机名称映射
CAMERA_KEYS = [
    "observation.images.cam_env",
    "observation.images.cam_left_wrist",
    "observation.images.cam_right_wrist",
]
CAMERA_LABELS = ["cam_env", "cam_left_wrist", "cam_right_wrist"]

# 标签栏高度 (像素)
LABEL_BAR_HEIGHT = 28


def decode_video(video_path: Path) -> np.ndarray:
    """将 MP4 解码为 [N, H, W, 3] uint8 数组。"""
    container = av.open(str(video_path))
    stream = container.streams.video[0]

    frames = []
    for frame in container.decode(stream):
        img = frame.to_ndarray(format='rgb24')
        frames.append(img)

    container.close()
    return np.stack(frames, axis=0)


def _resolve_episode_dir(output_dir: Path, episode_index: int) -> Path:
    """解析 episode 的实际目录。

    支持两种目录结构：
      结构A (单 episode 一个目录):  output_dir/episode_NNNN/videos/chunk-000/...
      结构B (合并输出):             output_dir/videos/chunk-000/.../episode_NNNNNN.mp4
    """
    # 结构A: output_dir 下有 episode_NNNN 子目录
    ep_subdir = output_dir / f"episode_{episode_index:04d}"
    if not ep_subdir.exists():
        ep_subdir = output_dir / f"episode_{episode_index:06d}"
    if ep_subdir.exists() and (ep_subdir / "videos").exists():
        return ep_subdir

    # 结构B: output_dir 本身就是 LeRobot 目录
    if (output_dir / "videos").exists():
        return output_dir

    raise FileNotFoundError(
        f"无法定位 episode {episode_index} 的视频目录。\n"
        f"  尝试过: {output_dir}/episode_{episode_index:04d}/videos\n"
        f"  尝试过: {output_dir}/videos"
    )


def find_episode_videos(output_dir: Path, episode_index: int = 0) -> List[Path]:
    """查找指定 episode 的三个相机视频路径。"""
    ep_dir = _resolve_episode_dir(output_dir, episode_index)

    paths = []
    for cam_key in CAMERA_KEYS:
        cam_dir = ep_dir / "videos" / "chunk-000" / cam_key
        if not cam_dir.exists():
            raise FileNotFoundError(f"相机目录不存在: {cam_dir}")
        mp4s = sorted(cam_dir.glob("episode_*.mp4"))
        if not mp4s:
            raise FileNotFoundError(f"视频文件不存在: {cam_dir}/episode_*.mp4")
        paths.append(mp4s[0])
    return paths


def list_available_episodes(output_dir: Path) -> List[int]:
    """列出所有可用的 episode 索引。"""
    # 结构A: output_dir 下有 episode_NNNN 子目录
    ep_dirs = sorted(output_dir.glob("episode_*"))
    if ep_dirs and (ep_dirs[0] / "videos").exists():
        episodes = []
        for d in ep_dirs:
            if d.is_dir() and (d / "videos").exists():
                idx_str = d.name.replace("episode_", "")
                try:
                    episodes.append(int(idx_str))
                except ValueError:
                    pass
        if episodes:
            return sorted(episodes)

    # 结构B: 合并输出
    video_dir = output_dir / "videos" / "chunk-000" / CAMERA_KEYS[0]
    if not video_dir.exists():
        return []
    episodes = []
    for mp4 in sorted(video_dir.glob("episode_*.mp4")):
        idx_str = mp4.stem.replace("episode_", "")
        episodes.append(int(idx_str))
    return episodes


def draw_text_on_frame(frame: np.ndarray, text: str, x: int = 4, y: int = 18,
                       color=(255, 255, 0)) -> np.ndarray:
    """在帧上绘制简易文本 (无需 PIL/cv2，用像素块渲染)。

    使用简化的 5x7 像素字体，仅支持数字、字母和基本符号。
    """
    # 简化方案：在左上角画一个半透明背景 + 用 numpy 实现简单字符
    # 为了避免依赖，使用更简单的方法：在背景条上标注
    frame = frame.copy()

    # 画半透明黑色背景条
    bar_h = LABEL_BAR_HEIGHT
    bar_w = min(len(text) * 10 + 8, frame.shape[1])
    alpha = 0.6
    frame[:bar_h, :bar_w] = (frame[:bar_h, :bar_w].astype(np.float32) * (1 - alpha)).astype(np.uint8)

    # 用简易位图字体渲染
    _draw_bitmap_text(frame, text, x=x, y=3, color=color)

    return frame


# 简易 5x7 位图字体 (仅数字 + 部分字符)
_FONT_5X7 = {
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    '3': ["01110", "10001", "00001", "00110", "00001", "10001", "01110"],
    '4': ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    '5': ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    '6': ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    '9': ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    '/': ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    '.': ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ':': ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    '#': ["01010", "01010", "11111", "01010", "11111", "01010", "01010"],
    's': ["00000", "00000", "01110", "10000", "01110", "00001", "11110"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    '_': ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    'e': ["00000", "00000", "01110", "10001", "11111", "10000", "01110"],
    'n': ["00000", "00000", "10110", "11001", "10001", "10001", "10001"],
    'v': ["00000", "00000", "10001", "10001", "01010", "01010", "00100"],
    'l': ["01100", "00100", "00100", "00100", "00100", "00100", "01110"],
    'f': ["00110", "01000", "01000", "11100", "01000", "01000", "01000"],
    't': ["00000", "01000", "11100", "01000", "01000", "01001", "00110"],
    'r': ["00000", "00000", "10110", "11001", "10000", "10000", "10000"],
    'i': ["00100", "00000", "01100", "00100", "00100", "00100", "01110"],
    'g': ["00000", "00000", "01111", "10001", "01111", "00001", "01110"],
    'h': ["10000", "10000", "10110", "11001", "10001", "10001", "10001"],
    'w': ["00000", "00000", "10001", "10001", "10101", "10101", "01010"],
    'c': ["00000", "00000", "01110", "10000", "10000", "10001", "01110"],
    'a': ["00000", "00000", "01110", "00001", "01111", "10001", "01111"],
    'm': ["00000", "00000", "11010", "10101", "10101", "10001", "10001"],
    'p': ["00000", "00000", "11110", "10001", "11110", "10000", "10000"],
}


def _draw_bitmap_text(frame: np.ndarray, text: str, x: int, y: int,
                      color=(255, 255, 0), scale: int = 3):
    """在 numpy 图像上渲染位图文字。"""
    H, W = frame.shape[:2]
    cx = x
    for ch in text:
        glyph = _FONT_5X7.get(ch)
        if glyph is None:
            cx += 4 * scale  # 未知字符跳过
            continue
        for row_idx, row_str in enumerate(glyph):
            for col_idx, pixel in enumerate(row_str):
                if pixel == '1':
                    py = y + row_idx * scale
                    px = cx + col_idx * scale
                    # 画 scale×scale 的像素块
                    y1, y2 = max(0, py), min(H, py + scale)
                    x1, x2 = max(0, px), min(W, px + scale)
                    if y1 < y2 and x1 < x2:
                        frame[y1:y2, x1:x2] = color
        cx += 6 * scale  # 字符间距


def compose_tiled_video(
    videos: List[np.ndarray],
    labels: List[str],
    output_path: Path,
    fps: int = 30,
    gap: int = 4,
):
    """将多个视频水平拼接为一个带标签和帧号的合成视频。

    Args:
        videos: 每个相机的帧数组列表 [N, H, W, 3]
        labels: 相机标签列表
        output_path: 输出 MP4 路径
        fps: 帧率
        gap: 相机之间的间隔像素
    """
    n_cams = len(videos)
    num_frames = min(len(v) for v in videos)
    H, W = videos[0].shape[1], videos[0].shape[2]

    # 合成画布尺寸
    canvas_w = W * n_cams + gap * (n_cams - 1)
    canvas_h = H + LABEL_BAR_HEIGHT  # 顶部标签栏

    # 确保尺寸为偶数 (h264 要求)
    canvas_w = canvas_w + (canvas_w % 2)
    canvas_h = canvas_h + (canvas_h % 2)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    container = av.open(str(output_path), mode='w')
    stream = container.add_stream('h264', rate=fps)
    stream.width = canvas_w
    stream.height = canvas_h
    stream.pix_fmt = 'yuv420p'
    stream.options = {'crf': '18'}  # 高质量，方便逐帧看

    print(f"\n🎬 合成视频: {canvas_w}×{canvas_h}, {num_frames} 帧")

    for frame_idx in range(num_frames):
        # 创建黑色画布
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

        # 顶部全局帧号标签 (白底黑字区域)
        canvas[:LABEL_BAR_HEIGHT, :] = 32  # 深灰背景

        # 绘制全局帧号
        time_s = frame_idx / fps
        global_text = f"F#{frame_idx}/{num_frames - 1} {time_s:.2f}s"
        _draw_bitmap_text(canvas, global_text, x=4, y=3, color=(255, 255, 0), scale=3)

        # 拼接每个相机
        for cam_idx in range(n_cams):
            x_offset = cam_idx * (W + gap)
            f = videos[cam_idx][min(frame_idx, len(videos[cam_idx]) - 1)]

            # 写入图像区域
            canvas[LABEL_BAR_HEIGHT:LABEL_BAR_HEIGHT + H, x_offset:x_offset + W] = f

            # 在每个相机画面左上角绘制相机名
            label = labels[cam_idx]
            _draw_bitmap_text(canvas, label,
                              x=x_offset + 4, y=LABEL_BAR_HEIGHT + 3,
                              color=(0, 255, 128), scale=2)

        # 间隔线
        for i in range(1, n_cams):
            x_gap = i * (W + gap) - gap
            canvas[LABEL_BAR_HEIGHT:, x_gap:x_gap + gap] = 80  # 灰色分隔线

        # 编码帧
        av_frame = av.VideoFrame.from_ndarray(canvas, format='rgb24')
        for packet in stream.encode(av_frame):
            container.mux(packet)

        # 进度
        if (frame_idx + 1) % 500 == 0 or frame_idx == num_frames - 1:
            pct = (frame_idx + 1) / num_frames * 100
            print(f"   编码进度: {frame_idx + 1}/{num_frames} ({pct:.0f}%)")

    # Flush
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    file_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\n✅ 输出: {output_path} ({file_size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(
        description="三相机视频并排合成工具 (headless 友好)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("output_dir", type=Path, help="LeRobot v2.1 输出目录")
    parser.add_argument("--episode", type=int, default=0, help="Episode 索引 (默认 0)")
    parser.add_argument("--output", type=Path, default=None,
                        help="输出 MP4 路径 (默认: output_dir 下自动命名)")
    parser.add_argument("--fps", type=int, default=30, help="输出帧率 (默认 30)")
    args = parser.parse_args()

    output_dir = args.output_dir
    episode = args.episode
    fps = args.fps

    # 列出可用 episodes
    available = list_available_episodes(output_dir)
    if not available:
        print(f"❌ 未找到视频文件: {output_dir}")
        return

    print(f"📂 数据目录: {output_dir}")
    print(f"   可用 episodes: {len(available)} 个, 范围 [{available[0]}, {available[-1]}]")

    if episode not in available:
        print(f"❌ Episode {episode} 不存在")
        return

    # 查找视频
    video_paths = find_episode_videos(output_dir, episode)
    print(f"\n📹 加载 episode {episode} 的三个相机视频...")

    # 解码视频
    videos = []
    for path, label in zip(video_paths, CAMERA_LABELS):
        print(f"   解码 {label}... ", end="", flush=True)
        v = decode_video(path)
        print(f"✓ {v.shape[0]} 帧, {v.shape[1]}×{v.shape[2]}")
        videos.append(v)

    # 验证帧数一致
    frame_counts = [len(v) for v in videos]
    if len(set(frame_counts)) > 1:
        print(f"\n⚠️  帧数不一致: {dict(zip(CAMERA_LABELS, frame_counts))}")
        print(f"   将使用最小帧数: {min(frame_counts)}")

    # 确定输出路径
    if args.output:
        out_path = args.output
    else:
        ep_dir = _resolve_episode_dir(output_dir, episode)
        out_path = ep_dir / f"sync_compare_ep{episode:04d}.mp4"

    # 合成
    compose_tiled_video(videos, CAMERA_LABELS, out_path, fps=fps)

    print(f"\n💡 逐帧查看提示:")
    print(f"   mpv {out_path}      # 按 . 下一帧, , 上一帧")
    print(f"   ffplay {out_path}   # 按 S 下一帧")


if __name__ == "__main__":
    main()
