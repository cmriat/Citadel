"""
Command-line interface for alignment analysis.
"""

import argparse
import sys
from pathlib import Path

from .analyzer import AlignmentAnalyzer


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Analyze Frame-State alignment in LeRobot datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze single episode
    python -m filter_lerobot.alignment /path/to/dataset

    # Analyze with black region detection (for ALOHA)
    python -m filter_lerobot.alignment /path/to/dataset --black-detection

    # Analyze with denoising
    python -m filter_lerobot.alignment /path/to/dataset --denoise

    # Analyze all episodes
    python -m filter_lerobot.alignment /path/to/dataset --all-episodes
"""
    )

    parser.add_argument("dataset_dir", type=str,
                        help="Path to LeRobot dataset directory")
    parser.add_argument("--episode", "-e", type=int, default=0,
                        help="Episode index to analyze (default: 0)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Output directory (default: dataset_dir/alignment_analysis)")
    parser.add_argument("--all-episodes", "-a", action="store_true",
                        help="Analyze all episodes")
    parser.add_argument("--camera", "-c", type=str, default="cam_left_wrist",
                        help="Camera to use (default: cam_left_wrist)")
    parser.add_argument("--gripper", "-g", type=str, default="left",
                        choices=["left", "right"],
                        help="Gripper to analyze (default: left)")

    # Detection mode options (mutually exclusive)
    detection_group = parser.add_mutually_exclusive_group()
    detection_group.add_argument("--color-detection", action="store_true",
                                  help="Use orange color detection (for orange grippers)")
    detection_group.add_argument("--black-detection", action="store_true",
                                  help="Use black region detection (for ALOHA)")

    # Denoising options
    parser.add_argument("--denoise", action="store_true",
                        help="Apply state-guided denoising")
    parser.add_argument("--denoise-method", type=str, default="state_guided",
                        choices=["state_guided", "weighted", "adaptive"],
                        help="Denoising method (default: state_guided)")

    return parser


def main(args: list[str] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    dataset_dir = Path(parsed.dataset_dir)
    if not dataset_dir.exists():
        print(f"Error: Dataset directory not found: {dataset_dir}")
        return 1

    # Determine detection mode
    if parsed.color_detection:
        detection_mode = "color"
    elif parsed.black_detection:
        detection_mode = "black"
    else:
        detection_mode = "roi"

    output_dir = Path(parsed.output) if parsed.output else None

    print(f"Dataset: {dataset_dir}")
    print(f"Camera: {parsed.camera}")
    print(f"Gripper: {parsed.gripper}")
    print(f"Detection mode: {detection_mode}")
    if parsed.denoise:
        print(f"Denoising: enabled (method={parsed.denoise_method})")

    try:
        analyzer = AlignmentAnalyzer(
            dataset_dir=dataset_dir,
            detection_mode=detection_mode,
            camera=parsed.camera,
            gripper=parsed.gripper,
            use_denoise=parsed.denoise,
            denoise_method=parsed.denoise_method
        )

        if parsed.all_episodes:
            analyzer.analyze_all_episodes(output_dir)
        else:
            analyzer.analyze_episode(parsed.episode, output_dir)

        return 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
