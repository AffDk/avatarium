"""Unit tests for generation services and pipeline orchestration.

Covers:
- Image generation model call (fal-ai/qwen-image)
- Video clip generation model call (configured via settings.fal_video_model)
- Last-frame extraction via ffmpeg
- Pipeline orchestration is now DB-aware (run_pipeline_background);
  integration tests in tests/integration/ should cover the full flow.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config import settings
from backend.services.image_gen_service import generate_initial_image
from backend.services.video_gen_service import extract_last_frame, generate_video_clip


class TestImageGenService:
    """Tests for generate_initial_image using fal.ai Qwen Image."""

    @pytest.mark.asyncio
    @patch("backend.services.image_gen_service.download_file", new_callable=AsyncMock)
    @patch("backend.services.image_gen_service.submit_and_poll", new_callable=AsyncMock)
    async def test_generate_image_calls_correct_model(self, mock_poll: AsyncMock, mock_dl: AsyncMock) -> None:
        mock_poll.return_value = {"images": [{"url": "https://example.com/img.jpg"}]}
        mock_dl.return_value = "/tmp/test/initial_image.jpg"

        result = await generate_initial_image(
            prompt="Alice in a garden, animation style",
            output_dir="/tmp/test",
        )

        mock_poll.assert_called_once()
        assert "qwen-image" in mock_poll.call_args[0][0]
        assert result == "/tmp/test/initial_image.jpg"

    @pytest.mark.asyncio
    @patch("backend.services.image_gen_service.download_file", new_callable=AsyncMock)
    @patch("backend.services.image_gen_service.submit_and_poll", new_callable=AsyncMock)
    async def test_generate_image_returns_path(self, mock_poll: AsyncMock, mock_dl: AsyncMock) -> None:
        mock_poll.return_value = {"images": [{"url": "https://example.com/img.jpg"}]}
        mock_dl.return_value = "/tmp/test/initial_image.jpg"

        result = await generate_initial_image(prompt="Scene prompt", output_dir="/tmp/test")
        assert result == "/tmp/test/initial_image.jpg"


class TestVideoGenService:
    """Tests for generate_video_clip using the configured fal.ai video model."""

    @pytest.mark.asyncio
    @patch("backend.services.video_gen_service.download_file", new_callable=AsyncMock)
    @patch("backend.services.video_gen_service.fal_client")
    @patch("backend.services.video_gen_service.submit_and_poll", new_callable=AsyncMock)
    async def test_generate_clip_calls_correct_model(
        self, mock_poll: AsyncMock, mock_fal: MagicMock, mock_dl: AsyncMock,
    ) -> None:
        mock_fal.upload_file_async = AsyncMock(return_value="https://fal.ai/uploaded/img.jpg")
        mock_poll.return_value = {"video": {"url": "https://example.com/clip.mp4"}}
        mock_dl.return_value = "/tmp/test/clip_1.mp4"

        await generate_video_clip(
            image_path="/tmp/test/img.jpg",
            prompt="Alice walks through garden",
            output_path="/tmp/test/clip_1.mp4",
        )

        mock_poll.assert_called_once()
        assert mock_poll.call_args[0][0] == settings.fal_video_model

    @pytest.mark.asyncio
    @patch("backend.services.video_gen_service.subprocess")
    async def test_extract_last_frame(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        result = await extract_last_frame(
            video_path="/tmp/test/clip_1.mp4",
            output_path="/tmp/test/last_frame_1.jpg",
        )
        assert result == "/tmp/test/last_frame_1.jpg"
        mock_subprocess.run.assert_called_once()
