"""EXHAUSTIVE permission matrix tests (spec B1) — every actor×target×VIP combo."""

import itertools

import pytest

from app.services import permissions as p

ROLES = [p.OWNER, p.ADMIN, p.USER]
VIP_TIERS = range(6)  # 0..5


@pytest.mark.parametrize("actor,target,tier", itertools.product(ROLES, ROLES, VIP_TIERS))
def test_kick_matrix(actor, target, tier):
    verdict = p.can_kick(actor, target, tier)
    if target == p.OWNER:
        assert verdict == "forbidden"          # nobody kicks the owner
    elif actor == p.OWNER:
        assert verdict == "ok"                 # owner kicks anyone (incl. admins, VIPs)
    elif actor == p.ADMIN and target == p.USER:
        assert verdict == ("anti_kick" if tier >= 3 else "ok")  # VIP3+ Anti-Kick
    else:
        assert verdict == "forbidden"          # admin→admin, user→anyone


@pytest.mark.parametrize("actor,target", itertools.product(ROLES, ROLES))
def test_mute_matrix(actor, target):
    verdict = p.can_mute(actor, target)
    if target == p.OWNER:
        assert verdict == "forbidden"
    elif actor == p.OWNER or (actor == p.ADMIN and target == p.USER):
        assert verdict == "ok"                 # Anti-Kick does NOT protect from mutes
    else:
        assert verdict == "forbidden"


@pytest.mark.parametrize("actor,target", itertools.product(ROLES, ROLES))
def test_chat_ban_matrix(actor, target):
    verdict = p.can_chat_ban(actor, target)
    if target == p.OWNER:
        assert verdict == "forbidden"
    elif actor == p.OWNER or (actor == p.ADMIN and target == p.USER):
        assert verdict == "ok"
    else:
        assert verdict == "forbidden"


@pytest.mark.parametrize("actor,target", itertools.product(ROLES, ROLES))
def test_block_matrix(actor, target):
    verdict = p.can_block(actor, target)
    # Owner-only, against anyone but themselves; overrides Anti-Kick by design.
    assert verdict == ("ok" if actor == p.OWNER and target != p.OWNER else "forbidden")


@pytest.mark.parametrize("actor", ROLES)
def test_owner_only_powers(actor):
    expected = "ok" if actor == p.OWNER else "forbidden"
    assert p.can_grant_admin(actor) == expected
    assert p.can_close_table(actor) == expected
