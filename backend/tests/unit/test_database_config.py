"""
Unit tests for Database Configuration (REC-272)

Tests the database abstraction layer including:
- SQLite configuration
- PostgreSQL configuration
- Environment-based switching
"""

import pytest
import os
from unittest.mock import patch


class TestDatabaseURL:
    """Tests for database URL generation."""
    
    def test_default_sqlite(self):
        """Default should be SQLite when no DATABASE_URL."""
        with patch.dict(os.environ, {}, clear=True):
            # Need to reimport to get fresh config
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            url = db_module.get_database_url()
            assert "sqlite" in url
            assert "aiosqlite" in url
    
    def test_postgresql_from_database_url(self):
        """Should use PostgreSQL when DATABASE_URL is set."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://user:pass@host:5432/db"}, clear=True):
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            url = db_module.get_database_url()
            assert "postgresql+asyncpg" in url
            assert "host:5432" in url
    
    def test_postgresql_conversion(self):
        """postgres:// should be converted to postgresql+asyncpg://."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://user:pass@host:5432/db"}, clear=True):
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            url = db_module.get_database_url()
            assert url.startswith("postgresql+asyncpg://")
            assert not url.startswith("postgres://")
    
    def test_database_type_postgresql(self):
        """DATABASE_TYPE=postgresql should build PostgreSQL URL from components."""
        env = {
            "DATABASE_TYPE": "postgresql",
            "PGHOST": "db.example.com",
            "PGPORT": "5432",
            "PGUSER": "sigil",
            "PGPASSWORD": "secret",
            "PGDATABASE": "sigil_prod",
        }
        with patch.dict(os.environ, env, clear=True):
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            url = db_module.get_database_url()
            assert "postgresql+asyncpg" in url
            assert "db.example.com" in url
            assert "sigil_prod" in url


class TestEngineOptions:
    """Tests for SQLAlchemy engine options."""
    
    def test_sqlite_options(self):
        """SQLite should have minimal options."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            options = db_module.get_engine_options()
            assert "pool_size" not in options  # SQLite doesn't use pooling
    
    def test_postgresql_pool_options(self):
        """PostgreSQL should have pool configuration."""
        env = {
            "DATABASE_URL": "postgres://user:pass@host:5432/db",
            "DB_POOL_SIZE": "10",
            "DB_MAX_OVERFLOW": "20",
        }
        with patch.dict(os.environ, env, clear=True):
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            options = db_module.get_engine_options()
            assert options.get("pool_size") == 10
            assert options.get("max_overflow") == 20


class TestDatabaseInfo:
    """Tests for database info endpoint."""
    
    def test_database_info_sanitizes_password(self):
        """Password should be hidden in database info."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://user:secretpass@host:5432/db"}, clear=True):
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            info = db_module.get_database_info()
            assert "secretpass" not in info["url"]
            assert "***" in info["url"]
            assert info["type"] == "postgresql"
    
    def test_database_info_sqlite(self):
        """SQLite info should show type correctly."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import auth.database as db_module
            importlib.reload(db_module)
            
            info = db_module.get_database_info()
            assert info["type"] == "sqlite"


class TestIBKRConfigRemoval:
    """Tests for IBKR hardcoded credential removal."""
    
    def test_no_default_account_id(self):
        """IB_ACCOUNT_ID should not have a hardcoded default."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import ibkr.ibkr_service as ibkr_module
            importlib.reload(ibkr_module)
            
            # The IB_ACCOUNT_ID should be None when not set
            assert ibkr_module.IB_ACCOUNT_ID is None
    
    def test_account_id_from_env(self):
        """IB_ACCOUNT_ID should be read from environment."""
        with patch.dict(os.environ, {"IB_ACCOUNT_ID": "DU123456"}, clear=True):
            import importlib
            import ibkr.ibkr_service as ibkr_module
            importlib.reload(ibkr_module)
            
            assert ibkr_module.IB_ACCOUNT_ID == "DU123456"


class TestConfigRoutes:
    """Tests for configuration API routes."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
        
        from api.config_routes import config_router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(config_router)
        return TestClient(app)
    
    def test_get_llm_providers(self, client):
        """Should return list of available LLM providers."""
        response = client.get("/api/v1/config/llm/providers")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"]
        assert "providers" in data["data"]
        
        providers = data["data"]["providers"]
        provider_names = [p["provider"] for p in providers]
        assert "anthropic" in provider_names
        assert "openai" in provider_names
        assert "google" in provider_names
    
    def test_get_system_info(self, client):
        """Should return system configuration overview."""
        response = client.get("/api/v1/config/system")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"]
        assert "llm" in data["data"]
        assert "database" in data["data"]
        assert "ibkr" in data["data"]
    
    def test_get_database_info(self, client):
        """Should return database configuration info."""
        response = client.get("/api/v1/config/database")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"]
        assert "type" in data["data"]
