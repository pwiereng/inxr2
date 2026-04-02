"""Tests for MCP resource handlers."""

import pytest
from mcp.types import (
    AnyUrl,
    ListResourcesRequest,
    ReadResourceRequest,
    ReadResourceRequestParams,
)

from src.resources import guide
from src.server import create_server
from tests.fake_client import FakeInxr2Client


class TestGuideResourceConstants:
    def test_resource_uri(self) -> None:
        assert guide.RESOURCE_URI == "inxr2://guide"

    def test_resource_content_non_empty(self) -> None:
        assert len(guide.RESOURCE_CONTENT.strip()) > 0

    def test_resource_content_covers_key_sections(self) -> None:
        content = guide.RESOURCE_CONTENT
        assert "How the Index Works" in content
        assert "Index Staleness" in content
        assert "Tool Selection" in content
        assert "Workflows" in content


class TestListResources:
    async def test_returns_exactly_one_resource(self) -> None:
        server = create_server(FakeInxr2Client())
        handler = server.request_handlers[ListResourcesRequest]
        result = await handler(
            ListResourcesRequest(method="resources/list", params=None)
        )
        resources = result.root.resources
        assert len(resources) == 1

    async def test_resource_uri_is_guide(self) -> None:
        server = create_server(FakeInxr2Client())
        handler = server.request_handlers[ListResourcesRequest]
        result = await handler(
            ListResourcesRequest(method="resources/list", params=None)
        )
        assert str(result.root.resources[0].uri) == "inxr2://guide"

    async def test_resource_name(self) -> None:
        server = create_server(FakeInxr2Client())
        handler = server.request_handlers[ListResourcesRequest]
        result = await handler(
            ListResourcesRequest(method="resources/list", params=None)
        )
        assert result.root.resources[0].name == guide.RESOURCE_NAME


class TestReadResource:
    async def test_read_guide_returns_non_empty_text(self) -> None:
        server = create_server(FakeInxr2Client())
        handler = server.request_handlers[ReadResourceRequest]
        result = await handler(
            ReadResourceRequest(
                method="resources/read",
                params=ReadResourceRequestParams(uri=AnyUrl(guide.RESOURCE_URI)),
            )
        )
        contents = result.root.contents
        assert len(contents) == 1
        assert len(contents[0].text) > 0

    async def test_unknown_resource_raises_value_error(self) -> None:
        server = create_server(FakeInxr2Client())
        handler = server.request_handlers[ReadResourceRequest]
        with pytest.raises(ValueError, match="Unknown resource"):
            await handler(
                ReadResourceRequest(
                    method="resources/read",
                    params=ReadResourceRequestParams(uri=AnyUrl("inxr2://unknown")),
                )
            )
