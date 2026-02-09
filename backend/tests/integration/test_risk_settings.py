"""
Integration tests for Risk Settings API

REC-222: Phase 1 Integration Tests
Tests for risk settings CRUD and IBKR integration.
"""

import pytest
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def app():
    """Create test app instance."""
    from api.main import app
    return app


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_headers(client):
    """Get auth headers for authenticated requests."""
    # First, register a test user
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "risktest@example.com",
            "password": "TestPassword123!",
            "full_name": "Risk Test User",
        }
    )
    
    # If user already exists, login instead
    if register_response.status_code != 200:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "risktest@example.com",
                "password": "TestPassword123!",
            }
        )
        data = login_response.json()
    else:
        data = register_response.json()
    
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    if not token:
        pytest.skip("Could not get auth token")
    
    return {"Authorization": f"Bearer {token}"}


class TestRiskSettingsGet:
    """Tests for GET /api/v1/user/risk-settings."""
    
    @pytest.mark.anyio
    async def test_get_default_settings(self, client, auth_headers):
        """New user should get default settings (all OFF)."""
        response = await client.get(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        settings = data["data"]
        
        # All protections should be OFF by default
        assert settings["hard_stop"]["enabled"] is False
        assert settings["trailing_stop"]["enabled"] is False
        assert settings["vix_adjustment"]["enabled"] is False
        assert settings["position_limit"]["enabled"] is False
        
        # Default thresholds
        assert settings["hard_stop"]["threshold_pct"] == -0.08
        assert settings["trailing_stop"]["distance_pct"] == -0.10
        assert settings["position_limit"]["max_pct"] == 0.15
    
    @pytest.mark.anyio
    async def test_get_settings_unauthorized(self, client):
        """Should reject unauthenticated requests."""
        response = await client.get("/api/v1/user/risk-settings")
        
        # Should be 401 or 403 depending on auth config
        assert response.status_code in [401, 403]


class TestRiskSettingsPut:
    """Tests for PUT /api/v1/user/risk-settings."""
    
    @pytest.mark.anyio
    async def test_enable_hard_stop(self, client, auth_headers):
        """Should enable hard stop-loss."""
        response = await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={
                "hard_stop": {
                    "enabled": True,
                    "threshold_pct": -0.10,
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["hard_stop"]["enabled"] is True
        assert data["data"]["hard_stop"]["threshold_pct"] == -0.10
    
    @pytest.mark.anyio
    async def test_enable_trailing_stop(self, client, auth_headers):
        """Should enable trailing stop-loss."""
        response = await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={
                "trailing_stop": {
                    "enabled": True,
                    "distance_pct": -0.15,
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["trailing_stop"]["enabled"] is True
        assert data["data"]["trailing_stop"]["distance_pct"] == -0.15
    
    @pytest.mark.anyio
    async def test_enable_all_protections(self, client, auth_headers):
        """Should enable all protections at once."""
        response = await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={
                "hard_stop": {"enabled": True, "threshold_pct": -0.08},
                "trailing_stop": {"enabled": True, "distance_pct": -0.12},
                "vix_adjustment": {"enabled": True},
                "position_limit": {"enabled": True, "max_pct": 0.20},
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["hard_stop"]["enabled"] is True
        assert data["data"]["trailing_stop"]["enabled"] is True
        assert data["data"]["vix_adjustment"]["enabled"] is True
        assert data["data"]["position_limit"]["enabled"] is True
    
    @pytest.mark.anyio
    async def test_partial_update(self, client, auth_headers):
        """Should only update specified fields."""
        # First enable hard stop
        await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={"hard_stop": {"enabled": True, "threshold_pct": -0.08}}
        )
        
        # Now update only trailing stop
        response = await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={"trailing_stop": {"enabled": True, "distance_pct": -0.15}}
        )
        
        data = response.json()
        
        # Hard stop should still be enabled
        assert data["data"]["hard_stop"]["enabled"] is True
        assert data["data"]["trailing_stop"]["enabled"] is True
    
    @pytest.mark.anyio
    async def test_invalid_hard_stop_threshold(self, client, auth_headers):
        """Should reject invalid hard stop threshold."""
        response = await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={
                "hard_stop": {
                    "enabled": True,
                    "threshold_pct": -0.50,  # Invalid: outside -5% to -20%
                }
            }
        )
        
        # Should return 400 or 422 for validation error
        assert response.status_code in [400, 422]
    
    @pytest.mark.anyio
    async def test_invalid_trailing_stop_distance(self, client, auth_headers):
        """Should reject invalid trailing stop distance."""
        response = await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={
                "trailing_stop": {
                    "enabled": True,
                    "distance_pct": -0.01,  # Invalid: outside -5% to -25%
                }
            }
        )
        
        assert response.status_code in [400, 422]
    
    @pytest.mark.anyio
    async def test_invalid_position_limit(self, client, auth_headers):
        """Should reject invalid position limit."""
        response = await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={
                "position_limit": {
                    "enabled": True,
                    "max_pct": 0.50,  # Invalid: outside 5% to 30%
                }
            }
        )
        
        assert response.status_code in [400, 422]


class TestRiskSettingsReset:
    """Tests for POST /api/v1/user/risk-settings/reset."""
    
    @pytest.mark.anyio
    async def test_reset_to_defaults(self, client, auth_headers):
        """Should reset all settings to defaults."""
        # First enable some protections
        await client.put(
            "/api/v1/user/risk-settings",
            headers=auth_headers,
            json={
                "hard_stop": {"enabled": True},
                "trailing_stop": {"enabled": True},
            }
        )
        
        # Now reset
        response = await client.post(
            "/api/v1/user/risk-settings/reset",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All should be OFF again
        assert data["data"]["hard_stop"]["enabled"] is False
        assert data["data"]["trailing_stop"]["enabled"] is False
        assert data["data"]["vix_adjustment"]["enabled"] is False
        assert data["data"]["position_limit"]["enabled"] is False


class TestRiskSettingsDefaults:
    """Tests for GET /api/v1/user/risk-settings/defaults."""
    
    @pytest.mark.anyio
    async def test_get_defaults_no_auth(self, client):
        """Should return defaults without authentication."""
        response = await client.get("/api/v1/user/risk-settings/defaults")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        settings = data["data"]
        
        # All OFF by default
        assert settings["hard_stop"]["enabled"] is False
        assert settings["trailing_stop"]["enabled"] is False
        assert settings["vix_adjustment"]["enabled"] is False
        assert settings["position_limit"]["enabled"] is False
