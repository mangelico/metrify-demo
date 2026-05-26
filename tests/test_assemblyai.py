import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from metrify import InsufficientBalanceError, GatewayError


@pytest.fixture
def assemblyai_fn(mock_server, mock_m):
    from tools.assemblyai_tool import register
    return register(mock_server, mock_m)


def _http_mock(post_data: dict, get_data: dict):
    submit_resp = MagicMock()
    submit_resp.json.return_value = post_data
    submit_resp.raise_for_status = MagicMock()

    poll_resp = MagicMock()
    poll_resp.json.return_value = get_data
    poll_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=submit_resp)
    mock_client.get = AsyncMock(return_value=poll_resp)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


async def test_assemblyai_happy_path(assemblyai_fn, mock_m):
    ctx = _http_mock(
        post_data={"id": "tx_abc123"},
        get_data={"status": "completed", "text": "Hello world transcription"},
    )
    with patch("httpx.AsyncClient", return_value=ctx):
        result = await assemblyai_fn("ck_test", "https://example.com/audio.mp3")

    assert result == "Hello world transcription"
    mock_m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_test", required=0.00617)
    mock_m._billing.charge.assert_called_once_with(consumer_api_key="ck_test", tool_name="assemblyai", cost=0.00617)


async def test_assemblyai_insufficient_balance(assemblyai_fn, mock_m):
    mock_m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    with pytest.raises(InsufficientBalanceError):
        await assemblyai_fn("ck_test", "https://example.com/audio.mp3")

    mock_m._billing.charge.assert_not_called()


async def test_assemblyai_gateway_error(assemblyai_fn, mock_m):
    mock_m._billing.check_balance.side_effect = GatewayError("timeout")

    with pytest.raises(GatewayError):
        await assemblyai_fn("ck_test", "https://example.com/audio.mp3")

    mock_m._billing.charge.assert_not_called()


async def test_assemblyai_transcription_error_no_charge(assemblyai_fn, mock_m):
    ctx = _http_mock(
        post_data={"id": "tx_abc123"},
        get_data={"status": "error", "error": "Audio format not supported"},
    )
    with patch("httpx.AsyncClient", return_value=ctx):
        result = await assemblyai_fn("ck_test", "https://example.com/audio.mp3")

    assert result.startswith("Error:")
    mock_m._billing.charge.assert_not_called()


async def test_assemblyai_duration_too_long(assemblyai_fn, mock_m):
    ctx = _http_mock(
        post_data={"id": "tx_abc123"},
        get_data={"status": "completed", "text": "...", "audio_duration": 301},
    )
    with patch("httpx.AsyncClient", return_value=ctx):
        result = await assemblyai_fn("ck_test", "https://example.com/long.mp3")

    assert result.startswith("Error:")
    assert "5 minutes" in result
    mock_m._billing.charge.assert_not_called()


async def test_assemblyai_duration_missing_skips_check(assemblyai_fn, mock_m):
    ctx = _http_mock(
        post_data={"id": "tx_abc123"},
        get_data={"status": "completed", "text": "ok"},
    )
    with patch("httpx.AsyncClient", return_value=ctx):
        result = await assemblyai_fn("ck_test", "https://example.com/audio.mp3")

    assert result == "ok"
    mock_m._billing.charge.assert_called_once()
