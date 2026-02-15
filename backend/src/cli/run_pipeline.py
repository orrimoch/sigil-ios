#!/usr/bin/env python3
"""
Unified CLI entry point for Sigil data pipelines.

Usage:
    python -m src.cli.run_pipeline full [--test] [--stocks N]
    python -m src.cli.run_pipeline scores-only
    python -m src.cli.run_pipeline crowd-wisdom
    python -m src.cli.run_pipeline train-hmm
    python -m src.cli.run_pipeline validate
"""
import argparse
import sys
import asyncio
from pathlib import Path
from datetime import datetime


def run_full_pipeline(test_mode: bool = False, stocks: int = None) -> int:
    """Run the full scoring pipeline."""
    try:
        from src.data.pipeline import run_pipeline
        
        print(f"[{datetime.now().isoformat()}] Starting full pipeline...")
        
        # In test mode, limit to specific tickers
        if test_mode:
            test_tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"]
            if stocks and stocks < len(test_tickers):
                test_tickers = test_tickers[:stocks]
            print(f"  Test mode: processing {len(test_tickers)} stocks: {test_tickers}")
            result = run_pipeline(tickers=test_tickers)
        else:
            result = run_pipeline()
        
        if result.success:
            print(f"[{datetime.now().isoformat()}] Full pipeline completed successfully")
            return 0
        else:
            print(f"[ERROR] Pipeline completed with errors: {result.errors}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"[ERROR] Full pipeline failed: {e}", file=sys.stderr)
        return 1


def run_scores_only() -> int:
    """Run only the scoring step (no data fetch)."""
    try:
        from src.data.pipeline import Pipeline
        from src.data.stock_universe import get_universe
        
        print(f"[{datetime.now().isoformat()}] Starting scores-only pipeline...")
        
        # Get current universe
        universe = get_universe()
        tickers = [s["ticker"] for s in universe]
        print(f"  Processing {len(tickers)} stocks from universe")
        
        # Run with all data fetching skipped
        pipeline = Pipeline()
        result = pipeline.run(
            skip_universe=True,
            skip_prices=True,
            skip_fundamentals=True,
            skip_news=True,
            skip_macro=True,
            tickers=tickers
        )
        
        if result.success:
            print(f"[{datetime.now().isoformat()}] Scoring completed successfully")
            return 0
        else:
            print(f"[ERROR] Scoring completed with errors: {result.errors}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"[ERROR] Scoring failed: {e}", file=sys.stderr)
        return 1


def run_crowd_wisdom() -> int:
    """Run crowd wisdom data fetching (Reddit + Insider)."""
    try:
        # Try to import crowd wisdom modules
        print(f"[{datetime.now().isoformat()}] Starting crowd wisdom fetch...")
        
        from src.crowd_wisdom.insider_fetcher import InsiderFetcher
        from src.crowd_wisdom.insider_scorer import InsiderScorer
        
        # Fetch insider data
        fetcher = InsiderFetcher()
        transactions = fetcher.fetch_recent_insider_buys(days=30)
        print(f"  Fetched {len(transactions)} insider transactions")
        
        # Score insider data
        scorer = InsiderScorer()
        scores = scorer.score_all_tickers(transactions)
        print(f"  Scored {len(scores)} tickers")
        
        print(f"[{datetime.now().isoformat()}] Crowd wisdom completed successfully")
        return 0
    except ImportError as e:
        print(f"[ERROR] Crowd wisdom module not found: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] Crowd wisdom failed: {e}", file=sys.stderr)
        return 1


def run_train_hmm() -> int:
    """Train the HMM regime model."""
    try:
        print(f"[{datetime.now().isoformat()}] Starting HMM training...")
        
        from src.risk.hmm_regime import HMMRegimeDetector
        
        detector = HMMRegimeDetector()
        detector.train()
        
        # Get current regime
        regime = detector.get_current_regime()
        print(f"  Model trained successfully")
        print(f"  Current regime: {regime.get('regime', 'unknown')}")
        
        print(f"[{datetime.now().isoformat()}] HMM training completed successfully")
        return 0
    except Exception as e:
        print(f"[ERROR] HMM training failed: {e}", file=sys.stderr)
        return 1


def run_validate() -> int:
    """Validate pipeline outputs."""
    try:
        print(f"[{datetime.now().isoformat()}] Starting validation...")
        
        data_dir = Path(__file__).parent.parent.parent / "data"
        
        # Check required files exist
        required_files = [
            "composite_scores.json",
            "stocks.db",
        ]
        
        missing = []
        for f in required_files:
            if not (data_dir / f).exists():
                missing.append(f)
        
        if missing:
            print(f"[ERROR] Missing files: {missing}", file=sys.stderr)
            return 1
        
        # Validate scores
        import json
        scores_file = data_dir / "composite_scores.json"
        with open(scores_file) as f:
            data = json.load(f)
        
        # Handle nested structure (scores may be under 'scores' key)
        if isinstance(data, dict) and "scores" in data:
            scores_data = data["scores"]
            # Scores can be dict keyed by ticker or list
            if isinstance(scores_data, dict):
                scores = list(scores_data.values())
            else:
                scores = scores_data
        elif isinstance(data, list):
            scores = data
        else:
            print(f"[ERROR] Unexpected scores format: {type(data)}", file=sys.stderr)
            return 1
        
        if len(scores) < 100:
            print(f"[ERROR] Too few scores: {len(scores)} (expected 100+)", file=sys.stderr)
            return 1
        
        # Check score ranges (handle both 'composite_score' and 'total_score' keys)
        invalid_scores = []
        for s in scores:
            if isinstance(s, dict):
                score_val = s.get("composite_score") or s.get("total_score", -1)
                if not (0 <= score_val <= 100):
                    invalid_scores.append(s)
        if invalid_scores:
            print(f"[ERROR] {len(invalid_scores)} scores out of range", file=sys.stderr)
            return 1
        
        print(f"  Validated {len(scores)} scores")
        print(f"[{datetime.now().isoformat()}] Validation passed")
        return 0
    except Exception as e:
        print(f"[ERROR] Validation failed: {e}", file=sys.stderr)
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sigil Data Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  full          Run full pipeline (universe, prices, fundamentals, news, macro, scoring)
  scores-only   Run only the scoring step (no data fetch)
  crowd-wisdom  Fetch Reddit and insider trading data
  train-hmm     Train HMM regime detection model
  validate      Validate pipeline outputs

Examples:
  python -m src.cli.run_pipeline full
  python -m src.cli.run_pipeline full --test --stocks 3
  python -m src.cli.run_pipeline scores-only
  python -m src.cli.run_pipeline crowd-wisdom
  python -m src.cli.run_pipeline train-hmm
  python -m src.cli.run_pipeline validate
"""
    )
    
    parser.add_argument(
        "command",
        choices=["full", "scores-only", "crowd-wisdom", "train-hmm", "validate"],
        help="Pipeline command to run"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (limited stocks)"
    )
    parser.add_argument(
        "--stocks",
        type=int,
        default=None,
        help="Number of stocks to process in test mode"
    )
    
    args = parser.parse_args()
    
    # Route to appropriate function
    if args.command == "full":
        exit_code = run_full_pipeline(test_mode=args.test, stocks=args.stocks)
    elif args.command == "scores-only":
        exit_code = run_scores_only()
    elif args.command == "crowd-wisdom":
        exit_code = run_crowd_wisdom()
    elif args.command == "train-hmm":
        exit_code = run_train_hmm()
    elif args.command == "validate":
        exit_code = run_validate()
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        exit_code = 1
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
