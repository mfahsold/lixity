"""Managed-service examples parse without operating on local services."""

import argparse
import shlex

import pytest

from lixity import cli, service


@pytest.mark.parametrize("action", [None, "start", "stop", "restart", "status"])
def test_service_help_exits_before_runtime_or_environment_validation(action, monkeypatch, capsys):
    def unexpected_runtime(*args, **kwargs):
        pytest.fail("Help must not inspect or control a service")

    monkeypatch.setattr(service, "run", unexpected_runtime)
    monkeypatch.setenv("LIXITY_PORT", "not-a-port")
    argv = ["service", *([action] if action else []), "--help"]
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 0
    output = capsys.readouterr()
    assert not output.err
    assert "Examples:" in output.out
    assert "--_service-token" not in output.out


def test_service_help_examples_cover_lifecycle_and_parse_without_dispatch():
    parser = argparse.ArgumentParser(prog="lixity service")
    service.configure(parser)
    examples = [
        shlex.split(line.strip())[2:]
        for line in parser.epilog.splitlines()
        if line.strip().startswith("lixity service ")
    ]
    parsed = [parser.parse_args(example) for example in examples]
    actions = {"start", "stop", "restart", "status"}
    assert {args.action for args in parsed} == actions
    assert {args.action for args in parsed if args.port == 8766} == actions
    assert any(args.action == "start" and args.project and args.open_browser for args in parsed)
    assert any(args.action == "status" and args.json for args in parsed)

    # An omitted override must remain distinguishable from an explicit value,
    # so restart can retain the settings described by the help.
    restart = next(args for args in parsed if args.action == "restart" and args.port == 8766)
    assert restart.project is None
    assert restart.host is None
    assert restart.language is None
    assert restart.open_browser is None
    assert restart.backend == "auto"
