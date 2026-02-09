"""
Backtesting CLI

Usage:
    python -m backtest run --start 2024-01-01 --end 2025-12-31
    python -m backtest results <backtest_id>
    python -m backtest list
    python -m backtest trades <backtest_id>
    python -m backtest report <backtest_id> --format html --output ./report.html
    python -m backtest optimize --trials 50
    python -m backtest ic-decay --start 2024-01-01 --end 2025-12-31
    python -m backtest walk-forward --start 2024-01-01 --end 2025-12-31
    python -m backtest monte-carlo <backtest_id> --sims 1000
    python -m backtest import-scores
    python -m backtest stats
"""

import argparse
import json
import sys
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_store import (
    BacktestDataStore,
    BacktestParameters,
    BacktestStatus,
    get_data_store,
)
from backtest.engine import BacktestEngine
from backtest.historical_scores import HistoricalScoreGenerator
from backtest.ic_decay import ICDecayAnalyzer
from backtest.walk_forward import WalkForwardValidator
from backtest.optimizer import HPOEngine, load_latest_optimization
from backtest.metrics import MetricsCalculator
from backtest.monte_carlo import MonteCarloSimulator, run_monte_carlo, save_monte_carlo_result
from backtest.report_generator import ReportGenerator, ReportConfig, generate_report


def cmd_run(args):
    """Run a backtest."""
    print(f"\n{'='*60}")
    print("RUNNING BACKTEST")
    print(f"{'='*60}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Capital: ${args.capital:,.0f}")
    print(f"Entry threshold: {args.entry}")
    print(f"Exit threshold: {args.exit}")
    print(f"Max positions: {args.positions}")
    
    # REC-221: Print risk rules if enabled
    if args.enable_risk_rules or args.hard_stop or args.trailing_stop:
        print(f"\nRisk Rules: ENABLED")
        if args.hard_stop:
            print(f"  Hard Stop: {args.hard_stop*100:.1f}%")
        if args.trailing_stop:
            print(f"  Trailing Stop: {args.trailing_stop*100:.1f}%")
    else:
        print(f"\nRisk Rules: DISABLED")
    
    print(f"{'='*60}\n")

    # Determine if risk rules are enabled
    enable_risk = args.enable_risk_rules or (args.hard_stop is not None) or (args.trailing_stop is not None)

    params = BacktestParameters(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        entry_threshold=args.entry,
        exit_threshold=args.exit,
        max_positions=args.positions,
        rebalance_freq=args.rebalance,
        # REC-221: Risk rules
        enable_risk_rules=enable_risk,
        hard_stop_pct=args.hard_stop,
        trailing_stop_pct=args.trailing_stop,
    )

    engine = BacktestEngine()

    try:
        result = engine.run_backtest(params)

        print(f"\n{'='*60}")
        print("RESULTS")
        print(f"{'='*60}")
        print(f"Backtest ID: {result.backtest_id}")
        print(f"Status: {result.status.value}")

        if result.status == BacktestStatus.COMPLETED:
            print(f"\nPerformance:")
            print(f"  Total Return: {result.total_return:.2%}" if result.total_return else "  Total Return: N/A")
            print(f"  CAGR: {result.cagr:.2%}" if result.cagr else "  CAGR: N/A")
            print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}" if result.sharpe_ratio else "  Sharpe: N/A")
            print(f"  Max Drawdown: {result.max_drawdown:.2%}" if result.max_drawdown else "  Max DD: N/A")
            print(f"  Win Rate: {result.win_rate:.2%}" if result.win_rate else "  Win Rate: N/A")
            print(f"  Total Trades: {result.total_trades}")

            if result.benchmark_return:
                print(f"\nBenchmark (SPY):")
                print(f"  Return: {result.benchmark_return:.2%}")
                print(f"  Alpha: {result.alpha:.2%}" if result.alpha else "")

        print(f"{'='*60}\n")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def cmd_results(args):
    """Show backtest results."""
    store = get_data_store()
    result = store.get_backtest_result(args.backtest_id)

    if not result:
        print(f"Backtest not found: {args.backtest_id}")
        return 1

    print(f"\n{'='*60}")
    print(f"BACKTEST: {result.backtest_id}")
    print(f"{'='*60}")
    print(f"Status: {result.status.value}")
    print(f"Created: {result.created_at}")

    print(f"\nParameters:")
    print(f"  Period: {result.parameters.start_date} to {result.parameters.end_date}")
    print(f"  Capital: ${result.parameters.initial_capital:,.0f}")
    print(f"  Entry/Exit: {result.parameters.entry_threshold}/{result.parameters.exit_threshold}")
    print(f"  Max Positions: {result.parameters.max_positions}")

    if result.status == BacktestStatus.COMPLETED:
        print(f"\nPerformance:")
        print(f"  Total Return: {result.total_return:.2%}" if result.total_return else "")
        print(f"  CAGR: {result.cagr:.2%}" if result.cagr else "")
        print(f"  Sharpe: {result.sharpe_ratio:.2f}" if result.sharpe_ratio else "")
        print(f"  Max Drawdown: {result.max_drawdown:.2%}" if result.max_drawdown else "")
        print(f"  Win Rate: {result.win_rate:.2%}" if result.win_rate else "")
        print(f"  Trades: {result.total_trades}")

    if result.error_message:
        print(f"\nError: {result.error_message}")

    print(f"{'='*60}\n")
    return 0


def cmd_list(args):
    """List backtests."""
    store = get_data_store()
    results = store.list_backtests(limit=args.limit)

    if not results:
        print("No backtests found.")
        return 0

    print(f"\n{'ID':<35} {'Status':<12} {'Return':<10} {'Sharpe':<8} {'Created'}")
    print("-" * 85)

    for r in results:
        ret = f"{r.total_return:.1%}" if r.total_return else "N/A"
        sharpe = f"{r.sharpe_ratio:.2f}" if r.sharpe_ratio else "N/A"
        created = r.created_at[:16] if r.created_at else "N/A"
        print(f"{r.backtest_id:<35} {r.status.value:<12} {ret:<10} {sharpe:<8} {created}")

    print(f"\nTotal: {len(results)} backtests\n")
    return 0


def cmd_trades(args):
    """Show trades for a backtest."""
    store = get_data_store()
    trades = store.get_trades(args.backtest_id)

    if not trades:
        print(f"No trades found for: {args.backtest_id}")
        return 0

    print(f"\n{'Date':<12} {'Ticker':<8} {'Side':<6} {'Qty':<8} {'Price':<10} {'Score':<8}")
    print("-" * 60)

    for t in trades[:args.limit]:
        print(f"{t.date:<12} {t.ticker:<8} {t.side:<6} {t.quantity:<8.0f} ${t.price:<9.2f} {t.score_at_trade:<8.1f}")

    print(f"\nTotal: {len(trades)} trades\n")
    return 0


def cmd_report(args):
    """Generate backtest report."""
    print(f"\n{'='*60}")
    print("GENERATING REPORT")
    print(f"{'='*60}")
    print(f"Backtest ID: {args.backtest_id}")
    print(f"Format: {args.format.upper()}")
    print(f"Output: {args.output or '(stdout)'}")
    print(f"{'='*60}\n")

    try:
        config = ReportConfig(
            title=args.title,
            include_trades=args.include_trades,
            include_charts=args.include_charts,
            output_format=args.format,
        )

        generator = ReportGenerator()
        content = generator.generate_report(args.backtest_id, config, args.output)

        if args.output:
            print(f"✅ Report saved to: {args.output}")
            if args.format == "html":
                print(f"   Size: {len(content):,} bytes")
        else:
            # Print HTML to stdout
            if args.format == "html":
                print(content)
            else:
                print("PDF output requires --output flag")
                return 1

        print(f"{'='*60}\n")
        return 0

    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except ImportError as e:
        print(f"Error: {e}")
        print("Install weasyprint for PDF support: pip install weasyprint")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_optimize(args):
    """Run hyperparameter optimization."""
    print(f"\n{'='*60}")
    print("HYPERPARAMETER OPTIMIZATION")
    print(f"{'='*60}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Trials: {args.trials}")
    print(f"Timeout: {args.timeout}s")
    print(f"{'='*60}\n")

    engine = HPOEngine()

    try:
        result = engine.optimize(
            start_date=args.start,
            end_date=args.end,
            n_trials=args.trials,
            timeout_seconds=args.timeout,
            train_months=args.train_months,
            test_months=args.test_months,
        )

        print(f"\n{'='*60}")
        print("OPTIMIZATION RESULTS")
        print(f"{'='*60}")
        print(f"Trials: {result.n_completed} completed, {result.n_pruned} pruned")
        print(f"Time: {result.optimization_time_seconds:.1f}s")

        print(f"\nBest Parameters:")
        for k, v in result.best_params.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.1f}")
            else:
                print(f"  {k}: {v}")

        print(f"\nBest OOS Performance:")
        print(f"  Sharpe: {result.best_oos_sharpe:.2f}")
        print(f"  Return: {result.best_oos_return:.2%}")
        print(f"  Max DD: {result.best_oos_max_drawdown:.2%}")
        print(f"  Overfitting Score: {result.best_overfitting_score:.1f}/100")

        if result.param_importance:
            print(f"\nParameter Importance:")
            for k, v in sorted(result.param_importance.items(), key=lambda x: -x[1]):
                print(f"  {k}: {v:.1%}")

        print(f"{'='*60}\n")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def cmd_ic_decay(args):
    """Analyze IC decay."""
    print(f"\n{'='*60}")
    print("IC DECAY ANALYSIS")
    print(f"{'='*60}")
    print(f"Period: {args.start} to {args.end}")
    print(f"{'='*60}\n")

    analyzer = ICDecayAnalyzer()

    try:
        result = analyzer.analyze_ic_decay(args.start, args.end)

        print("IC by Day Offset:")
        print("-" * 50)
        for day in range(1, 6):
            ic = result.ic_by_day.get(day, 0)
            p = result.ic_p_values.get(day, 1)
            n = result.ic_by_day_count.get(day, 0)
            sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
            print(f"  Day {day}: IC = {ic:+.4f}  (p={p:.3f}, n={n}) {sig}")

        print(f"\nDecay Analysis:")
        print(f"  Decay Rate: {result.decay_rate:.4f} per day")
        print(f"  Half-Life: {result.half_life_days:.1f} days")

        print(f"\nRecommendation: {result.recommended_refresh_freq.upper()}")
        print(f"  Reason: {result.refresh_reason}")

        print(f"\nWeeks Analyzed: {result.weeks_analyzed}")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def cmd_walk_forward(args):
    """Run walk-forward validation."""
    print(f"\n{'='*60}")
    print("WALK-FORWARD VALIDATION")
    print(f"{'='*60}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Train: {args.train_months} months, Test: {args.test_months} months")
    print(f"{'='*60}\n")

    validator = WalkForwardValidator()

    try:
        result = validator.run_walk_forward(
            start_date=args.start,
            end_date=args.end,
            train_months=args.train_months,
            test_months=args.test_months,
        )

        print(f"Folds: {result.total_folds}")

        print(f"\nOut-of-Sample (TRUE) Performance:")
        print(f"  Total Return: {result.oos_total_return:.2%}")
        print(f"  CAGR: {result.oos_cagr:.2%}")
        print(f"  Sharpe: {result.oos_sharpe:.2f}")
        print(f"  Max Drawdown: {result.oos_max_drawdown:.2%}")
        print(f"  Win Rate: {result.oos_win_rate:.2%}")

        print(f"\nIn-Sample Performance:")
        print(f"  Total Return: {result.is_total_return:.2%}")
        print(f"  Sharpe: {result.is_sharpe:.2f}")

        print(f"\nOverfitting Analysis:")
        print(f"  Return Degradation: {result.avg_return_degradation:.2%}")
        print(f"  Sharpe Degradation: {result.avg_sharpe_degradation:.2f}")
        print(f"  Overfitting Score: {result.overfitting_score:.1f}/100")
        print(f"  Assessment: {result.overfitting_assessment.upper()}")

        print(f"{'='*60}\n")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def cmd_monte_carlo(args):
    """Run Monte Carlo simulation on backtest results."""
    print(f"\n{'='*60}")
    print("MONTE CARLO SIMULATION")
    print(f"{'='*60}")
    print(f"Backtest ID: {args.backtest_id}")
    print(f"Simulations: {args.sims}")
    if args.seed:
        print(f"Random Seed: {args.seed}")
    print(f"{'='*60}\n")

    try:
        simulator = MonteCarloSimulator(seed=args.seed)

        def progress(current, total):
            pct = current / total * 100
            print(f"  Progress: {current}/{total} ({pct:.0f}%)")

        result = simulator.run_from_backtest(
            backtest_id=args.backtest_id,
            n_simulations=args.sims,
            progress_callback=progress,
        )

        # Save result
        if not args.no_save:
            save_monte_carlo_result(args.backtest_id, result)

        # Print summary
        print(f"\n{result.summary()}")

        print(f"\n{'='*60}\n")

    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def cmd_generate(args):
    """Generate historical scores for backtesting."""
    print(f"\n{'='*60}")
    print("GENERATING HISTORICAL SCORES")
    print(f"{'='*60}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Frequency: {args.frequency}")
    if args.tickers:
        print(f"Tickers: {args.tickers}")
    else:
        print(f"Tickers: All universe (~677 stocks)")
    if args.force:
        print(f"Mode: Force regenerate (ignoring cache)")
    else:
        print(f"Mode: Incremental (skip cached dates)")
    if args.no_sentiment:
        print(f"Weights: No-sentiment mode (redistributed to fundamental/technical/macro)")
    else:
        print(f"Weights: Standard (includes 25% sentiment @ neutral 50)")
    print(f"{'='*60}\n")

    generator = HistoricalScoreGenerator(no_sentiment=args.no_sentiment)

    def progress(current, total, ticker=""):
        pct = current / total * 100 if total > 0 else 0
        if ticker:
            print(f"  [{current}/{total}] ({pct:.0f}%) {ticker}")
        else:
            print(f"  Progress: {current}/{total} ({pct:.0f}%)")

    try:
        tickers = args.tickers.split(",") if args.tickers else None

        count = generator.generate_historical_scores(
            start_date=args.start,
            end_date=args.end,
            tickers=tickers,
            frequency=args.frequency,
            progress_callback=progress,
            force_regenerate=args.force,
        )

        print(f"\n{'='*60}")
        if count > 0:
            print(f"✅ Generated {count:,} historical scores")
        else:
            print(f"✅ All dates already cached. Nothing to generate.")
            print(f"   Use --force to regenerate.")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


def cmd_import_scores(args):
    """Import existing scores into backtest storage."""
    print("Importing existing pipeline scores...\n")

    generator = HistoricalScoreGenerator()
    imported = generator.generate_from_existing_pipeline()

    print(f"Imported {imported} scores from existing pipeline history.\n")
    return 0


def cmd_stats(args):
    """Show storage statistics."""
    store = get_data_store()
    stats = store.get_storage_stats()

    print(f"\n{'='*60}")
    print("BACKTEST STORAGE STATISTICS")
    print(f"{'='*60}")
    print(f"Historical Scores: {stats['historical_scores_count']:,}")
    print(f"Backtests: {stats['backtest_count']}")

    if stats['date_range']['min']:
        print(f"Date Range: {stats['date_range']['min']} to {stats['date_range']['max']}")

    print(f"Data Directory: {stats['data_dir']}")
    print(f"{'='*60}\n")
    return 0


def main():
    # Default dates
    default_end = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - relativedelta(months=18)).strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(
        description="Sigil Backtesting CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backtest run --start 2024-01-01 --end 2025-12-31
  python -m backtest list
  python -m backtest results bt_20260206_123456_abc123
  python -m backtest optimize --trials 50
  python -m backtest ic-decay
  python -m backtest walk-forward
  python -m backtest stats
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run
    run_parser = subparsers.add_parser("run", help="Run a backtest")
    run_parser.add_argument("--start", default=default_start, help="Start date (YYYY-MM-DD)")
    run_parser.add_argument("--end", default=default_end, help="End date (YYYY-MM-DD)")
    run_parser.add_argument("--capital", type=float, default=100000, help="Initial capital")
    run_parser.add_argument("--entry", type=float, default=70, help="Entry threshold")
    run_parser.add_argument("--exit", type=float, default=50, help="Exit threshold")
    run_parser.add_argument("--positions", type=int, default=10, help="Max positions")
    run_parser.add_argument("--rebalance", default="weekly", help="Rebalance frequency")
    # REC-221: Risk rules
    run_parser.add_argument("--enable-risk-rules", action="store_true", help="Enable risk management rules")
    run_parser.add_argument("--hard-stop", type=float, default=None, help="Hard stop-loss %% (e.g., -0.08 for -8%%)")
    run_parser.add_argument("--trailing-stop", type=float, default=None, help="Trailing stop %% (e.g., -0.10 for -10%%)")

    # results
    results_parser = subparsers.add_parser("results", help="Show backtest results")
    results_parser.add_argument("backtest_id", help="Backtest ID")

    # list
    list_parser = subparsers.add_parser("list", help="List backtests")
    list_parser.add_argument("--limit", type=int, default=20, help="Max results")

    # trades
    trades_parser = subparsers.add_parser("trades", help="Show trades for a backtest")
    trades_parser.add_argument("backtest_id", help="Backtest ID")
    trades_parser.add_argument("--limit", type=int, default=50, help="Max trades to show")

    # report (F12.10)
    report_parser = subparsers.add_parser("report", help="Generate backtest report")
    report_parser.add_argument("backtest_id", help="Backtest ID")
    report_parser.add_argument("--format", default="html", choices=["html", "pdf"], help="Output format")
    report_parser.add_argument("--output", "-o", help="Output file path")
    report_parser.add_argument("--title", default="Sigil Backtest Report", help="Report title")
    report_parser.add_argument("--no-trades", dest="include_trades", action="store_false", help="Exclude trade log")
    report_parser.add_argument("--no-charts", dest="include_charts", action="store_false", help="Exclude charts")

    # optimize
    opt_parser = subparsers.add_parser("optimize", help="Run HPO")
    opt_parser.add_argument("--start", default=default_start, help="Start date")
    opt_parser.add_argument("--end", default=default_end, help="End date")
    opt_parser.add_argument("--trials", type=int, default=50, help="Number of trials")
    opt_parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    opt_parser.add_argument("--train-months", type=int, default=9, help="Train period months")
    opt_parser.add_argument("--test-months", type=int, default=3, help="Test period months")

    # ic-decay
    ic_parser = subparsers.add_parser("ic-decay", help="Analyze IC decay")
    ic_parser.add_argument("--start", default=default_start, help="Start date")
    ic_parser.add_argument("--end", default=default_end, help="End date")

    # walk-forward
    wf_parser = subparsers.add_parser("walk-forward", help="Run walk-forward validation")
    wf_parser.add_argument("--start", default=default_start, help="Start date")
    wf_parser.add_argument("--end", default=default_end, help="End date")
    wf_parser.add_argument("--train-months", type=int, default=9, help="Train period months")
    wf_parser.add_argument("--test-months", type=int, default=3, help="Test period months")

    # monte-carlo
    mc_parser = subparsers.add_parser("monte-carlo", help="Run Monte Carlo simulation")
    mc_parser.add_argument("backtest_id", help="Backtest ID to analyze")
    mc_parser.add_argument("--sims", type=int, default=1000, help="Number of simulations (100-10000)")
    mc_parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    mc_parser.add_argument("--no-save", action="store_true", help="Don't save results to file")

    # generate (historical scores)
    gen_parser = subparsers.add_parser("generate", help="Generate historical scores")
    gen_parser.add_argument("--start", default=default_start, help="Start date (YYYY-MM-DD)")
    gen_parser.add_argument("--end", default=default_end, help="End date (YYYY-MM-DD)")
    gen_parser.add_argument("--frequency", default="weekly", choices=["daily", "weekly"], help="Score frequency")
    gen_parser.add_argument("--tickers", default=None, help="Comma-separated tickers (default: all)")
    gen_parser.add_argument("--force", action="store_true", help="Force regenerate, ignore cached scores")
    gen_parser.add_argument("--no-sentiment", action="store_true", dest="no_sentiment", 
                           help="Exclude sentiment from scoring (redistribute weight to fundamental/technical/macro)")

    # import-scores
    subparsers.add_parser("import-scores", help="Import existing pipeline scores")

    # stats
    subparsers.add_parser("stats", help="Show storage statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "run": cmd_run,
        "results": cmd_results,
        "list": cmd_list,
        "trades": cmd_trades,
        "report": cmd_report,
        "optimize": cmd_optimize,
        "ic-decay": cmd_ic_decay,
        "walk-forward": cmd_walk_forward,
        "monte-carlo": cmd_monte_carlo,
        "generate": cmd_generate,
        "import-scores": cmd_import_scores,
        "stats": cmd_stats,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
