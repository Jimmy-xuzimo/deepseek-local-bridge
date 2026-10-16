from app.__main__ import _normalize_argv


def test_normalize_argv_defaults_to_run():
    assert _normalize_argv([]) == ["run"]


def test_normalize_argv_adds_run_for_options_only():
    assert _normalize_argv(["--open-admin"]) == ["run", "--open-admin"]
    assert _normalize_argv(["--port", "8318"]) == ["run", "--port", "8318"]
    assert _normalize_argv(["--no-browser"]) == ["run", "--no-browser"]


def test_normalize_argv_keeps_subcommands():
    assert _normalize_argv(["doctor"]) == ["doctor"]
    assert _normalize_argv(["run", "--port", "8317"]) == ["run", "--port", "8317"]


def test_normalize_argv_keeps_help():
    assert _normalize_argv(["--help"]) == ["--help"]
    assert _normalize_argv(["-h"]) == ["-h"]
