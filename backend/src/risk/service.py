"""
Risk Settings Service

Handles persistence and IBKR order synchronization for user risk settings.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone

from auth.database import Base
from .models import UserRiskSettings

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


class UserRiskSettingsDB(Base):
    """SQLAlchemy model for user risk settings."""
    __tablename__ = "user_risk_settings"

    user_id = Column(String(36), primary_key=True)
    settings_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


class RiskSettingsService:
    """
    Service for managing user risk settings.
    
    Responsibilities:
    - CRUD operations for risk settings
    - Validation
    - IBKR order synchronization (when settings change)
    """

    @staticmethod
    async def get_settings(db: AsyncSession, user_id: str) -> UserRiskSettings:
        """
        Get user's risk settings, or return defaults if none exist.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            UserRiskSettings with user's preferences or defaults
        """
        result = await db.execute(
            select(UserRiskSettingsDB).where(UserRiskSettingsDB.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        
        if row is None:
            # Return default settings (all OFF)
            return UserRiskSettings.default(user_id)
        
        return UserRiskSettings.from_json(user_id, row.settings_json)

    @staticmethod
    async def save_settings(
        db: AsyncSession,
        user_id: str,
        settings: UserRiskSettings,
        sync_ibkr: bool = True,
    ) -> UserRiskSettings:
        """
        Save user's risk settings and optionally sync IBKR orders.
        
        Args:
            db: Database session
            user_id: User ID
            settings: New settings to save
            sync_ibkr: Whether to sync IBKR stop orders
            
        Returns:
            Saved UserRiskSettings
            
        Raises:
            ValueError: If settings validation fails
        """
        # Validate settings
        settings.validate()
        
        # Check if record exists
        result = await db.execute(
            select(UserRiskSettingsDB).where(UserRiskSettingsDB.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        
        settings_json = settings.to_json()
        
        if existing:
            existing.settings_json = settings_json
            existing.updated_at = _utcnow()
        else:
            new_record = UserRiskSettingsDB(
                user_id=user_id,
                settings_json=settings_json,
            )
            db.add(new_record)
        
        await db.commit()
        
        # Sync IBKR orders if requested
        if sync_ibkr:
            await RiskSettingsService._sync_ibkr_stops(db, user_id, settings)
        
        logger.info(f"Saved risk settings for user {user_id}")
        return settings

    @staticmethod
    async def update_settings(
        db: AsyncSession,
        user_id: str,
        updates: Dict[str, Any],
        sync_ibkr: bool = True,
    ) -> UserRiskSettings:
        """
        Partially update user's risk settings.
        
        Args:
            db: Database session
            user_id: User ID
            updates: Partial updates to apply
            sync_ibkr: Whether to sync IBKR stop orders
            
        Returns:
            Updated UserRiskSettings
        """
        # Get current settings
        current = await RiskSettingsService.get_settings(db, user_id)
        
        # Merge updates
        current_dict = current.to_dict()
        for key, value in updates.items():
            if key in current_dict and key != "user_id":
                if isinstance(value, dict) and isinstance(current_dict[key], dict):
                    current_dict[key].update(value)
                else:
                    current_dict[key] = value
        
        # Create new settings from merged data
        new_settings = UserRiskSettings.from_dict(user_id, current_dict)
        
        # Save
        return await RiskSettingsService.save_settings(db, user_id, new_settings, sync_ibkr)

    @staticmethod
    async def reset_to_defaults(db: AsyncSession, user_id: str) -> UserRiskSettings:
        """
        Reset user's risk settings to defaults (all OFF).
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Default UserRiskSettings
        """
        defaults = UserRiskSettings.default(user_id)
        return await RiskSettingsService.save_settings(db, user_id, defaults, sync_ibkr=True)

    @staticmethod
    async def _sync_ibkr_stops(
        db: AsyncSession,
        user_id: str,
        settings: UserRiskSettings,
    ) -> None:
        """
        Synchronize IBKR stop orders with user's settings.
        
        Called when settings change to:
        - Place/update stop orders if enabled
        - Cancel stop orders if disabled
        
        Args:
            db: Database session
            user_id: User ID
            settings: Current risk settings
        """
        try:
            from .ibkr_orders import IBKRStopOrderManager
            
            # Get IBKR connection (use singleton to avoid blocking)
            from ibkr.ibkr_service import get_ibkr_service
            ibkr = get_ibkr_service()
            
            if not ibkr.is_connected(user_id):
                logger.warning(f"IBKR not connected, skipping stop order sync for user {user_id}")
                return
            
            # Get user's positions
            from trading.user_trading_service import UserTradingService
            positions = await UserTradingService.get_portfolio_holdings(db, user_id)
            
            if not positions:
                logger.debug(f"No positions for user {user_id}, skipping stop order sync")
                return
            
            # Initialize stop order manager
            stop_manager = IBKRStopOrderManager(ibkr)
            
            # Sync stops with settings
            await stop_manager.sync_stops_with_settings(positions, settings)
            
            logger.info(f"Synced IBKR stop orders for user {user_id}")
            
        except ImportError as e:
            logger.warning(f"IBKR module not available: {e}")
        except Exception as e:
            logger.error(f"Failed to sync IBKR stops for user {user_id}: {e}")


# Helper function for API route
async def get_risk_settings_dict(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """Get risk settings as a dictionary for API response."""
    settings = await RiskSettingsService.get_settings(db, user_id)
    return settings.to_dict()
