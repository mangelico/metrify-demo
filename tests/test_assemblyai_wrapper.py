from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.wrappers.assemblyai_wrapper import AssemblyAIWrapper
from src.wrappers.base import UpstreamError


def _make_mock_client(submit_json: dict, poll_json: dict):
    submit_response = MagicMock()
    submit_response.json.return_value = submit_json
    submit_response.raise_for_status = MagicMock()
    submit_response.status_code = 200

    poll_response = MagicMock()
    poll_response.json.return_value = poll_json
    poll_response.raise_for_status = MagicMock()
    poll_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=submit_response)
    mock_client.get = AsyncMock(return_value=poll_response)
    return mock_client


@pytest.mark.asyncio
async def test_estimate_cost_default_duration():
    wrapper = AssemblyAIWrapper()
    cost = await wrapper.estimate_cost({})
    # 60 seconds = 1 minute = $0.00617
    assert cost == Decimal("0.00617")


@pytest.mark.asyncio
async def test_estimate_cost_custom_duration():
    wrapper = AssemblyAIWrapper()
    cost = await wrapper.estimate_cost({"duration_seconds": 120})
    # 120 seconds = 2 minutes = $0.01234
    assert cost == Decimal("0.012340")


@pytest.mark.asyncio
async def test_estimate_cost_partial_minute():
    wrapper = AssemblyAIWrapper()
    cost = await wrapper.estimate_cost({"duration_seconds": 30})
    # 30 seconds = 0.5 minutes
    assert cost == Decimal("0.003085")


@pytest.mark.asyncio
async def test_call_happy_path_uses_audio_duration_from_response():
    wrapper = AssemblyAIWrapper()
    submit_json = {"id": "abc123"}
    poll_json = {
        "id": "abc123",
        "status": "completed",
        "text": "Hello world",
        "audio_duration": 90,
        "language_code": "en",
    }
    mock_client = _make_mock_client(submit_json, poll_json)

    with patch("src.wrappers.assemblyai_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({"audio_url": "https://example.com/audio.mp3"})

    assert result["transcript_id"] == "abc123"
    assert result["text"] == "Hello world"
    assert result["audio_duration_seconds"] == 90.0
    # 90 seconds = 1.5 minutes * $0.00617 = $0.009255
    assert cost == Decimal("0.009255")


@pytest.mark.asyncio
async def test_call_uses_estimated_duration_as_fallback():
    wrapper = AssemblyAIWrapper()
    submit_json = {"id": "abc123"}
    poll_json = {
        "id": "abc123",
        "status": "completed",
        "text": "Fallback test",
        # no audio_duration in response
    }
    mock_client = _make_mock_client(submit_json, poll_json)

    with patch("src.wrappers.assemblyai_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({
            "audio_url": "https://example.com/audio.mp3",
            "duration_seconds": 60,
        })

    assert result["audio_duration_seconds"] == 60.0
    assert cost == Decimal("0.00617")


@pytest.mark.asyncio
async def test_call_transcription_error_raises_upstream_error():
    wrapper = AssemblyAIWrapper()
    submit_json = {"id": "abc123"}
    poll_json = {
        "id": "abc123",
        "status": "error",
        "error": "Audio file could not be decoded",
    }
    mock_client = _make_mock_client(submit_json, poll_json)

    with patch("src.wrappers.assemblyai_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"audio_url": "https://example.com/bad.mp3"})

    assert "Audio file could not be decoded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_http_status_error_raises_upstream_error():
    wrapper = AssemblyAIWrapper()
    mock_bad_response = MagicMock()
    mock_bad_response.status_code = 401
    mock_bad_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=mock_bad_response
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_bad_response)

    with patch("src.wrappers.assemblyai_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"audio_url": "https://example.com/audio.mp3"})

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_call_request_error_raises_upstream_error():
    wrapper = AssemblyAIWrapper()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        side_effect=httpx.RequestError("Connection refused", request=MagicMock())
    )

    with patch("src.wrappers.assemblyai_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"audio_url": "https://example.com/audio.mp3"})

    assert exc_info.value.status_code == 0
