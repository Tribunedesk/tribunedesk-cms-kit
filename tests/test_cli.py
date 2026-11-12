import pytest

from tdkit.cli import main


def test_cli_version_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "tdkit 1.0.0"


def test_cli_unknown_command_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["frobnicate"])
    assert exc.value.code == 2


def test_mock_token_scopes_narrow_the_default_token() -> None:
    from tdkit.cli import build_parser, mock_state

    args = build_parser().parse_args(["mock", "--token-scopes", "articles:read,articles:write"])
    assert mock_state(args).tokens == {"tdcms_mock": {"articles:read", "articles:write"}}


def test_mock_unknown_scope_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(["mock", "--token-scopes", "media:everything", "--docs", "tests/fixtures/cms-api"])
        == 2
    )
    assert "media:everything" in capsys.readouterr().err
