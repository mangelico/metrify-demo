import os
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("METRIFY_PROVIDER_KEY", "pk_test_xxx")
os.environ.setdefault("METRIFY_GATEWAY_URL", "http://localhost:9999")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("OPENAI_API_KEY", "sk-openai-test")
os.environ.setdefault("STABILITY_API_KEY", "sk-stability-test")
os.environ.setdefault("ASSEMBLYAI_API_KEY", "sk-assemblyai-test")
os.environ.setdefault("APIFY_API_KEY", "apify-test")
os.environ.setdefault("FIRECRAWL_API_KEY", "fc-test")


@pytest.fixture
def mock_server():
    """FastMCP server mock where @server.tool() is a passthrough."""
    server = MagicMock()
    server.tool.return_value = lambda f: f
    return server


@pytest.fixture
def mock_m():
    """Metrify instance with billing methods mocked out (sync MagicMock)."""
    from metrify import Metrify

    m = Metrify()
    m._billing.check_balance = MagicMock()
    m._billing.charge = MagicMock()
    return m
