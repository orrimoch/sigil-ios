-- Agent Memory Schema (pgvector)
-- PostgreSQL 17 + pgvector 0.8.1
--
-- Run: psql sigil_agent < schema.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Agent decisions table
CREATE TABLE IF NOT EXISTS agent_decisions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- User association
    user_id VARCHAR(50),  -- Nullable for backward compatibility
    
    -- Decision details
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- BUY, SELL
    shares INTEGER NOT NULL DEFAULT 0,
    price DECIMAL(12, 4) NOT NULL DEFAULT 0,
    
    -- Context at decision time
    score DECIMAL(5, 2) NOT NULL,
    regime VARCHAR(20) NOT NULL DEFAULT 'normal',
    sector VARCHAR(50) DEFAULT 'Unknown',
    
    -- Rationale
    rationale TEXT NOT NULL DEFAULT '',
    confidence DECIMAL(3, 2) DEFAULT 0,
    
    -- Full context (JSON)
    context_json JSONB DEFAULT '{}',
    
    -- Outcome (filled 1-4 weeks AFTER decision)
    outcome_pct DECIMAL(8, 4),      -- e.g., +12.5 or -3.2
    outcome_date TIMESTAMPTZ,       -- When outcome was recorded
    lesson_learned TEXT,            -- Claude's reflection
    
    -- Embedding for similarity search
    embedding vector(1536)  -- OpenAI embedding size
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON agent_decisions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON agent_decisions(ticker);
CREATE INDEX IF NOT EXISTS idx_decisions_user ON agent_decisions(user_id);
CREATE INDEX IF NOT EXISTS idx_decisions_outcome ON agent_decisions(outcome_pct) WHERE outcome_pct IS NOT NULL;

-- pgvector index for fast similarity search
-- IVFFlat: Good for 100K+ rows, approximate but fast
CREATE INDEX IF NOT EXISTS idx_decisions_embedding 
ON agent_decisions USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Add user_id column if it doesn't exist (for migration)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'agent_decisions' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE agent_decisions ADD COLUMN user_id VARCHAR(50);
        CREATE INDEX idx_decisions_user ON agent_decisions(user_id);
    END IF;
END $$;

-- View for decisions with known outcomes
CREATE OR REPLACE VIEW agent_completed_decisions AS
SELECT 
    id, timestamp, user_id, ticker, action, shares, price,
    score, regime, sector, rationale, confidence,
    outcome_pct, outcome_date, lesson_learned,
    CASE 
        WHEN outcome_pct > 10 THEN 'strong_win'
        WHEN outcome_pct > 5 THEN 'win'
        WHEN outcome_pct > 1 THEN 'small_win'
        WHEN outcome_pct > -1 THEN 'neutral'
        WHEN outcome_pct > -5 THEN 'loss'
        ELSE 'strong_loss'
    END as outcome_tag
FROM agent_decisions
WHERE outcome_pct IS NOT NULL;

-- Pending trades table (for supervised mode)
CREATE TABLE IF NOT EXISTS agent_pending_trades (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    
    -- Trade details
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,
    shares INTEGER NOT NULL,
    estimated_price DECIMAL(12, 4) NOT NULL,
    estimated_value DECIMAL(14, 2) NOT NULL,
    weight DECIMAL(5, 4) DEFAULT 0,
    rationale TEXT NOT NULL,
    decision_id INTEGER REFERENCES agent_decisions(id),
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending_approval',
    
    -- Execution result (if approved)
    order_id VARCHAR(50),
    fill_price DECIMAL(12, 4),
    executed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pending_user ON agent_pending_trades(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_status ON agent_pending_trades(status);

-- Trading loop runs history
CREATE TABLE IF NOT EXISTS agent_trading_runs (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    
    -- Results summary
    success BOOLEAN NOT NULL DEFAULT FALSE,
    decisions_made INTEGER DEFAULT 0,
    executions_attempted INTEGER DEFAULT 0,
    executions_succeeded INTEGER DEFAULT 0,
    
    -- Details (JSON)
    result_json JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_runs_user ON agent_trading_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_runs_started ON agent_trading_runs(started_at DESC);

-- Agent settings per user
CREATE TABLE IF NOT EXISTS agent_settings (
    user_id VARCHAR(50) PRIMARY KEY,
    mode VARCHAR(20) NOT NULL DEFAULT 'supervised',
    max_trades_per_week INTEGER DEFAULT 5,
    min_score_for_buy DECIMAL(5, 2) DEFAULT 75.0,
    max_score_for_sell DECIMAL(5, 2) DEFAULT 40.0,
    risk_profile VARCHAR(20) DEFAULT 'moderate',
    stop_loss_enabled BOOLEAN DEFAULT TRUE,
    stop_loss_percent DECIMAL(4, 2) DEFAULT 8.0,
    auto_run_enabled BOOLEAN DEFAULT TRUE,
    auto_run_day VARCHAR(10) DEFAULT 'sunday',
    auto_run_hour INTEGER DEFAULT 1,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
