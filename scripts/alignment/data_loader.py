"""
Data loader for LeRobot datasets.

Supports both v2.0 (per-episode files) and v3.0 (merged files) formats.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .robot_config import get_robot_config, DEFAULT_CONFIG


@dataclass
class DatasetFormat:
    """Dataset format information."""
    version: str
    fps: float
    robot_type: str
    is_v3: bool
    data_path_pattern: str
    video_path_pattern: str


class DatasetLoader:
    """Loader for LeRobot datasets."""

    def __init__(self, dataset_dir: str | Path):
        self.dataset_dir = Path(dataset_dir)
        self.format_info = self._detect_format()

    def _detect_format(self) -> DatasetFormat:
        """Detect dataset format version."""
        info_path = self.dataset_dir / "meta" / "info.json"

        if info_path.exists():
            with open(info_path, "r") as f:
                info = json.load(f)

            robot_type = info.get("robot_type", "default")
            robot_config = get_robot_config(robot_type)

            version = info.get("codebase_version", "v2.0")
            fps = info.get("fps", robot_config.video.fps)

            if version.startswith("v3"):
                return DatasetFormat(
                    version=version,
                    fps=fps,
                    robot_type=robot_type,
                    is_v3=True,
                    data_path_pattern=info.get(
                        "data_path",
                        "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
                    ),
                    video_path_pattern=info.get(
                        "video_path",
                        robot_config.video.path_pattern
                    ),
                )

            # v2.x format - read config from info.json
            return DatasetFormat(
                version=version,
                fps=fps,
                robot_type=robot_type,
                is_v3=False,
                data_path_pattern=info.get(
                    "data_path",
                    "data/chunk-000/episode_{episode:06d}.parquet"
                ),
                video_path_pattern=info.get(
                    "video_path",
                    robot_config.video.path_pattern
                ),
            )

        # Legacy format (no info.json)
        return DatasetFormat(
            version="v2.0",
            fps=DEFAULT_CONFIG.video.fps,
            robot_type="default",
            is_v3=False,
            data_path_pattern="data/chunk-000/episode_{episode:06d}.parquet",
            video_path_pattern=DEFAULT_CONFIG.video.path_pattern,
        )

    def load_episode(self, episode: int) -> tuple[np.ndarray, np.ndarray, int]:
        """
        Load state and action data for an episode.

        Returns:
            (state, action, num_frames)
        """
        if self.format_info.is_v3:
            return self._load_v3_episode(episode)
        return self._load_v2_episode(episode)

    def _load_v2_episode(self, episode: int) -> tuple[np.ndarray, np.ndarray, int]:
        """Load episode from v2.0 format (per-episode parquet)."""
        parquet_path = self.dataset_dir / "data" / "chunk-000" / f"episode_{episode:06d}.parquet"

        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")

        df = pd.read_parquet(parquet_path)
        state = np.stack(df["observation.state"].values)
        action = np.stack(df["action"].values)

        return state, action, len(df)

    def _load_v3_episode(self, episode: int) -> tuple[np.ndarray, np.ndarray, int]:
        """Load episode from v3.0 format (merged parquet)."""
        data_dir = self.dataset_dir / "data" / "chunk-000"
        parquet_files = sorted(data_dir.glob("file-*.parquet"))

        if not parquet_files:
            raise FileNotFoundError(f"No parquet files found in {data_dir}")

        for pq_file in parquet_files:
            df = pd.read_parquet(pq_file)
            episode_df = df[df["episode_index"] == episode]
            if len(episode_df) > 0:
                state = np.stack(episode_df["observation.state"].values)
                action = np.stack(episode_df["action"].values)
                return state, action, len(episode_df)

        raise ValueError(f"Episode {episode} not found in dataset")

    def get_video_path(self, episode: int, camera: str) -> Path:
        """Get video file path for an episode."""
        if self.format_info.is_v3:
            return self._get_v3_video_path(episode, camera)
        return self._get_v2_video_path(episode, camera)

    def _get_v2_video_path(self, episode: int, camera: str) -> Path:
        """
        Get video path for v2.0/v2.1 format.

        Tries multiple path patterns to support different dataset structures:
        1. Pattern from info.json video_path template
        2. Standard v2.0: videos/chunk-000/observation.images.{camera}/
        3. R1_lite style: chunk-000/observation.images.{camera}/
        4. With _rgb suffix variations
        """
        video_key = f"observation.images.{camera}"

        # Build candidate paths to try
        candidate_paths = []

        # 1. Try pattern from info.json (if available)
        if self.format_info.video_path_pattern:
            try:
                # Handle different placeholder formats
                pattern = self.format_info.video_path_pattern
                # Replace {video_key} placeholder
                pattern = pattern.replace("{video_key}", video_key)
                # Replace episode placeholders
                pattern = pattern.replace("{episode_chunk:03d}", "000")
                pattern = pattern.replace("{episode_index:06d}", f"{episode:06d}")
                candidate_paths.append(self.dataset_dir / pattern)
            except (KeyError, ValueError):
                pass

        # 2. Standard v2.0 pattern: videos/chunk-000/observation.images.{camera}/
        candidate_paths.append(
            self.dataset_dir / "videos" / "chunk-000" / video_key / f"episode_{episode:06d}.mp4"
        )

        # 3. R1_lite style: chunk-000/observation.images.{camera}/ (no videos/ prefix)
        candidate_paths.append(
            self.dataset_dir / "chunk-000" / video_key / f"episode_{episode:06d}.mp4"
        )

        # 4. Try with _rgb suffix if camera name doesn't already have it
        if not camera.endswith("_rgb"):
            video_key_rgb = f"observation.images.{camera}_rgb"
            candidate_paths.append(
                self.dataset_dir / "videos" / "chunk-000" / video_key_rgb / f"episode_{episode:06d}.mp4"
            )
            candidate_paths.append(
                self.dataset_dir / "chunk-000" / video_key_rgb / f"episode_{episode:06d}.mp4"
            )

        # Try each candidate path
        for path in candidate_paths:
            if path.exists():
                return path

        # If none found, raise with helpful message
        tried_paths = "\n  - ".join(str(p) for p in candidate_paths)
        raise FileNotFoundError(
            f"Video not found for episode {episode}, camera '{camera}'.\n"
            f"Tried paths:\n  - {tried_paths}\n"
            f"Available cameras in dataset may have different names (e.g., '{camera}_rgb')."
        )

    def _get_v3_video_path(self, episode: int, camera: str) -> Path:
        """Get video path for v3.0 format."""
        video_key = f"observation.images.{camera}"

        # Try to find from episode metadata
        episodes_dir = self.dataset_dir / "meta" / "episodes"
        if episodes_dir.exists():
            for chunk_dir in sorted(episodes_dir.glob("chunk-*")):
                for ep_file in sorted(chunk_dir.glob("episode_*.json")):
                    ep_idx = int(ep_file.stem.split("_")[1])
                    if ep_idx == episode:
                        with open(ep_file) as f:
                            ep_info = json.load(f)
                        video_info = ep_info.get("videos", {}).get(video_key, {})
                        if "video_path" in video_info:
                            return self.dataset_dir / video_info["video_path"]

        # Fallback: assume chunk-000/file-000.mp4
        video_path = self.dataset_dir / "videos" / video_key / "chunk-000" / "file-000.mp4"
        if video_path.exists():
            return video_path

        # Try alternative patterns
        video_dir = self.dataset_dir / "videos" / video_key / "chunk-000"
        if video_dir.exists():
            video_files = sorted(video_dir.glob("file-*.mp4"))
            if video_files:
                return video_files[0]

        raise FileNotFoundError(f"Video not found for camera {camera}")

    def get_video_frame_range(self, episode: int, camera: str) -> tuple[int, int]:
        """
        Get frame range for episode in video (for v3.0 format).

        Returns:
            (start_frame, end_frame), (-1 for end means until video end)
        """
        if not self.format_info.is_v3:
            return (0, -1)

        fps = self.format_info.fps
        video_key = f"observation.images.{camera}"

        # Read from episode metadata parquet
        episodes_meta_dir = self.dataset_dir / "meta" / "episodes" / "chunk-000"
        meta_files = sorted(episodes_meta_dir.glob("file-*.parquet"))

        if meta_files:
            for meta_file in meta_files:
                df = pd.read_parquet(meta_file)
                ep_row = df[df["episode_index"] == episode]
                if len(ep_row) > 0:
                    ep_data = ep_row.iloc[0]
                    from_ts_col = f"videos/{video_key}/from_timestamp"
                    to_ts_col = f"videos/{video_key}/to_timestamp"

                    if from_ts_col in ep_data and to_ts_col in ep_data:
                        from_ts = ep_data[from_ts_col]
                        to_ts = ep_data[to_ts_col]
                        return (int(from_ts * fps), int(to_ts * fps))

        return (0, -1)

    def list_episodes(self) -> list[int]:
        """List all available episode indices."""
        if self.format_info.is_v3:
            data_dir = self.dataset_dir / "data" / "chunk-000"
            parquet_files = sorted(data_dir.glob("file-*.parquet"))
            if parquet_files:
                df = pd.read_parquet(parquet_files[0])
                return sorted(df["episode_index"].unique().tolist())
            return []
        else:
            data_dir = self.dataset_dir / "data" / "chunk-000"
            return sorted([
                int(f.stem.split("_")[1])
                for f in data_dir.glob("episode_*.parquet")
            ])
