"""
Core alignment analyzer module.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np

from .config import LEFT_GRIPPER_DIM, RIGHT_GRIPPER_DIM
from .data_loader import DatasetLoader
from .signal_processing import SignalProcessor, AlignmentEvent
from .video_tracker import VideoTracker
from .visualization import AlignmentVisualizer


@dataclass
class AlignmentResult:
    """Single event alignment result (for export)."""
    frame: int
    state_peak: int
    video_peak: int
    offset: int
    offset_ms: float
    state_change: float


@dataclass
class AlignmentReport:
    """Overall alignment analysis report."""
    dataset_dir: str
    episode: int
    analysis_time: str
    total_frames: int
    total_events: int
    mean_offset_frames: float
    mean_offset_ms: float
    median_offset_frames: float
    std_offset_frames: float
    min_offset: int
    max_offset: int
    offset_distribution: dict
    conclusion: str
    events: list


class AlignmentAnalyzer:
    """
    Main analyzer for frame-state alignment.

    Usage:
        analyzer = AlignmentAnalyzer("/path/to/dataset")
        report = analyzer.analyze_episode(0)
    """

    def __init__(self, dataset_dir: str | Path,
                 detection_mode: Literal["roi", "black", "color"] = "roi",
                 camera: str = "cam_left_wrist",
                 gripper: Literal["left", "right"] = "left",
                 use_denoise: bool = False,
                 denoise_method: str = "state_guided"):
        """
        Initialize analyzer.

        Args:
            dataset_dir: Path to LeRobot dataset
            detection_mode: Video tracking method ("roi", "black", "color")
            camera: Camera to analyze
            gripper: Gripper to analyze ("left" or "right")
            use_denoise: Whether to apply denoising
            denoise_method: Denoising method
        """
        self.dataset_dir = Path(dataset_dir)
        self.detection_mode = detection_mode
        self.camera = camera
        self.gripper_dim = LEFT_GRIPPER_DIM if gripper == "left" else RIGHT_GRIPPER_DIM
        self.use_denoise = use_denoise
        self.denoise_method = denoise_method

        # Initialize components
        self.loader = DatasetLoader(dataset_dir)
        self.format_info = self.loader.format_info
        self.fps = self.format_info.fps
        self.robot_type = self.format_info.robot_type

        self.tracker = VideoTracker(detection_mode, self.robot_type, camera)
        self.signal_processor = SignalProcessor(self.fps)
        self.visualizer = AlignmentVisualizer()

    def analyze_episode(self, episode: int, output_dir: Path = None,
                        verbose: bool = True) -> AlignmentReport:
        """
        Analyze frame-state alignment for a single episode.

        Args:
            episode: Episode index
            output_dir: Output directory (default: dataset_dir/alignment_analysis)
            verbose: Print progress messages

        Returns:
            AlignmentReport
        """
        output_dir = output_dir or (self.dataset_dir / "alignment_analysis")
        output_dir.mkdir(parents=True, exist_ok=True)

        if verbose:
            print(f"\n{'='*60}")
            print(f"Analyzing Episode {episode}")
            print(f"{'='*60}")
            print(f"Format: {self.format_info.version}, FPS: {self.fps}, Robot: {self.robot_type}")

        # Load data
        state, _, num_frames = self.loader.load_episode(episode)
        if verbose:
            print(f"Loaded {num_frames} frames")

        # Get video info
        video_path = self.loader.get_video_path(episode, self.camera)
        frame_range = self.loader.get_video_frame_range(episode, self.camera)

        if verbose:
            print(f"Video: {video_path}")
            if frame_range != (0, -1):
                print(f"Frame range: {frame_range[0]} - {frame_range[1]}")
            print(f"Computing video frame differences ({self.tracker.description})...")

        # Compute video diffs
        video_diff = self.tracker.compute_diffs(video_path, frame_range)

        # Align lengths
        if len(video_diff) != num_frames:
            if verbose:
                print(f"⚠ Frame count mismatch: video={len(video_diff)}, state={num_frames}")
            min_len = min(len(video_diff), num_frames)
            video_diff = video_diff[:min_len]
            state = state[:min_len]

        # Compute state diff
        state_diff = self.signal_processor.compute_state_diff(state, self.gripper_dim)

        # Apply denoising if requested
        if self.use_denoise:
            if verbose:
                print(f"Applying state-guided denoising (method: {self.denoise_method})...")

            video_diff_raw = video_diff.copy()
            video_diff = self.signal_processor.denoise(video_diff, state_diff, self.denoise_method)

            # Report correlation improvement
            corr_raw = self.signal_processor.compute_correlation(state_diff, video_diff_raw)
            corr_denoised = self.signal_processor.compute_correlation(state_diff, video_diff)
            if verbose:
                improvement = (corr_denoised - corr_raw) / abs(corr_raw) * 100 if corr_raw != 0 else 0
                print(f"Correlation improvement: {corr_raw:.3f} → {corr_denoised:.3f} (+{improvement:.1f}%)")

        # Find significant state changes
        significant_frames = self.signal_processor.find_significant_changes(state, self.gripper_dim)
        if verbose:
            print(f"Found {len(significant_frames)} significant state changes")

        # Compute offsets
        events = self.signal_processor.compute_offsets(state_diff, video_diff, significant_frames)
        offsets = [e.offset for e in events]

        # Generate report
        report = self._create_report(episode, len(state), offsets, events, verbose)

        # Create visualization
        vis_path = output_dir / f"episode_{episode:06d}_alignment.png"
        self.visualizer.create_report(state_diff, video_diff, offsets, vis_path, episode)
        if verbose:
            print(f"\nVisualization saved: {vis_path}")

        # Save JSON report
        report_path = output_dir / f"episode_{episode:06d}_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)
        if verbose:
            print(f"Report saved: {report_path}")

        return report

    def analyze_all_episodes(self, output_dir: Path = None, verbose: bool = True) -> dict:
        """
        Analyze all episodes in the dataset.

        Returns:
            Summary report dictionary
        """
        output_dir = output_dir or (self.dataset_dir / "alignment_analysis")
        episodes = self.loader.list_episodes()

        if verbose:
            print(f"Found {len(episodes)} episodes (format: {self.format_info.version})")

        all_offsets = []
        reports = []

        for ep in episodes:
            try:
                report = self.analyze_episode(ep, output_dir, verbose)
                reports.append(report)
                if report.total_events > 0:
                    all_offsets.extend([e["offset"] for e in report.events])
            except Exception as e:
                if verbose:
                    print(f"⚠ Error analyzing episode {ep}: {e}")

        # Generate summary
        if len(all_offsets) > 0:
            summary = {
                "dataset_dir": str(self.dataset_dir),
                "format_version": self.format_info.version,
                "fps": self.fps,
                "total_episodes": len(episodes),
                "total_events": len(all_offsets),
                "overall_mean_offset_frames": float(np.mean(all_offsets)),
                "overall_mean_offset_ms": float(np.mean(all_offsets) * 1000 / self.fps),
                "overall_median_offset_frames": float(np.median(all_offsets)),
                "overall_std_offset_frames": float(np.std(all_offsets)),
                "overall_min_offset": int(min(all_offsets)),
                "overall_max_offset": int(max(all_offsets)),
                "episode_reports": [asdict(r) for r in reports]
            }

            # Save summary
            summary_path = output_dir / "summary_report.json"
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            if verbose:
                print(f"\n{'='*60}")
                print("OVERALL SUMMARY")
                print(f"{'='*60}")
                print(f"Total episodes: {len(episodes)}")
                print(f"Total events: {len(all_offsets)}")
                print(f"Mean offset: {np.mean(all_offsets):+.2f} frames "
                      f"({np.mean(all_offsets) * 1000 / self.fps:+.1f}ms)")
                print(f"Median offset: {np.median(all_offsets):+.1f} frames")
                print(f"Summary saved: {summary_path}")

            return summary

        return {"error": "No events detected in any episode"}

    def _create_report(self, episode: int, num_frames: int, offsets: list[int],
                       events: list[AlignmentEvent], verbose: bool) -> AlignmentReport:
        """Create alignment report from analysis results."""
        if len(offsets) == 0:
            if verbose:
                print("⚠ No significant events detected!")
            return AlignmentReport(
                dataset_dir=str(self.dataset_dir),
                episode=episode,
                analysis_time=datetime.now().isoformat(),
                total_frames=num_frames,
                total_events=0,
                mean_offset_frames=0,
                mean_offset_ms=0,
                median_offset_frames=0,
                std_offset_frames=0,
                min_offset=0,
                max_offset=0,
                offset_distribution={},
                conclusion="Insufficient data for analysis",
                events=[]
            )

        mean_offset = np.mean(offsets)
        median_offset = np.median(offsets)
        std_offset = np.std(offsets)
        offset_ms = mean_offset * 1000 / self.fps

        # Generate conclusion
        if abs(mean_offset) < 1:
            conclusion = f"✓ Frame and State/Action are well synchronized (offset: {mean_offset:+.1f} frames)"
        elif mean_offset > 0:
            conclusion = f"⚠ Video lags behind State by {mean_offset:.1f} frames ({offset_ms:.0f}ms)"
        else:
            conclusion = f"⚠ Video leads State by {abs(mean_offset):.1f} frames ({abs(offset_ms):.0f}ms)"

        if verbose:
            print(f"\n--- Results ---")
            print(f"Events analyzed: {len(offsets)}")
            print(f"Mean offset: {mean_offset:+.2f} frames ({offset_ms:+.1f}ms)")
            print(f"Median offset: {median_offset:+.1f} frames")
            print(f"Std offset: {std_offset:.2f} frames")
            print(f"Range: [{min(offsets):+d}, {max(offsets):+d}] frames")
            print(f"\nConclusion: {conclusion}")

        # Compute offset distribution
        offset_dist = {}
        for o in range(min(offsets) - 1, max(offsets) + 2):
            offset_dist[str(o)] = int(sum(1 for x in offsets if x == o))

        return AlignmentReport(
            dataset_dir=str(self.dataset_dir),
            episode=episode,
            analysis_time=datetime.now().isoformat(),
            total_frames=num_frames,
            total_events=len(offsets),
            mean_offset_frames=float(mean_offset),
            mean_offset_ms=float(offset_ms),
            median_offset_frames=float(median_offset),
            std_offset_frames=float(std_offset),
            min_offset=int(min(offsets)),
            max_offset=int(max(offsets)),
            offset_distribution=offset_dist,
            conclusion=conclusion,
            events=[asdict(e) for e in events]
        )
