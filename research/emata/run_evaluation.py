#!/usr/bin/env python3
"""
Run the EMATA evaluation with Sigil's actual composite score data.
Produces comparative results across all retrieval strategies.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add emata to path
sys.path.insert(0, str(Path(__file__).parent))

from emata.evaluation import SyntheticDataGenerator, Evaluator


def main():
    sigil_scores = Path(__file__).parent / "../../backend/data/composite_scores.json"
    
    scores_path = str(sigil_scores) if sigil_scores.exists() else None
    print(f"Sigil scores: {'LOADED' if scores_path else 'NOT FOUND (using synthetic)'}")
    
    # Generate episodes
    print("\n📊 Generating synthetic episodes...")
    gen = SyntheticDataGenerator(scores_path=scores_path, seed=42)
    
    # 500 episodes for statistical significance
    episodes = gen.generate_episodes(n=500)
    print(f"   Generated {len(episodes)} episodes")
    
    # Distribution summary
    regimes = {}
    for ep in episodes:
        r = ep.context.regime
        regimes[r] = regimes.get(r, 0) + 1
    print(f"   Regime distribution: {regimes}")
    
    outcomes = [ep.outcome.pct_return for ep in episodes]
    import numpy as np
    print(f"   Outcome range: [{min(outcomes):.1f}%, {max(outcomes):.1f}%]")
    print(f"   Mean outcome: {np.mean(outcomes):+.2f}%")
    
    # Generate evaluation scenarios
    print("\n🎯 Generating evaluation scenarios...")
    scenarios = gen.generate_eval_scenarios(episodes, n_scenarios=100)
    print(f"   Generated {len(scenarios)} scenarios")
    
    # Run evaluation
    print("\n🔬 Running comparative evaluation...")
    evaluator = Evaluator(episodes, scenarios)
    results = evaluator.evaluate_all(k=10)
    
    # Print results
    report = evaluator.format_comparison(results)
    print("\n" + report)
    
    # Save results
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    results_dict = {name: m.to_dict() for name, m in results.items()}
    results_dict["metadata"] = {
        "timestamp": datetime.utcnow().isoformat(),
        "num_episodes": len(episodes),
        "num_scenarios": len(scenarios),
        "sigil_scores_used": bool(scores_path),
        "k": 10,
    }
    
    with open(output_dir / "evaluation_results.json", 'w') as f:
        json.dump(results_dict, f, indent=2)
    
    with open(output_dir / "evaluation_report.txt", 'w') as f:
        f.write(report)
    
    print(f"\n💾 Results saved to {output_dir}")
    print(f"   - evaluation_results.json")
    print(f"   - evaluation_report.txt")
    
    return results


if __name__ == "__main__":
    main()
