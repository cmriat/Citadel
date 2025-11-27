#!/usr/bin/env python3
"""LeRobot v2.1 数据转换 CLI 入口"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lerobot_converter.pipeline.converter import LeRobotConverter
from lerobot_converter.pipeline.config import load_config


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='LeRobot v2.1 数据转换器 - 支持三种对齐策略',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用 chunking 策略转换所有 episodes
  python scripts/convert.py --config config/dual_arm_chunking.yaml

  # 使用 nearest 策略转换单个 episode
  python scripts/convert.py --config config/dual_arm_nearest.yaml --episode-id episode_0000

  # 覆盖配置文件中的策略和输出路径
  python scripts/convert.py --config config/dual_arm_chunking.yaml \\
      --strategy window --output ./custom_output

  # 覆盖 chunk_size 参数
  python scripts/convert.py --config config/dual_arm_chunking.yaml \\
      --chunk-size 15

使用 Pixi 快捷命令:
  pixi run convert-nearest   # 最近邻策略
  pixi run convert-chunking  # Action chunking 策略
  pixi run convert-window    # 时间窗口策略
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='配置文件路径 (YAML)'
    )

    parser.add_argument(
        '--strategy',
        type=str,
        choices=['nearest', 'chunking', 'window'],
        help='对齐策略 (覆盖配置文件)'
    )

    parser.add_argument(
        '--chunk-size',
        type=int,
        help='Chunking 策略的 chunk size (覆盖配置文件)'
    )

    parser.add_argument(
        '--window-ms',
        type=int,
        help='Window 策略的时间窗口大小/毫秒 (覆盖配置文件)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='输出目录路径 (覆盖配置文件)'
    )

    parser.add_argument(
        '--episode-id',
        type=str,
        help='只转换指定的单个 episode (例如: episode_0000)'
    )

    parser.add_argument(
        '--min-duration',
        type=float,
        help='最小时长过滤/秒 (覆盖配置文件)'
    )

    return parser.parse_args()


def override_config(config: dict, args: argparse.Namespace) -> dict:
    """
    使用命令行参数覆盖配置

    Args:
        config: 原始配置字典
        args: 命令行参数

    Returns:
        覆盖后的配置字典
    """
    # 覆盖对齐策略
    if args.strategy:
        config['alignment']['strategy'] = args.strategy
        print(f"  └─ Strategy override: {args.strategy}")

    # 覆盖 chunk_size
    if args.chunk_size:
        config['alignment']['chunk_size'] = args.chunk_size
        print(f"  └─ Chunk size override: {args.chunk_size}")

    # 覆盖 window_ms
    if args.window_ms:
        config['alignment']['window_ms'] = args.window_ms
        print(f"  └─ Window size override: {args.window_ms}ms")

    # 覆盖输出路径
    if args.output:
        config['output']['base_path'] = args.output
        print(f"  └─ Output path override: {args.output}")

    # 覆盖最小时长
    if args.min_duration:
        if 'filtering' not in config:
            config['filtering'] = {}
        config['filtering']['min_duration_sec'] = args.min_duration
        print(f"  └─ Min duration override: {args.min_duration}s")

    return config


def main():
    """主函数"""
    args = parse_args()

    try:
        # 1. 加载配置
        print(f"\n📂 Loading config: {args.config}")
        config = load_config(args.config)

        # 2. 应用命令行覆盖
        if any([args.strategy, args.chunk_size, args.window_ms,
                args.output, args.min_duration]):
            print("\n🔧 Applying CLI overrides:")
            config = override_config(config, args)

        # 3. 创建转换器
        converter = LeRobotConverter(config)

        # 4. 执行转换
        if args.episode_id:
            print(f"\n🎯 Converting single episode: {args.episode_id}")
            converter.convert(episode_id=args.episode_id)
        else:
            print("\n🚀 Converting all episodes...")
            converter.convert()

        print("\n✅ Conversion completed successfully!\n")
        return 0

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        print("请检查配置文件路径和输入数据路径是否正确。\n", file=sys.stderr)
        return 1

    except ValueError as e:
        print(f"\n❌ Configuration error: {e}", file=sys.stderr)
        print("请检查配置文件的有效性。\n", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Conversion interrupted by user.\n", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
