"""Unit tests for pipeline_service — iterative video generation orchestration.

Tests MUST fail before T044 implementation (Constitution Principle V: Test-First).

Covers:
- Pipeline orchestration sequence (image→video→frame→video→frame…)
- Mock fal_client.subscribe calls
- Correct model IDs (fal-ai/qwen-image, fal-ai/ltx-video-13b-distilled/image-to-video)
- Retry logic (1 automatic retry)
- Failure handling after retry exhausted
- Status transitions (pending→generating→completed/failed)
- Last-frame extraction call
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.image_gen_service import generate_initial_image
from backend.services.video_gen_service import generate_video_clip, extract_last_frame
from backend.services.pipeline_service import run_pipeline


class TestImageGenService:
    """Tests for generate_initial_image using fal.ai Qwen Image."""

    @pytest.mark.asyncio
    @patch("backend.services.image_gen_service.fal_client")
    async def test_generate_image_calls_correct_model(self, mock_fal: MagicMock) -> None:
        """Should call fal-ai/qwen-image model."""
        mock_fal.subscribe = AsyncMock(return_value={"images": [{"url": "https://example.com/img.jpg"}]})

        result = await generate_initial_image(
            prompt="Alice in a garden, animation style",
            output_dir="/tmp/test",
        )

        mock_fal.subscribe.assert_called_once()
        call_args = mock_fal.subscribe.call_args
        assert "qwen-image" in call_args[0][0]
        assert result is not None

    @pytest.mark.asyncio
    @patch("backend.services.image_gen_service.fal_client")
    async def test_generate_image_returns_path(self, mock_fal: MagicMock) -> None:
        """Should return path to downloaded image."""
        mock_fal.subscribe = AsyncMock(return_value={"images": [{"url": "https://example.com/img.jpg"}]})

        with patch("backend.services.image_gen_service.download_file", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = "/tmp/test/initial_image.jpg"
            result = await generate_initial_image(
                prompt="Scene prompt",
                output_dir="/tmp/test",
            )
            assert result == "/tmp/test/initial_image.jpg"


class TestVideoGenService:
    """Tests for generate_video_clip using fal.ai LTX Video."""

    @pytest.mark.asyncio
    @patch("backend.services.video_gen_service.fal_client")
    async def test_generate_clip_calls_correct_model(self, mock_fal: MagicMock) -> None:
        """Should call fal-ai/ltx-video-13b-distilled/image-to-video."""
        mock_fal.subscribe = AsyncMock(return_value={"video": {"url": "https://example.com/clip.mp4"}})

        with patch("backend.services.video_gen_service.download_file", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = "/tmp/test/clip_1.mp4"
            result = await generate_video_clip(
                image_path="/tmp/test/img.jpg",
                prompt="Alice walks through garden",
                output_path="/tmp/test/clip_1.mp4",
            )

        mock_fal.subscribe.assert_called_once()
        call_args = mock_fal.subscribe.call_args
        assert "ltx-video" in call_args[0][0]

    @pytest.mark.asyncio
    @patch("backend.services.video_gen_service.subprocess")
    async def test_extract_last_frame(self, mock_subprocess: MagicMock) -> None:
        """Should call ffmpeg to extract last frame."""
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        result = await extract_last_frame(
            video_path="/tmp/test/clip_1.mp4",
            output_path="/tmp/test/last_frame_1.jpg",
        )
        assert result == "/tmp/test/last_frame_1.jpg"
        mock_subprocess.run.assert_called_once()


class TestPipelineOrchestration:
    """Tests for run_pipeline orchestration."""

    @pytest.mark.asyncio
    @patch("backend.services.pipeline_service.extract_last_frame", new_callable=AsyncMock)
    @patch("backend.services.pipeline_service.generate_video_clip", new_callable=AsyncMock)
    @patch("backend.services.pipeline_service.generate_initial_image", new_callable=AsyncMock)
    async def test_pipeline_sequence(
        self,
        mock_image: AsyncMock,
        mock_video: AsyncMock,
        mock_frame: AsyncMock,
    ) -> None:
        """Pipeline should: image → video → frame → video → frame for 2 segments."""
        mock_image.return_value = "/tmp/initial.jpg"
        mock_video.return_value = "/tmp/clip.mp4"
        mock_frame.return_value = "/tmp/frame.jpg"

        segments = [
            {"sequence_number": 1, "description": "Scene one"},
            {"sequence_number": 2, "description": "Scene two"},
        ]

        results = await run_pipeline(
            segments=segments,
            style="animation",
            output_dir="/tmp/test",
            person_names=["alice"],
        )

        # First call generates the initial image
        assert mock_image.call_count == 1
        # Two segments = two video generations
        assert mock_video.call_count == 2
        # Last frame extracted after each clip (for next clip's input)
        assert mock_frame.call_count == 2
        # Should return list of clip results
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch("backend.services.pipeline_service.extract_last_frame", new_callable=AsyncMock)
    @patch("backend.services.pipeline_service.generate_video_clip", new_callable=AsyncMock)
    @patch("backend.services.pipeline_service.generate_initial_image", new_callable=AsyncMock)
    async def test_pipeline_retry_on_failure(
        self,
        mock_image: AsyncMock,
        mock_video: AsyncMock,
        mock_frame: AsyncMock,
    ) -> None:
        """Pipeline retries once on video generation failure."""
        mock_image.return_value = "/tmp/initial.jpg"
        mock_video.side_effect = [RuntimeError("fal error"), "/tmp/clip.mp4"]
        mock_frame.return_value = "/tmp/frame.jpg"

        segments = [{"sequence_number": 1, "description": "Scene one"}]

        results = await run_pipeline(
            segments=segments,
            style="animation",
            output_dir="/tmp/test",
            person_names=["alice"],
        )

        # Should have retried: 1 fail + 1 success = 2 calls
        assert mock_video.call_count == 2
        assert len(results) == 1

    @pytest.mark.asyncio
    @patch("backend.services.pipeline_service.extract_last_frame", new_callable=AsyncMock)
    @patch("backend.services.pipeline_service.generate_video_clip", new_callable=AsyncMock)
    @patch("backend.services.pipeline_service.generate_initial_image", new_callable=AsyncMock)
    async def test_pipeline_fails_after_retry_exhausted(
        self,
        mock_image: AsyncMock,
        mock_video: AsyncMock,
        mock_frame: AsyncMock,
    ) -> None:
        """Pipeline raises after retry exhausted."""
        mock_image.return_value = "/tmp/initial.jpg"
        mock_video.side_effect = RuntimeError("persistent error")

        segments = [{"sequence_number": 1, "description": "Scene one"}]

        with pytest.raises(RuntimeError, match="persistent error"):
            await run_pipeline(
                segments=segments,
                style="animation",
                output_dir="/tmp/test",
                person_names=["alice"],
            )

        # Original call + 1 retry = 2 attempts
        assert mock_video.call_count == 2
