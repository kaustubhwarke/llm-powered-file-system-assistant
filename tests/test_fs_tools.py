"""Unit tests for the four core file system tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_file_assistant.fs_tools import (
    list_files,
    read_file,
    search_in_file,
    write_file,
)


# ----------------------------------------------------------------------
# read_file
# ----------------------------------------------------------------------


class TestReadFile:
    def test_reads_plain_text(self, sandbox: Path) -> None:
        (sandbox / "note.txt").write_text("hello world", encoding="utf-8")
        result = read_file("note.txt")
        assert result["status"] == "success"
        assert result["content"] == "hello world"
        assert result["metadata"]["name"] == "note.txt"
        assert result["metadata"]["extension"] == ".txt"
        assert result["metadata"]["size_bytes"] == 11

    def test_reads_markdown(self, sandbox: Path) -> None:
        (sandbox / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
        result = read_file("doc.md")
        assert result["status"] == "success"
        assert "Title" in result["content"]

    def test_handles_utf8_bom(self, sandbox: Path) -> None:
        (sandbox / "bom.txt").write_bytes(b"\xef\xbb\xbfwith bom")
        result = read_file("bom.txt")
        assert result["status"] == "success"
        assert result["content"].endswith("with bom")

    def test_falls_back_to_latin1(self, sandbox: Path) -> None:
        (sandbox / "latin.txt").write_bytes(b"caf\xe9")
        result = read_file("latin.txt")
        assert result["status"] == "success"
        assert "caf" in result["content"]

    def test_missing_file_returns_error(self, sandbox: Path) -> None:
        result = read_file("missing.txt")
        assert result["status"] == "error"
        assert result["error_type"] == "FileNotFoundInSandboxError"

    def test_directory_target_returns_error(self, sandbox: Path) -> None:
        (sandbox / "subdir").mkdir()
        result = read_file("subdir")
        assert result["status"] == "error"

    def test_rejects_path_traversal(self, sandbox: Path) -> None:
        result = read_file("../../etc/passwd")
        assert result["status"] == "error"
        assert result["error_type"] == "PathSecurityError"

    def test_rejects_absolute_outside_sandbox(self, sandbox: Path) -> None:
        result = read_file("/etc/passwd")
        assert result["status"] == "error"

    def test_unsupported_extension(self, sandbox: Path) -> None:
        (sandbox / "binary.bin").write_bytes(b"\x00\x01\x02")
        result = read_file("binary.bin")
        assert result["status"] == "error"
        assert result["error_type"] == "UnsupportedFileTypeError"

    def test_oversized_file_rejected(
        self, sandbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from llm_file_assistant.config import reset_settings_cache

        monkeypatch.setenv("FS_MAX_FILE_BYTES", "10")
        reset_settings_cache()
        (sandbox / "big.txt").write_text("x" * 100, encoding="utf-8")
        result = read_file("big.txt")
        assert result["status"] == "error"
        assert result["error_type"] == "FileTooLargeError"


# ----------------------------------------------------------------------
# list_files
# ----------------------------------------------------------------------


class TestListFiles:
    def test_lists_all_files(self, sandbox: Path) -> None:
        (sandbox / "a.txt").write_text("a", encoding="utf-8")
        (sandbox / "b.pdf").write_bytes(b"pdf")
        (sandbox / "c.docx").write_bytes(b"docx")
        result = list_files(".")
        assert result["status"] == "success"
        assert result["count"] == 3
        names = [f["name"] for f in result["files"]]
        assert set(names) == {"a.txt", "b.pdf", "c.docx"}

    def test_filters_by_extension_with_dot(self, sandbox: Path) -> None:
        (sandbox / "a.txt").write_text("a", encoding="utf-8")
        (sandbox / "b.pdf").write_bytes(b"pdf")
        result = list_files(".", extension=".pdf")
        assert result["count"] == 1
        assert result["files"][0]["name"] == "b.pdf"

    def test_filters_by_extension_without_dot(self, sandbox: Path) -> None:
        (sandbox / "a.txt").write_text("a", encoding="utf-8")
        (sandbox / "b.pdf").write_bytes(b"pdf")
        result = list_files(".", extension="pdf")
        assert result["count"] == 1

    def test_skips_subdirectories(self, sandbox: Path) -> None:
        (sandbox / "a.txt").write_text("a", encoding="utf-8")
        (sandbox / "sub").mkdir()
        (sandbox / "sub" / "nested.txt").write_text("n", encoding="utf-8")
        result = list_files(".")
        assert result["count"] == 1

    def test_missing_directory(self, sandbox: Path) -> None:
        result = list_files("nope")
        assert result["status"] == "error"

    def test_empty_directory(self, sandbox: Path) -> None:
        (sandbox / "empty").mkdir()
        result = list_files("empty")
        assert result["status"] == "success"
        assert result["count"] == 0

    def test_traversal_blocked(self, sandbox: Path) -> None:
        result = list_files("../..")
        assert result["status"] == "error"
        assert result["error_type"] == "PathSecurityError"


# ----------------------------------------------------------------------
# write_file
# ----------------------------------------------------------------------


class TestWriteFile:
    def test_writes_new_file(self, sandbox: Path) -> None:
        result = write_file("hello.txt", "hello")
        assert result["status"] == "success"
        assert result["bytes_written"] == 5
        assert (sandbox / "hello.txt").read_text(encoding="utf-8") == "hello"

    def test_creates_parent_directories(self, sandbox: Path) -> None:
        result = write_file("nested/deep/file.txt", "content")
        assert result["status"] == "success"
        assert result["created_directories"] is True
        assert (sandbox / "nested" / "deep" / "file.txt").exists()

    def test_overwrites_existing(self, sandbox: Path) -> None:
        (sandbox / "f.txt").write_text("old", encoding="utf-8")
        result = write_file("f.txt", "new")
        assert result["status"] == "success"
        assert result["overwritten"] is True
        assert (sandbox / "f.txt").read_text(encoding="utf-8") == "new"

    def test_unicode_content_preserved(self, sandbox: Path) -> None:
        result = write_file("u.txt", "héllo — wörld 🚀")
        assert result["status"] == "success"
        assert (sandbox / "u.txt").read_text(encoding="utf-8") == "héllo — wörld 🚀"

    def test_traversal_blocked(self, sandbox: Path) -> None:
        result = write_file("../escape.txt", "x")
        assert result["status"] == "error"
        assert result["error_type"] == "PathSecurityError"

    def test_rejects_directory_target(self, sandbox: Path) -> None:
        (sandbox / "adir").mkdir()
        result = write_file("adir", "x")
        assert result["status"] == "error"

    def test_size_limit_enforced(
        self, sandbox: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from llm_file_assistant.config import reset_settings_cache

        monkeypatch.setenv("FS_MAX_FILE_BYTES", "5")
        reset_settings_cache()
        result = write_file("big.txt", "x" * 100)
        assert result["status"] == "error"
        assert result["error_type"] == "FileTooLargeError"


# ----------------------------------------------------------------------
# search_in_file
# ----------------------------------------------------------------------


class TestSearchInFile:
    def test_finds_matches_case_insensitive(self, sandbox: Path) -> None:
        (sandbox / "r.txt").write_text(
            "line one\nPython is great\npython is everywhere\nthe end",
            encoding="utf-8",
        )
        result = search_in_file("r.txt", "python")
        assert result["status"] == "success"
        assert result["match_count"] == 2
        assert result["matches"][0]["line_number"] == 2

    def test_includes_context(self, sandbox: Path) -> None:
        content = "\n".join(f"line {i}" for i in range(10))
        (sandbox / "r.txt").write_text(content, encoding="utf-8")
        # 'line 5' is on row index 5 -> line_number 6
        result = search_in_file("r.txt", "line 5", context_lines=2)
        assert result["status"] == "success"
        match = result["matches"][0]
        assert match["context_before"] == ["line 3", "line 4"]
        assert match["context_after"] == ["line 6", "line 7"]

    def test_no_matches(self, sandbox: Path) -> None:
        (sandbox / "r.txt").write_text("nothing here", encoding="utf-8")
        result = search_in_file("r.txt", "absent")
        assert result["status"] == "success"
        assert result["match_count"] == 0
        assert result["matches"] == []

    def test_empty_keyword_rejected(self, sandbox: Path) -> None:
        (sandbox / "r.txt").write_text("x", encoding="utf-8")
        result = search_in_file("r.txt", "")
        assert result["status"] == "error"

    def test_missing_file_propagates_error(self, sandbox: Path) -> None:
        result = search_in_file("missing.txt", "x")
        assert result["status"] == "error"

    def test_traversal_blocked(self, sandbox: Path) -> None:
        result = search_in_file("../../etc/passwd", "root")
        assert result["status"] == "error"
        assert result["error_type"] == "PathSecurityError"

    def test_invalid_context_lines_rejected(self, sandbox: Path) -> None:
        (sandbox / "r.txt").write_text("foo", encoding="utf-8")
        result = search_in_file("r.txt", "foo", context_lines=99)
        assert result["status"] == "error"
