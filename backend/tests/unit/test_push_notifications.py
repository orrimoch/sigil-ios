"""Unit tests for push notification service."""
import json
import os
import tempfile
import pytest
from unittest.mock import patch

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from notifications import push_service


@pytest.fixture(autouse=True)
def temp_tokens_file(tmp_path):
    """Use a temporary file for device tokens storage."""
    tokens_file = str(tmp_path / "device_tokens.json")
    with patch.object(push_service, 'TOKENS_FILE', tokens_file):
        yield tokens_file


class TestRegisterDeviceToken:
    """Tests for register_device_token."""

    def test_register_new_token(self):
        """Register a new device token creates an entry."""
        result = push_service.register_device_token(
            user_id="user1",
            device_token="abc123def456",
            platform="ios"
        )

        assert result["user_id"] == "user1"
        assert result["device_token"] == "abc123def456"
        assert result["platform"] == "ios"
        assert result["is_active"] is True
        assert "id" in result
        assert "registered_at" in result

    def test_register_creates_file(self, temp_tokens_file):
        """Registering a token creates the tokens file."""
        push_service.register_device_token("user1", "token1")
        assert os.path.exists(temp_tokens_file)

        with open(temp_tokens_file) as f:
            data = json.load(f)
        assert len(data["tokens"]) == 1

    def test_register_multiple_tokens(self):
        """Register multiple tokens for the same user."""
        push_service.register_device_token("user1", "token_a")
        push_service.register_device_token("user1", "token_b")

        tokens = push_service.get_user_tokens("user1")
        assert len(tokens) == 2

    def test_register_same_token_twice_no_duplicate(self):
        """Re-registering the same device token updates instead of duplicating."""
        push_service.register_device_token("user1", "same_token")
        push_service.register_device_token("user1", "same_token")

        tokens = push_service.get_all_active_tokens()
        assert len(tokens) == 1
        assert tokens[0]["device_token"] == "same_token"

    def test_register_same_token_different_user(self):
        """Re-registering a token under a different user updates the user_id."""
        push_service.register_device_token("user1", "shared_token")
        push_service.register_device_token("user2", "shared_token")

        tokens = push_service.get_all_active_tokens()
        assert len(tokens) == 1
        assert tokens[0]["user_id"] == "user2"

    def test_default_platform_is_ios(self):
        """Default platform should be 'ios'."""
        result = push_service.register_device_token("user1", "token1")
        assert result["platform"] == "ios"


class TestUnregisterDeviceToken:
    """Tests for unregister_device_token."""

    def test_unregister_existing_token(self):
        """Unregistering an existing token removes it."""
        push_service.register_device_token("user1", "token_to_remove")
        removed = push_service.unregister_device_token("token_to_remove")

        assert removed is True
        tokens = push_service.get_all_active_tokens()
        assert len(tokens) == 0

    def test_unregister_nonexistent_token(self):
        """Unregistering a nonexistent token returns False."""
        removed = push_service.unregister_device_token("nonexistent")
        assert removed is False

    def test_unregister_leaves_other_tokens(self):
        """Unregistering one token doesn't affect others."""
        push_service.register_device_token("user1", "keep_token")
        push_service.register_device_token("user1", "remove_token")

        push_service.unregister_device_token("remove_token")

        tokens = push_service.get_user_tokens("user1")
        assert len(tokens) == 1
        assert tokens[0]["device_token"] == "keep_token"


class TestGetUserTokens:
    """Tests for get_user_tokens."""

    def test_get_tokens_for_user(self):
        """Get tokens filters by user_id."""
        push_service.register_device_token("user1", "token_a")
        push_service.register_device_token("user2", "token_b")
        push_service.register_device_token("user1", "token_c")

        user1_tokens = push_service.get_user_tokens("user1")
        assert len(user1_tokens) == 2

        user2_tokens = push_service.get_user_tokens("user2")
        assert len(user2_tokens) == 1

    def test_get_tokens_empty_for_unknown_user(self):
        """Returns empty list for user with no tokens."""
        tokens = push_service.get_user_tokens("unknown_user")
        assert tokens == []

    def test_get_tokens_excludes_inactive(self):
        """get_user_tokens only returns active tokens."""
        push_service.register_device_token("user1", "active_token")

        # Manually deactivate a token
        data = push_service._load_tokens()
        data["tokens"].append({
            "id": "test",
            "user_id": "user1",
            "device_token": "inactive_token",
            "platform": "ios",
            "registered_at": "2025-01-01T00:00:00",
            "last_used_at": "2025-01-01T00:00:00",
            "is_active": False
        })
        push_service._save_tokens(data)

        tokens = push_service.get_user_tokens("user1")
        assert len(tokens) == 1
        assert tokens[0]["device_token"] == "active_token"


class TestGetAllActiveTokens:
    """Tests for get_all_active_tokens."""

    def test_get_all_active(self):
        """Returns all active tokens across users."""
        push_service.register_device_token("user1", "token1")
        push_service.register_device_token("user2", "token2")
        push_service.register_device_token("user3", "token3")

        tokens = push_service.get_all_active_tokens()
        assert len(tokens) == 3

    def test_empty_when_no_tokens(self):
        """Returns empty list when no tokens registered."""
        tokens = push_service.get_all_active_tokens()
        assert tokens == []


class TestSendPushNotification:
    """Tests for send_push_notification."""

    def test_send_returns_stub_result(self):
        """Send returns a structured stub response."""
        result = push_service.send_push_notification(
            device_token="abc123def456ghi789",
            title="Test Title",
            body="Test Body"
        )

        assert "notification_id" in result
        assert result["status"] == "queued"
        assert result["device_token"] == "abc123def456ghi7..."
        assert result["payload"]["aps"]["alert"]["title"] == "Test Title"
        assert result["payload"]["aps"]["alert"]["body"] == "Test Body"
        assert result["payload"]["aps"]["sound"] == "default"
        assert "sent_at" in result
        assert "APNs stub" in result["note"]

    def test_send_with_badge(self):
        """Badge count is included in payload when specified."""
        result = push_service.send_push_notification(
            device_token="abc123def456ghi789",
            title="Test",
            body="Body",
            badge=5
        )

        assert result["payload"]["aps"]["badge"] == 5

    def test_send_with_custom_data(self):
        """Custom data is merged into payload."""
        result = push_service.send_push_notification(
            device_token="abc123def456ghi789",
            title="Test",
            body="Body",
            data={"ticker": "AAPL", "type": "score_alert"}
        )

        assert result["payload"]["ticker"] == "AAPL"
        assert result["payload"]["type"] == "score_alert"

    def test_send_without_badge(self):
        """No badge key when badge is None."""
        result = push_service.send_push_notification(
            device_token="abc123def456ghi789",
            title="Test",
            body="Body"
        )

        assert "badge" not in result["payload"]["aps"]


class TestBroadcastPush:
    """Tests for broadcast_push."""

    def test_broadcast_to_all(self):
        """Broadcast sends to all active tokens."""
        push_service.register_device_token("user1", "token_aaaaaaaaaaaaaaaaaa")
        push_service.register_device_token("user2", "token_bbbbbbbbbbbbbbbbbb")

        result = push_service.broadcast_push(
            title="Broadcast",
            body="Hello everyone"
        )

        assert result["total_tokens"] == 2
        assert result["sent"] == 2
        assert len(result["results"]) == 2

    def test_broadcast_to_specific_user(self):
        """Broadcast with user_id only sends to that user's tokens."""
        push_service.register_device_token("user1", "token_aaaaaaaaaaaaaaaaaa")
        push_service.register_device_token("user2", "token_bbbbbbbbbbbbbbbbbb")

        result = push_service.broadcast_push(
            title="Personal",
            body="Just for you",
            user_id="user1"
        )

        assert result["total_tokens"] == 1
        assert result["sent"] == 1

    def test_broadcast_no_tokens(self):
        """Broadcast with no tokens sends nothing."""
        result = push_service.broadcast_push(
            title="Empty",
            body="No one here"
        )

        assert result["total_tokens"] == 0
        assert result["sent"] == 0
        assert result["results"] == []

    def test_broadcast_with_custom_data(self):
        """Custom data is passed through to each notification."""
        push_service.register_device_token("user1", "token_aaaaaaaaaaaaaaaaaa")

        result = push_service.broadcast_push(
            title="Alert",
            body="Score changed",
            data={"ticker": "AAPL"}
        )

        assert result["results"][0]["payload"]["ticker"] == "AAPL"


class TestLoadSaveTokens:
    """Tests for internal _load_tokens / _save_tokens."""

    def test_load_empty_returns_default(self):
        """Loading from nonexistent file returns empty structure."""
        data = push_service._load_tokens()
        assert data == {"tokens": []}

    def test_save_and_load_roundtrip(self, temp_tokens_file):
        """Data survives save/load roundtrip."""
        test_data = {"tokens": [{"id": "1", "device_token": "test"}]}
        push_service._save_tokens(test_data)

        loaded = push_service._load_tokens()
        assert loaded == test_data


# ═══════════════════════════════════════════════════════════════════════
# Order Fill Notification Tests (REC-141)
# ═══════════════════════════════════════════════════════════════════════

class TestOrderFillNotification:
    """Tests for send_order_fill_notification function."""

    def test_fill_notification_buy_paper(self):
        """Buy order fill notification has correct format."""
        push_service.register_device_token("user1", "token_aaaaaaaaaaaaaaaaaa")

        result = push_service.send_order_fill_notification(
            user_id="user1",
            ticker="AAPL",
            side="BUY",
            quantity=10,
            fill_price=150.50,
            order_type="MARKET",
            is_paper=True
        )

        assert result["total_tokens"] == 1
        assert result["sent"] == 1
        # Check notification content
        notification = result["results"][0]
        assert "Paper" in notification["payload"]["aps"]["alert"]["title"]
        assert "BUY" in notification["payload"]["aps"]["alert"]["body"]
        assert "AAPL" in notification["payload"]["aps"]["alert"]["body"]
        assert "150.50" in notification["payload"]["aps"]["alert"]["body"]
        # Check data payload
        assert notification["payload"]["type"] == "order_fill"
        assert notification["payload"]["ticker"] == "AAPL"
        assert notification["payload"]["side"] == "BUY"
        assert notification["payload"]["quantity"] == 10
        assert notification["payload"]["fill_price"] == 150.50
        assert notification["payload"]["is_paper"] is True

    def test_fill_notification_sell_live(self):
        """Sell order live notification doesn't have Paper prefix."""
        push_service.register_device_token("user1", "token_aaaaaaaaaaaaaaaaaa")

        result = push_service.send_order_fill_notification(
            user_id="user1",
            ticker="TSLA",
            side="SELL",
            quantity=5,
            fill_price=200.00,
            order_type="LIMIT",
            is_paper=False
        )

        notification = result["results"][0]
        assert "Paper" not in notification["payload"]["aps"]["alert"]["title"]
        assert "SELL" in notification["payload"]["aps"]["alert"]["body"]
        assert "TSLA" in notification["payload"]["aps"]["alert"]["body"]
        assert notification["payload"]["is_paper"] is False

    def test_fill_notification_no_tokens(self):
        """Fill notification with no registered tokens sends nothing."""
        result = push_service.send_order_fill_notification(
            user_id="unknown_user",
            ticker="AAPL",
            side="BUY",
            quantity=1,
            fill_price=100.00
        )

        assert result["total_tokens"] == 0
        assert result["sent"] == 0

    def test_fill_notification_calculates_total(self):
        """Fill notification includes calculated total."""
        push_service.register_device_token("user1", "token_aaaaaaaaaaaaaaaaaa")

        result = push_service.send_order_fill_notification(
            user_id="user1",
            ticker="AAPL",
            side="BUY",
            quantity=10,
            fill_price=150.00
        )

        notification = result["results"][0]
        # Total should be 10 * 150 = 1,500
        assert notification["payload"]["total"] == 1500.0
        assert "1,500" in notification["payload"]["aps"]["alert"]["body"]
