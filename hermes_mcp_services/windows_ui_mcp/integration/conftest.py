import os
import sys
import asyncio
from pathlib import Path

import pytest
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_service import WindowsMCPService


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def require_real_tests() -> None:
    if not _env_flag("HERMES_RUN_REAL_TESTS"):
        pytest.skip(
            "Real integration tests are disabled. Set HERMES_RUN_REAL_TESTS=1 to enable."
        )


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not set.")
    return value


def get_env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    return int(value)


def get_env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


@pytest.fixture()
def real_service():
    require_real_tests()
    return WindowsMCPService()


@pytest.fixture()
def server_url():
    require_real_tests()
    return get_env_str("HERMES_TEST_SERVER_URL", "http://localhost:8030/mcp")


def run_async(awaitable):
    return asyncio.run(awaitable)


async def call_tool(server_url: str, tool_name: str, arguments: dict):
    async with Client(server_url) as client:
        result = await client.call_tool(tool_name, arguments)
        return result.data
