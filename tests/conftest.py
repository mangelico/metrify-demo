import os
import pytest

# Set env vars before any app imports so pydantic-settings finds them
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("STABILITY_API_KEY", "test-key")
os.environ.setdefault("ASSEMBLYAI_API_KEY", "test-key")
os.environ.setdefault("APIFY_API_TOKEN", "test-token")
os.environ.setdefault("FIRECRAWL_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "60")
