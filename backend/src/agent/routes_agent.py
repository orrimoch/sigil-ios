"""
Agent API Routes (REC-291)

Endpoints for agent status, control, pending approvals, and history.

Agent Status & Control:
- GET  /api/v1/agent/status           # Agent state + stats
- POST /api/v1/agent/run              # Trigger trading loop
- POST /api/v1/agent/pause            # Pause agent
- POST /api/v1/agent/resume           # Resume agent
- PUT  /api/v1/agent/settings         # Update settings

Pending Approvals:
- GET  /api/v1/agent/pending          # List pending trades
- POST /api/v1/agent/pending/{id}/approve
- POST /api/v1/agent/pending/{id}/reject

History:
- GET  /api/v1/agent/history          # Run history
- GET  /api/v1/agent/decisions        # Decision history

Learning:
- GET  /api/v1/agent/lessons          # Recent lessons learned
- GET  /api/v1/agent/stats            # Learning statistics
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field

from .trading_loop import (
    TradingLoop,
    TradingLoopResult,
    AgentSettings,
    AgentStatus,
    get_trading_loop,
)
from .executor import (
    TradeExecutor,
    ExecutorSettings,
    ExecutionMode,
    PendingTrade,
    get_executor,
)
from .learning import LearningLoop, get_learning_loop
from .memory import get_agent_memory
from .decision_pairs import get_decision_pair_logger, DecisionPairLogger

# Auth imports with fallback for testing
try:
    from ..auth.middleware import get_agent_user
    from ..auth.models import User
    get_current_user = get_agent_user  # Alias for compatibility
except ImportError:
    import os
    # Stubs for standalone testing - use configured default user
    default_user_id = os.getenv("AGENT_DEFAULT_USER_ID", "test_user")
    async def get_current_user():
        return type('User', (), {'id': default_user_id})()
    get_agent_user = get_current_user
    User = None

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AgentSettingsRequest(BaseModel):
    """Request model for updating agent settings."""
    mode: Optional[str] = Field(None, description="supervised or autonomous")
    max_trades_per_week: Optional[int] = Field(None, ge=1, le=20)
    min_score_for_buy: Optional[float] = Field(None, ge=50, le=100)
    max_score_for_sell: Optional[float] = Field(None, ge=0, le=50)
    risk_profile: Optional[str] = Field(None, pattern="^(conservative|moderate|aggressive)$")
    stop_loss_enabled: Optional[bool] = None
    stop_loss_percent: Optional[float] = Field(None, ge=1, le=20)
    auto_run_enabled: Optional[bool] = None


class RunTradingLoopRequest(BaseModel):
    """Request model for triggering trading loop."""
    dry_run: bool = Field(False, description="If true, simulate without executing")


class ApprovalResponse(BaseModel):
    """Response for pending trade approval/rejection."""
    success: bool
    message: str
    execution_result: Optional[Dict[str, Any]] = None


class AgentStatusResponse(BaseModel):
    """Response model for agent status."""
    status: str
    settings: Dict[str, Any]
    last_run: Optional[Dict[str, Any]]
    total_runs: int
    pending_approvals: int


class TradingLoopResponse(BaseModel):
    """Response model for trading loop execution."""
    success: bool
    run_id: str
    message: str
    details: Dict[str, Any]


# ============================================================================
# Agent Status & Control Endpoints
# ============================================================================

@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(
    current_user: User = Depends(get_current_user),
):
    """
    Get current agent status.
    
    Returns:
        Agent status, settings, and last run info
    """
    loop = get_trading_loop()
    executor = get_executor()
    
    status = loop.get_status()
    pending = await executor.get_pending_trades(str(current_user.id))
    
    # Get total runs from in-memory, fallback to DB execution count
    total_runs = status["total_runs"]
    if total_runs == 0:
        try:
            import aiosqlite
            from pathlib import Path
            db_path = Path(__file__).parent.parent.parent / "data" / "agent_memory.db"
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM executions WHERE user_id = ?",
                    (str(current_user.id),)
                )
                row = await cursor.fetchone()
                total_runs = row[0] if row else 0
        except Exception as e:
            logger.warning(f"Failed to get execution count from DB: {e}")
    
    return AgentStatusResponse(
        status=status["status"],
        settings=status["settings"],
        last_run=status["last_run"],
        total_runs=total_runs,
        pending_approvals=len(pending),
    )


@router.post("/run", response_model=TradingLoopResponse)
async def run_trading_loop(
    request: RunTradingLoopRequest = Body(default=RunTradingLoopRequest()),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger the trading loop manually.
    
    This runs the complete cycle:
    1. Aggregate context
    2. Retrieve memories
    3. Make decisions
    4. Size positions
    5. Validate risk
    6. Execute trades (or queue for approval)
    7. Store decisions
    8. Update learning
    """
    loop = get_trading_loop()
    
    if loop.status == AgentStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Trading loop is already running"
        )
    
    if loop.status == AgentStatus.PAUSED:
        raise HTTPException(
            status_code=409,
            detail="Agent is paused. Resume before running."
        )
    
    result = await loop.run(
        user_id=str(current_user.id),
        dry_run=request.dry_run,
    )
    
    return TradingLoopResponse(
        success=result.success,
        run_id=result.run_id,
        message="Trading loop completed" if result.success else "Trading loop failed",
        details=result.to_dict(),
    )


@router.post("/pause")
async def pause_agent(
    current_user: User = Depends(get_current_user),
):
    """Pause the agent."""
    loop = get_trading_loop()
    loop.pause()
    return {"success": True, "status": "paused"}


@router.post("/resume")
async def resume_agent(
    current_user: User = Depends(get_current_user),
):
    """Resume the agent."""
    loop = get_trading_loop()
    loop.resume()
    return {"success": True, "status": "active"}


@router.put("/settings")
async def update_settings(
    request: AgentSettingsRequest,
    current_user: User = Depends(get_current_user),
):
    """Update agent settings."""
    loop = get_trading_loop()
    current = loop.settings
    
    # Merge with current settings
    new_settings = AgentSettings(
        mode=ExecutionMode(request.mode) if request.mode else current.mode,
        max_trades_per_week=request.max_trades_per_week or current.max_trades_per_week,
        min_score_for_buy=request.min_score_for_buy or current.min_score_for_buy,
        max_score_for_sell=request.max_score_for_sell or current.max_score_for_sell,
        risk_profile=request.risk_profile or current.risk_profile,
        stop_loss_enabled=request.stop_loss_enabled if request.stop_loss_enabled is not None else current.stop_loss_enabled,
        stop_loss_percent=request.stop_loss_percent or current.stop_loss_percent,
        auto_run_enabled=request.auto_run_enabled if request.auto_run_enabled is not None else current.auto_run_enabled,
    )
    
    loop.update_settings(new_settings)
    
    return {"success": True, "settings": new_settings.to_dict()}


# ============================================================================
# Pending Approvals Endpoints
# ============================================================================

@router.get("/pending")
async def get_pending_trades(
    current_user: User = Depends(get_current_user),
):
    """Get all pending trades awaiting approval."""
    executor = get_executor()
    pending = await executor.get_pending_trades(str(current_user.id))
    
    return {
        "pending": [p.to_dict() for p in pending],
        "count": len(pending),
    }


@router.post("/pending/{pending_id}/approve", response_model=ApprovalResponse)
async def approve_pending_trade(
    pending_id: str,
    current_user: User = Depends(get_current_user),
):
    """Approve a pending trade for execution."""
    executor = get_executor()
    loop = get_trading_loop()
    
    settings = ExecutorSettings(
        mode=loop.settings.mode,
        stop_loss_type="trailing" if loop.settings.stop_loss_enabled else "none",
        stop_loss_percent=loop.settings.stop_loss_percent,
    )
    
    result = await executor.approve_pending(
        pending_id=pending_id,
        user_id=str(current_user.id),
        settings=settings,
    )
    
    return ApprovalResponse(
        success=result.success,
        message=result.message,
        execution_result=result.to_dict() if result.success else None,
    )


@router.post("/pending/{pending_id}/reject", response_model=ApprovalResponse)
async def reject_pending_trade(
    pending_id: str,
    reason: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Reject a pending trade."""
    executor = get_executor()
    
    success = await executor.reject_pending(
        pending_id=pending_id,
        user_id=str(current_user.id),
        reason=reason,
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Pending trade {pending_id} not found"
        )
    
    return ApprovalResponse(
        success=True,
        message=f"Trade rejected: {reason or 'No reason provided'}",
    )


# ============================================================================
# History Endpoints
# ============================================================================

@router.get("/history")
async def get_run_history(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get trading loop run history."""
    loop = get_trading_loop()
    history = loop.get_run_history(limit=limit)
    
    return {
        "runs": history,
        "count": len(history),
    }


@router.get("/decisions")
async def get_decision_history(
    limit: int = Query(50, ge=1, le=200),
    ticker: Optional[str] = Query(None),
    action: Optional[str] = Query(None, pattern="^(BUY|SELL)$"),
    current_user: User = Depends(get_current_user),
):
    """Get decision history with optional filters."""
    memory = await get_agent_memory()
    
    decisions = await memory.get_recent_decisions(
        user_id=str(current_user.id),
        limit=limit,
        ticker=ticker,
        action=action,
    )
    
    return {
        "decisions": [d.to_dict() if hasattr(d, 'to_dict') else vars(d) for d in decisions],
        "count": len(decisions),
    }


@router.get("/executions")
async def get_execution_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Get trade execution history."""
    executor = get_executor()
    executions = await executor.get_execution_history(
        user_id=str(current_user.id),
        limit=limit,
    )
    
    # Fallback: read from persistent DB if in-memory is empty
    if not executions:
        try:
            import aiosqlite
            from pathlib import Path
            db_path = Path(__file__).parent.parent.parent / "data" / "agent_memory.db"
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM executions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (str(current_user.id), limit)
                )
                rows = await cursor.fetchall()
                # Return as dicts directly
                result = []
                for row in rows:
                    # Convert timestamp to ISO8601 format for iOS
                    ts = row["timestamp"]
                    if ts and " " in ts and "T" not in ts:
                        ts = ts.replace(" ", "T")
                    result.append({
                        "ticker": row["ticker"],
                        "action": row["action"],
                        "shares": row["shares"],
                        "fill_price": row["fill_price"],
                        "fill_value": row["fill_value"],
                        "order_id": row["order_id"],
                        "success": bool(row["success"]),
                        "message": row["message"],
                        "executed_at": ts,
                    })
                return {"executions": result, "count": len(result)}
        except Exception as e:
            logger.warning(f"Failed to load executions from DB: {e}")
    
    return {
        "executions": [e.to_dict() for e in executions],
        "count": len(executions),
    }


# ============================================================================
# Learning Endpoints
# ============================================================================

@router.get("/lessons")
async def get_recent_lessons(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Get recently generated lessons from the learning loop."""
    learning = get_learning_loop()
    lessons = await learning.get_recent_lessons(limit=limit)
    
    return {
        "lessons": [l.to_dict() for l in lessons],
        "count": len(lessons),
    }


@router.get("/stats")
async def get_agent_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Get agent statistics for dashboard.
    
    Returns unified stats matching iOS AgentStats model:
    - total_decisions: Total decisions made
    - total_executions: Total trades executed
    - success_rate: Win rate as decimal (0-1)
    - avg_outcome: Average P&L percentage
    - weekly_trades: Trades in the last 7 days
    - lessons_learned: Total lessons generated
    """
    from datetime import timedelta
    
    learning = get_learning_loop()
    memory = await get_agent_memory()
    executor = get_executor()
    
    # Get learning stats
    learning_stats = await learning.get_learning_stats()
    
    # Get decision count
    decisions = await memory.get_recent_decisions(
        user_id=str(current_user.id),
        limit=1000,  # Get all recent
    )
    total_decisions = len(decisions)
    
    # Get execution history (in-memory first, then fallback to DB)
    executions = await executor.get_execution_history(
        user_id=str(current_user.id),
        limit=1000,
    )
    
    # Fallback: read from persistent DB if in-memory is empty
    if not executions:
        try:
            import aiosqlite
            from pathlib import Path
            db_path = Path(__file__).parent.parent.parent / "data" / "agent_memory.db"
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM executions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1000",
                    (str(current_user.id),)
                )
                rows = await cursor.fetchall()
                # Convert to simple objects
                class Execution:
                    def __init__(self, row):
                        self.ticker = row['ticker']
                        self.action = row['action']
                        self.shares = row['shares']
                        self.fill_price = row['fill_price']
                        self.success = bool(row['success'])
                        self.executed_at = row['timestamp']
                executions = [Execution(r) for r in rows]
        except Exception as e:
            logger.warning(f"Failed to load executions from DB: {e}")
    
    total_executions = len(executions)
    
    # Count successful executions
    successful = sum(1 for e in executions if e.success)
    success_rate = (successful / total_executions) if total_executions > 0 else 0.0
    
    # Count weekly trades (last 7 days)
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_trades = 0
    for e in executions:
        try:
            exec_time_str = getattr(e, 'executed_at', None) or getattr(e, 'timestamp', None)
            if exec_time_str:
                exec_time = datetime.fromisoformat(exec_time_str.replace('Z', '+00:00').replace(' ', 'T'))
                if exec_time.replace(tzinfo=None) >= one_week_ago:
                    weekly_trades += 1
        except (ValueError, AttributeError, TypeError):
            # If can't parse date, count as this week (conservative)
            weekly_trades += 1
    
    return {
        "total_decisions": total_decisions,
        "total_executions": total_executions,
        "success_rate": success_rate,
        "avg_outcome": learning_stats.get("avg_outcome", 0.0),
        "weekly_trades": weekly_trades,
        "lessons_learned": learning_stats.get("total_lessons", 0),
    }


@router.post("/learn")
async def trigger_learning_update(
    current_user: User = Depends(get_current_user),
):
    """Manually trigger the learning update."""
    from .learning import run_learning_update
    
    result = await run_learning_update()
    
    return {
        "success": len(result.get("errors", [])) == 0,
        "outcomes_recorded": result.get("outcomes_recorded", 0),
        "lessons_generated": result.get("lessons_generated", 0),
        "errors": result.get("errors", []),
    }


# ============================================================================
# Decision Pair Logging Endpoints (REC-298)
# ============================================================================

@router.get("/training/stats")
async def get_training_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Get statistics about logged decisions for training data.
    
    Returns:
    - total_decisions: All logged decisions
    - with_outcomes: Decisions with recorded outcomes
    - preferred/neutral/dispreferred: Count by preference label
    - avg_outcome_pct: Average P&L%
    - ready_for_training: True if enough data for useful training
    """
    pair_logger = get_decision_pair_logger()
    return await pair_logger.get_stats()


@router.get("/training/decisions")
async def get_training_decisions(
    limit: int = Query(100, ge=1, le=500),
    with_outcomes_only: bool = Query(True),
    min_outcome: Optional[float] = Query(None),
    max_outcome: Optional[float] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """
    Get logged decisions for analysis.
    
    Use with_outcomes_only=True to get only decisions with known outcomes.
    Filter by outcome range with min_outcome/max_outcome.
    """
    pair_logger = get_decision_pair_logger()
    
    if with_outcomes_only:
        decisions = await pair_logger.get_decisions_with_outcomes(
            user_id=str(current_user.id),
            min_outcome=min_outcome,
            max_outcome=max_outcome,
            limit=limit,
        )
    else:
        decisions = await pair_logger.get_decisions_with_outcomes(
            user_id=str(current_user.id),
            limit=limit,
        )
    
    return {
        "decisions": [d.to_dict() for d in decisions],
        "count": len(decisions),
    }


@router.post("/training/generate-pairs")
async def generate_training_pairs(
    min_outcome_diff: float = Query(5.0, ge=1.0, le=20.0),
    max_pairs: int = Query(500, ge=10, le=2000),
    current_user: User = Depends(get_current_user),
):
    """
    Generate DPO training pairs from logged decisions.
    
    Pairs high-outcome decisions with low-outcome ones from similar contexts.
    min_outcome_diff controls the minimum difference required (default 5%).
    """
    pair_logger = get_decision_pair_logger()
    pairs = await pair_logger.generate_training_pairs(
        min_outcome_diff=min_outcome_diff,
        max_pairs=max_pairs,
    )
    
    return {
        "pairs": [p.to_dpo_format() for p in pairs],
        "count": len(pairs),
        "min_outcome_diff": min_outcome_diff,
    }


@router.post("/training/export")
async def export_training_data(
    format: str = Query("jsonl", pattern="^(jsonl|json)$"),
    min_outcome_diff: float = Query(5.0, ge=1.0, le=20.0),
    current_user: User = Depends(get_current_user),
):
    """
    Export training data to file.
    
    Formats:
    - jsonl: DPO training format (prompt, chosen, rejected)
    - json: Full decision records with context
    
    Returns the file path for download.
    """
    from pathlib import Path
    
    pair_logger = get_decision_pair_logger()
    export_dir = Path(__file__).parent.parent.parent / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    if format == "jsonl":
        output_path = export_dir / f"dpo_training_{timestamp}.jsonl"
        count = await pair_logger.export_to_jsonl(
            str(output_path),
            min_outcome_diff=min_outcome_diff,
        )
    else:
        output_path = export_dir / f"decisions_{timestamp}.json"
        count = await pair_logger.export_all_decisions(
            str(output_path),
            with_outcomes_only=True,
        )
    
    return {
        "success": True,
        "format": format,
        "file_path": str(output_path),
        "records_exported": count,
    }
