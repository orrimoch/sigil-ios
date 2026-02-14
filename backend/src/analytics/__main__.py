"""
Sector Performance Analysis CLI (REC-271)

Usage:
    python3 -m src.analytics sector-scores [OPTIONS]
    python3 -m src.analytics sector-trends [OPTIONS]
    python3 -m src.analytics sector-report [OPTIONS]
    python3 -m src.analytics list-sectors
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict

from .sector_analysis import SectorAnalyzer, SectorScore
from .visualization import (
    plot_sector_trends,
    plot_sector_heatmap,
    plot_score_distribution,
    plot_signal_distribution,
    generate_sector_report,
    MATPLOTLIB_AVAILABLE,
    PLOTLY_AVAILABLE
)


def cmd_list_sectors(args):
    """List all available sectors and industries."""
    analyzer = SectorAnalyzer()
    analyzer.load_data()
    
    print("\n📊 AVAILABLE SECTORS & INDUSTRIES")
    print("=" * 60)
    
    for sector in analyzer.sectors:
        stocks = analyzer.get_stocks_in_sector(sector=sector)
        industries = analyzer.get_sector_industries(sector)
        
        print(f"\n🏛️  {sector} ({len(stocks)} stocks)")
        for industry in industries:
            industry_stocks = analyzer.get_stocks_in_sector(industry=industry)
            print(f"    └─ {industry} ({len(industry_stocks)})")
    
    print(f"\n📈 Total: {len(analyzer.sectors)} sectors, {len(analyzer.industries)} industries")


def cmd_sector_scores(args):
    """Calculate and display sector scores."""
    analyzer = SectorAnalyzer()
    
    # Default date
    date = args.date
    if not date:
        dates = analyzer.get_available_dates()
        date = dates[-1] if dates else datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n📊 SECTOR SCORES for {date}")
    print("=" * 80)
    
    if args.sector:
        # Single sector
        score = analyzer.calculate_sector_score(
            date=date,
            sector=args.sector,
            industry=args.industry,
            top_n=args.top_n
        )
        _print_sector_score(score)
    else:
        # All sectors
        summary = []
        for sector in analyzer.sectors:
            score = analyzer.calculate_sector_score(
                date=date,
                sector=sector,
                top_n=args.top_n
            )
            summary.append(score)
        
        # Sort by mean score descending
        summary.sort(key=lambda s: s.mean_score, reverse=True)
        
        if args.format == "json":
            print(json.dumps([asdict(s) for s in summary], indent=2))
        elif args.format == "csv":
            print("sector,mean_score,median_score,std_score,pct_buy,pct_hold,pct_sell,stock_count")
            for s in summary:
                print(f"{s.sector},{s.mean_score},{s.median_score},{s.std_score},{s.pct_buy},{s.pct_hold},{s.pct_sell},{s.stock_count}")
        else:
            _print_sector_table(summary)
        
        # Save to file if requested
        if args.output:
            output_path = Path(args.output)
            if args.format == "json" or output_path.suffix == ".json":
                with open(output_path, "w") as f:
                    json.dump([asdict(s) for s in summary], f, indent=2)
            elif args.format == "csv" or output_path.suffix == ".csv":
                with open(output_path, "w") as f:
                    f.write("sector,mean_score,median_score,std_score,pct_buy,pct_hold,pct_sell,stock_count\n")
                    for s in summary:
                        f.write(f"{s.sector},{s.mean_score},{s.median_score},{s.std_score},{s.pct_buy},{s.pct_hold},{s.pct_sell},{s.stock_count}\n")
            print(f"\n✅ Saved to {output_path}")


def _print_sector_score(score: SectorScore):
    """Print a single sector score."""
    signal = "🟢 BUY" if score.mean_score >= 70 else "🔴 SELL" if score.mean_score < 40 else "🟡 HOLD"
    
    print(f"\n🏛️  {score.sector}" + (f" / {score.industry}" if score.industry else ""))
    print(f"   Date: {score.date}")
    print(f"   Signal: {signal}")
    print(f"\n   Scores:")
    print(f"     Mean:   {score.mean_score:.1f}")
    print(f"     Median: {score.median_score:.1f}")
    print(f"     Std:    {score.std_score:.1f}")
    print(f"     Range:  {score.min_score:.1f} - {score.max_score:.1f}")
    print(f"\n   Distribution:")
    print(f"     🟢 BUY:  {score.pct_buy:.1f}%")
    print(f"     🟡 HOLD: {score.pct_hold:.1f}%")
    print(f"     🔴 SELL: {score.pct_sell:.1f}%")
    print(f"\n   Coverage: {score.stock_count} stocks ({score.missing_count} imputed)")


def _print_sector_table(scores: list):
    """Print sector scores as table."""
    print(f"\n{'Sector':<25} {'Score':>8} {'Signal':>8} {'BUY%':>8} {'HOLD%':>8} {'SELL%':>8} {'Stocks':>8}")
    print("-" * 85)
    
    for s in scores:
        signal = "🟢" if s.mean_score >= 70 else "🔴" if s.mean_score < 40 else "🟡"
        print(f"{s.sector:<25} {s.mean_score:>7.1f} {signal:>8} {s.pct_buy:>7.1f}% {s.pct_hold:>7.1f}% {s.pct_sell:>7.1f}% {s.stock_count:>7}")
    
    print("-" * 85)


def cmd_sector_trends(args):
    """Generate sector trend visualizations."""
    if not MATPLOTLIB_AVAILABLE and not PLOTLY_AVAILABLE:
        print("❌ Error: matplotlib or plotly required for visualizations")
        print("   Install: pip install matplotlib plotly")
        sys.exit(1)
    
    analyzer = SectorAnalyzer()
    
    # Parse date range
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"\n📈 GENERATING SECTOR TRENDS")
    print(f"   Period: {start_date} to {end_date}")
    
    # Get sector data
    if args.sectors:
        sectors = [s.strip() for s in args.sectors.split(",")]
        sector_data = {}
        for sector in sectors:
            sector_data[sector] = analyzer.calculate_sector_trends(
                start_date=start_date,
                end_date=end_date,
                sector=sector,
                top_n=args.top_n
            )
    else:
        sector_data = analyzer.get_all_sector_trends(
            start_date=start_date,
            end_date=end_date,
            top_n=args.top_n
        )
    
    # Check for output path
    if not args.output:
        print("❌ Error: --output required for chart generation")
        sys.exit(1)
    
    output_path = Path(args.output)
    
    # Determine format
    fmt = args.format or ("html" if output_path.suffix == ".html" else "png")
    
    # Generate chart based on type
    chart_type = args.chart_type or "line"
    
    print(f"   Chart type: {chart_type}")
    print(f"   Output: {output_path}")
    
    try:
        if chart_type == "line":
            plot_sector_trends(
                sector_data,
                str(output_path),
                width=args.width,
                height=args.height,
                format=fmt
            )
        elif chart_type == "heatmap":
            plot_sector_heatmap(
                sector_data,
                str(output_path),
                width=args.width,
                height=args.height,
                format=fmt
            )
        elif chart_type == "distribution":
            plot_score_distribution(
                sector_data,
                str(output_path),
                width=args.width,
                height=args.height
            )
        elif chart_type == "stacked":
            plot_signal_distribution(
                sector_data,
                str(output_path),
                width=args.width,
                height=args.height
            )
        else:
            print(f"❌ Unknown chart type: {chart_type}")
            print("   Available: line, heatmap, distribution, stacked")
            sys.exit(1)
        
        print(f"\n✅ Chart saved to {output_path}")
        
    except Exception as e:
        print(f"❌ Error generating chart: {e}")
        sys.exit(1)


def cmd_sector_report(args):
    """Generate comprehensive sector report."""
    if not MATPLOTLIB_AVAILABLE:
        print("❌ Error: matplotlib required for report generation")
        print("   Install: pip install matplotlib")
        sys.exit(1)
    
    analyzer = SectorAnalyzer()
    
    # Parse date range
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"\n📊 GENERATING SECTOR PERFORMANCE REPORT")
    print(f"   Period: {start_date} to {end_date}")
    
    # Get sector data
    sector_data = analyzer.get_all_sector_trends(
        start_date=start_date,
        end_date=end_date,
        top_n=args.top_n
    )
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"   Output directory: {output_dir}")
    
    # Generate all charts
    generated = generate_sector_report(
        sector_data,
        str(output_dir),
        title="Sigil Sector Performance"
    )
    
    # Generate summary JSON
    summary = analyzer.get_latest_sector_summary()
    summary_path = output_dir / "sector_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "period": {"start": start_date, "end": end_date},
            "sectors": summary
        }, f, indent=2)
    
    print(f"\n✅ Report generated successfully!")
    print(f"\n   Generated files:")
    for name, path in generated.items():
        print(f"     {name}: {path}")
    print(f"     summary: {summary_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sigil Sector Performance Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all sectors and industries
  python3 -m src.analytics list-sectors

  # Get sector scores for today
  python3 -m src.analytics sector-scores

  # Get scores for specific sector
  python3 -m src.analytics sector-scores --sector "Technology"

  # Generate trend chart
  python3 -m src.analytics sector-trends --output trends.png

  # Generate heatmap
  python3 -m src.analytics sector-trends --chart-type heatmap --output heatmap.png

  # Generate full report
  python3 -m src.analytics sector-report --output ./reports/sector_analysis/
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # list-sectors command
    list_parser = subparsers.add_parser("list-sectors", help="List all sectors and industries")
    list_parser.set_defaults(func=cmd_list_sectors)
    
    # sector-scores command
    scores_parser = subparsers.add_parser("sector-scores", help="Calculate sector scores")
    scores_parser.add_argument("--date", help="Date (YYYY-MM-DD), defaults to latest")
    scores_parser.add_argument("--sector", help="Filter by sector name")
    scores_parser.add_argument("--industry", help="Filter by industry name")
    scores_parser.add_argument("--top-n", type=int, help="Limit to top N stocks by market cap")
    scores_parser.add_argument("--output", help="Output file path")
    scores_parser.add_argument("--format", choices=["table", "json", "csv"], default="table",
                              help="Output format")
    scores_parser.set_defaults(func=cmd_sector_scores)
    
    # sector-trends command
    trends_parser = subparsers.add_parser("sector-trends", help="Generate sector trend charts")
    trends_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    trends_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    trends_parser.add_argument("--sectors", help="Comma-separated sector names")
    trends_parser.add_argument("--top-n", type=int, help="Limit to top N stocks by market cap")
    trends_parser.add_argument("--chart-type", choices=["line", "heatmap", "distribution", "stacked"],
                              default="line", help="Chart type")
    trends_parser.add_argument("--output", required=True, help="Output file path (PNG or HTML)")
    trends_parser.add_argument("--format", choices=["png", "html"], help="Output format")
    trends_parser.add_argument("--width", type=int, default=1200, help="Chart width in pixels")
    trends_parser.add_argument("--height", type=int, default=700, help="Chart height in pixels")
    trends_parser.set_defaults(func=cmd_sector_trends)
    
    # sector-report command
    report_parser = subparsers.add_parser("sector-report", help="Generate comprehensive report")
    report_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    report_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    report_parser.add_argument("--top-n", type=int, help="Limit to top N stocks by market cap")
    report_parser.add_argument("--output", required=True, help="Output directory")
    report_parser.set_defaults(func=cmd_sector_report)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    args.func(args)


if __name__ == "__main__":
    main()
