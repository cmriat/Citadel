"""
Command-line interface for alignment analysis.
"""

import argparse
import sys
from pathlib import Path

from .analyzer import AlignmentAnalyzer
from .robot_config import list_robot_types, get_robot_config


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Analyze Frame-State alignment in LeRobot datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze single episode (auto-detect robot type)
    python -m alignment /path/to/dataset

    # Analyze with specific robot type
    python -m alignment /path/to/dataset --robot-type aloha

    # Analyze with black region detection (for ALOHA)
    python -m alignment /path/to/dataset --black-detection

    # Analyze with denoising
    python -m alignment /path/to/dataset --denoise

    # Analyze all episodes
    python -m alignment /path/to/dataset --all-episodes

Supported robot types:
    - airbot_play: Default robot with orange gripper
    - aloha: ALOHA robot with black gripper
    - galaxea_r1_lite: Galaxea R1 Lite with _rgb camera suffix
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

    # Robot type option
    parser.add_argument("--robot-type", "-r", type=str, default=None,
                        choices=list_robot_types(),
                        help="Override robot type (default: auto-detect from dataset)")

    # Camera option (default from robot config)
    parser.add_argument("--camera", "-c", type=str, default=None,
                        help="Camera to use (default: from robot config)")
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

    # Show robot type info
    if parsed.robot_type:
        print(f"Robot type: {parsed.robot_type} (override)")
        robot_config = get_robot_config(parsed.robot_type)
    else:
        print(f"Robot type: auto-detect")
        robot_config = None

    # Show camera info
    if parsed.camera:
        print(f"Camera: {parsed.camera}")
    elif robot_config:
        print(f"Camera: {robot_config.get_default_camera()} (from robot config)")
    else:
        print(f"Camera: (will auto-detect)")

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
            robot_type=parsed.robot_type,
            use_denoise=parsed.denoise,
            denoise_method=parsed.denoise_method
        )

        # Print detected info
        print(f"\nDetected: robot={analyzer.robot_type}, camera={analyzer.camera}, "
              f"gripper_dim={analyzer.gripper_dim}")

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
