from app.config import Settings


def test_defaults_match_spec() -> None:
    s = Settings(_env_file=None)
    assert s.signup_grant == 100_000
    assert s.daily_bonus == 50_000
    assert s.rescue_amount == 20_000
    assert s.rescue_max_per_day == 3
    assert s.rescue_threshold == 200
    assert s.game_timezone == "Asia/Dhaka"
    assert (s.betting_seconds, s.spinning_seconds, s.results_seconds) == (15, 3, 3)


def test_env_override(monkeypatch) -> None:
    monkeypatch.setenv("DAILY_BONUS", "12345")
    assert Settings(_env_file=None).daily_bonus == 12345
