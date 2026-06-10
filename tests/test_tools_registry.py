"""Tests for the central tool registry / dispatcher."""

from __future__ import annotations

from pathlib import Path

from llm_file_assistant import tools_registry


class TestToolsRegistry:
    def test_descriptors_include_all_four_tools(self, sandbox: Path) -> None:
        names = {d.name for d in tools_registry.all_descriptors()}
        assert names == {"read_file", "list_files", "write_file", "search_in_file"}

    def test_each_descriptor_has_schema(self, sandbox: Path) -> None:
        for descriptor in tools_registry.all_descriptors():
            assert descriptor.description
            assert descriptor.parameters.properties
            assert isinstance(descriptor.parameters.required, list)

    def test_execute_with_dict_args(self, sandbox: Path) -> None:
        (sandbox / "x.txt").write_text("hi", encoding="utf-8")
        result = tools_registry.execute("read_file", {"filepath": "x.txt"})
        assert result["status"] == "success"

    def test_execute_with_json_string_args(self, sandbox: Path) -> None:
        (sandbox / "x.txt").write_text("hi", encoding="utf-8")
        result = tools_registry.execute("read_file", '{"filepath": "x.txt"}')
        assert result["status"] == "success"

    def test_execute_invalid_json_string(self, sandbox: Path) -> None:
        result = tools_registry.execute("read_file", "{not json}")
        assert result["status"] == "error"
        assert result["error_type"] == "InvalidArgumentsError"

    def test_execute_unknown_tool(self, sandbox: Path) -> None:
        result = tools_registry.execute("delete_internet", {})
        assert result["status"] == "error"
        assert result["error_type"] == "UnknownToolError"

    def test_execute_bad_kwargs(self, sandbox: Path) -> None:
        result = tools_registry.execute("read_file", {"wrong_kw": "x"})
        assert result["status"] == "error"
        assert result["error_type"] == "InvalidArgumentsError"

    def test_execute_with_empty_string_args(self, sandbox: Path) -> None:
        result = tools_registry.execute("list_files", "")
        # No args -> TypeError -> InvalidArgumentsError
        assert result["status"] == "error"
