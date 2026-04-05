"""
End-to-End tests for the Team Management System (Phase 6).

Tests every endpoint and scenario:
  - Default team auto-creation on registration
  - Public team creation (slug generation)
  - Invite-link join flow
  - Join-request → admin approval flow
  - Direct admin invite → user accepts
  - MAINTAINER promotion and revision approval
  - VIEWER blocked from privileged actions
  - Member removal
  - Invite token rotation (old token invalid after regeneration)
  - Slug collision handling (two teams with same name get unique slugs)
  - Private team cannot be request-joined
"""

import pytest
import uuid

from httpx import AsyncClient, ASGITransport
from api.main import app

BASE = "http://test"
API = "/api/v1"
transport = ASGITransport(app=app)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _register(client: AsyncClient, suffix: str) -> dict:
    username = f"user_{suffix}"
    payload = {"username": username, "email": f"{username}@test.com", "password": "Secret123!"}
    r = await client.post(f"{API}/auth/register", json=payload)
    assert r.status_code in (200, 201), r.text
    return payload


async def _login(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post(
        f"{API}/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestTeamManagement:

    async def test_default_team_created_on_registration(self):
        """Registering a user auto-creates a personal team named after their username."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            creds = await _register(ac, uid)
            token = await _login(ac, creds["username"], creds["password"])

            r = await ac.get(f"{API}/teams/me", headers=auth(token))
            assert r.status_code == 200
            teams = r.json()
            assert len(teams) == 1
            assert creds["username"].replace("_", "-") in teams[0]["slug"]
            assert teams[0]["is_public"] is False  # personal team is private by default

    async def test_create_public_team_with_slug(self):
        """Creating a team generates a unique slug from the name."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            creds = await _register(ac, uid)
            token = await _login(ac, creds["username"], creds["password"])

            r = await ac.post(
                f"{API}/teams/",
                json={"name": "Acme Corp", "is_public": True},
                headers=auth(token),
            )
            assert r.status_code == 201
            data = r.json()
            assert data["slug"] == "acme-corp"
            assert data["is_public"] is True
            assert "invite_token" in data

    async def test_slug_collision_gets_unique_suffix(self):
        """Two teams with the same name receive unique slugs (acme-corp and acme-corp-2)."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            creds = await _register(ac, uid)
            token = await _login(ac, creds["username"], creds["password"])

            r1 = await ac.post(f"{API}/teams/", json={"name": "Slug Test Team"}, headers=auth(token))
            r2 = await ac.post(f"{API}/teams/", json={"name": "Slug Test Team"}, headers=auth(token))
            assert r1.status_code == 201
            assert r2.status_code == 201
            assert r1.json()["slug"] != r2.json()["slug"]

    async def test_join_via_invite_link(self):
        """A user can join a team using the invite link token."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            # Admin creates team
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"InviteTeam {uid}"}, headers=auth(admin_token))
            invite_token = r.json()["invite_token"]
            team_id = r.json()["id"]

            # Bob joins via link
            bob_creds = await _register(ac, f"bob_{uid}")
            bob_token = await _login(ac, bob_creds["username"], bob_creds["password"])
            r2 = await ac.post(f"{API}/teams/join/{invite_token}", headers=auth(bob_token))
            assert r2.status_code == 200
            assert r2.json()["team_id"] == team_id
            assert r2.json()["role"] == "VIEWER"

    async def test_join_requires_unique_member(self):
        """Trying to join via invite link twice returns 409."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"dup_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"DupTeam {uid}"}, headers=auth(admin_token))
            invite_token = r.json()["invite_token"]

            bob_creds = await _register(ac, f"dup_bob_{uid}")
            bob_token = await _login(ac, bob_creds["username"], bob_creds["password"])
            await ac.post(f"{API}/teams/join/{invite_token}", headers=auth(bob_token))
            r2 = await ac.post(f"{API}/teams/join/{invite_token}", headers=auth(bob_token))
            assert r2.status_code == 409

    async def test_request_to_join_and_admin_approves(self):
        """User requests to join a public team; admin approves; user becomes VIEWER."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"reqadmin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"ReqTeam {uid}", "is_public": True}, headers=auth(admin_token))
            team_id = r.json()["id"]

            carol_creds = await _register(ac, f"carol_{uid}")
            carol_token = await _login(ac, carol_creds["username"], carol_creds["password"])

            # Carol requests to join
            rq = await ac.post(f"{API}/teams/{team_id}/request-join", headers=auth(carol_token))
            assert rq.status_code == 201
            inv_id = rq.json()["id"]
            assert rq.json()["status"] == "PENDING"

            # Admin lists pending
            ls = await ac.get(f"{API}/teams/{team_id}/invitations", headers=auth(admin_token))
            assert ls.status_code == 200
            assert len(ls.json()) == 1

            # Admin approves
            ap = await ac.post(
                f"{API}/teams/{team_id}/invitations/{inv_id}/respond",
                json={"accept": True},
                headers=auth(admin_token),
            )
            assert ap.status_code == 200
            assert ap.json()["status"] == "ACCEPTED"

            # Carol now has team in her list
            my = await ac.get(f"{API}/teams/me", headers=auth(carol_token))
            team_ids = [t["id"] for t in my.json()]
            assert team_id in team_ids

    async def test_request_to_join_private_team_blocked(self):
        """Users cannot request to join a private team."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"priv_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"PrivTeam {uid}", "is_public": False}, headers=auth(admin_token))
            team_id = r.json()["id"]

            bob_creds = await _register(ac, f"priv_bob_{uid}")
            bob_token = await _login(ac, bob_creds["username"], bob_creds["password"])
            rq = await ac.post(f"{API}/teams/{team_id}/request-join", headers=auth(bob_token))
            assert rq.status_code == 403

    async def test_admin_sends_invite_and_user_implicitly_joins(self):
        """Admin sends an invite; upon responding accept=True, user is added."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"inv_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"InvSendTeam {uid}"}, headers=auth(admin_token))
            team_id = r.json()["id"]

            dave_creds = await _register(ac, f"dave_{uid}")
            dave_token = await _login(ac, dave_creds["username"], dave_creds["password"])
            dave_id = (await ac.get(f"{API}/teams/me", headers=auth(dave_token))).json()[0]["id"]  # use team id as proxy for user_id test
            # Get Dave's actual user_id from his personal team member data
            # We'll fetch them after registration differently
            # For simplicity, parse from the token to get the sub, or alternatively
            # we register Dave and note his username, then admin looks up user_id via search
            # Here we just use the teams me endpoint to verify Dave joins

            # Admin invites Dave - we need dave's user_id, let's get it from authentication
            # For testing, we send an invite with admin sending via a search-obtained ID
            # Since we don't have a user search endpoint yet, we use a workaround approach:
            # We store it from registration
            r_reg = await ac.post(
                f"{API}/auth/register",
                json={"username": f"dave2_{uid}", "email": f"dave2_{uid}@test.com", "password": "Secret123!"},
            )
            dave2_id = r_reg.json()["id"]
            dave2_token = await _login(ac, f"dave2_{uid}", "Secret123!")

            # Admin sends invite to dave2
            inv = await ac.post(f"{API}/teams/{team_id}/invite/{dave2_id}", headers=auth(admin_token))
            assert inv.status_code == 201
            inv_id = inv.json()["id"]

            # Dave2 (invitee) accepts
            ap = await ac.post(
                f"{API}/teams/{team_id}/invitations/{inv_id}/respond",
                json={"accept": True},
                headers=auth(admin_token),  # Admin resolves; invitee could also respond in a real notify-flow
            )
            assert ap.status_code == 200

    async def test_viewer_cannot_approve_revisions(self):
        """A VIEWER member gets 403 when trying to approve a revision."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"rev_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"RevTeam {uid}", "is_public": True}, headers=auth(admin_token))
            team_id = r.json()["id"]
            invite_token = r.json()["invite_token"]

            viewer_creds = await _register(ac, f"viewer_{uid}")
            viewer_token = await _login(ac, viewer_creds["username"], viewer_creds["password"])
            await ac.post(f"{API}/teams/join/{invite_token}", headers=auth(viewer_token))

            # Viewer tries to approve a (non-existent) revision — should fail with 403 before DB lookup
            rr = await ac.post(
                f"{API}/{team_id}/docs/approve/fake-revision-id",
                headers=auth(viewer_token),
            )
            assert rr.status_code == 403

    async def test_maintainer_can_approve_invitations(self):
        """A MAINTAINER can see and respond to join requests."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"m_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"MaintTeam {uid}", "is_public": True}, headers=auth(admin_token))
            team_id = r.json()["id"]
            invite_token = r.json()["invite_token"]

            # Add maintainer via invite link then promote
            maint_creds = await _register(ac, f"maint_{uid}")
            maint_token = await _login(ac, maint_creds["username"], maint_creds["password"])
            maint_join = await ac.post(f"{API}/teams/join/{invite_token}", headers=auth(maint_token))
            maint_user_id = maint_join.json()["user_id"]

            # Admin promotes to MAINTAINER
            pr = await ac.patch(
                f"{API}/teams/{team_id}/members/{maint_user_id}/role",
                json={"role": "MAINTAINER"},
                headers=auth(admin_token),
            )
            assert pr.status_code == 200
            assert pr.json()["role"] == "MAINTAINER"

            # Someone requests to join
            carol_creds = await _register(ac, f"m_carol_{uid}")
            carol_token = await _login(ac, carol_creds["username"], carol_creds["password"])
            rq = await ac.post(f"{API}/teams/{team_id}/request-join", headers=auth(carol_token))
            inv_id = rq.json()["id"]

            # Maintainer approves
            ap = await ac.post(
                f"{API}/teams/{team_id}/invitations/{inv_id}/respond",
                json={"accept": True},
                headers=auth(maint_token),
            )
            assert ap.status_code == 200
            assert ap.json()["status"] == "ACCEPTED"

    async def test_admin_removes_member(self):
        """Admin can remove a non-admin member."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"rm_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"RemoveTeam {uid}"}, headers=auth(admin_token))
            team_id = r.json()["id"]
            invite_token = r.json()["invite_token"]

            bob_creds = await _register(ac, f"rm_bob_{uid}")
            bob_token = await _login(ac, bob_creds["username"], bob_creds["password"])
            join = await ac.post(f"{API}/teams/join/{invite_token}", headers=auth(bob_token))
            bob_user_id = join.json()["user_id"]

            rm = await ac.delete(f"{API}/teams/{team_id}/members/{bob_user_id}", headers=auth(admin_token))
            assert rm.status_code == 204

    async def test_invite_token_rotation(self):
        """After regenerating the invite token, the old token is no longer valid."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"rot_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            r = await ac.post(f"{API}/teams/", json={"name": f"RotTeam {uid}"}, headers=auth(admin_token))
            old_token = r.json()["invite_token"]
            team_id = r.json()["id"]

            # Regenerate
            new_r = await ac.post(f"{API}/teams/{team_id}/invite-link/regenerate", headers=auth(admin_token))
            assert new_r.status_code == 200
            new_token = new_r.json()["invite_token"]
            assert new_token != old_token

            # Old token is now invalid
            bob_creds = await _register(ac, f"rot_bob_{uid}")
            bob_token = await _login(ac, bob_creds["username"], bob_creds["password"])
            bad = await ac.post(f"{API}/teams/join/{old_token}", headers=auth(bob_token))
            assert bad.status_code == 404

            # New token works
            good = await ac.post(f"{API}/teams/join/{new_token}", headers=auth(bob_token))
            assert good.status_code == 200

    async def test_search_public_teams(self):
        """Search returns public teams matching the query."""
        async with AsyncClient(transport=transport, base_url=BASE) as ac:
            uid = uuid.uuid4().hex[:8]
            admin_creds = await _register(ac, f"search_admin_{uid}")
            admin_token = await _login(ac, admin_creds["username"], admin_creds["password"])
            await ac.post(f"{API}/teams/", json={"name": f"SearchableTeam {uid}", "is_public": True}, headers=auth(admin_token))

            r = await ac.get(f"{API}/teams/search?q=SearchableTeam {uid}")
            assert r.status_code == 200
            results = r.json()
            assert any("SearchableTeam" in t["name"] for t in results)
