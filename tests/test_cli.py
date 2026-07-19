import pytest

from propeller_vision.cli import DEFAULT_SOCKET_PATH, parse_args


def test_socket_defaults_when_no_flag_or_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROPELLER_SOCK", raising=False)

    args = parse_args([])

    assert args.socket == DEFAULT_SOCKET_PATH


def test_socket_reads_from_propeller_sock_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROPELLER_SOCK", "/tmp/custom.sock")

    args = parse_args([])

    assert args.socket == "/tmp/custom.sock"


def test_socket_flag_overrides_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROPELLER_SOCK", "/tmp/from-env.sock")

    args = parse_args(["--socket", "/tmp/from-flag.sock"])

    assert args.socket == "/tmp/from-flag.sock"


def test_view_defaults_to_dashboard() -> None:
    args = parse_args([])

    assert args.view == "dashboard"


def test_view_accepts_plasma() -> None:
    args = parse_args(["--view", "plasma"])

    assert args.view == "plasma"


def test_view_rejects_unknown_value() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--view", "not-a-real-view"])


def test_position_interval_defaults_to_100ms() -> None:
    args = parse_args([])

    assert args.position_interval == pytest.approx(0.1)


def test_position_interval_is_overridable() -> None:
    args = parse_args(["--position-interval", "0.05"])

    assert args.position_interval == pytest.approx(0.05)


def test_status_interval_defaults_to_1s() -> None:
    args = parse_args([])

    assert args.status_interval == pytest.approx(1.0)


def test_status_interval_is_overridable() -> None:
    args = parse_args(["--status-interval", "2.5"])

    assert args.status_interval == pytest.approx(2.5)


def test_debug_defaults_to_false() -> None:
    args = parse_args([])

    assert args.debug is False


def test_debug_flag_enables_debug() -> None:
    args = parse_args(["--debug"])

    assert args.debug is True
