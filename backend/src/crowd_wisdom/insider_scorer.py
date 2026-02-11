"""
REC-253: Insider Signal Scoring

Calculates insider buying signal scores (0-100) from transaction data.
Weights by: insider role, transaction size, cluster detection.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from collections import defaultdict
import logging

from .insider_fetcher import InsiderTransaction

logger = logging.getLogger(__name__)


@dataclass
class InsiderScore:
    """Insider buying score for a stock."""
    ticker: str
    company_name: str
    insider_score: float  # 0-100
    insider_buy_count: int
    insider_buy_value: float
    insider_cluster: bool
    executive_buys: int
    director_buys: int
    large_owner_buys: int
    notable_events: List[str]
    signal: str  # STRONG_BUY, BUY, NEUTRAL


class InsiderScorer:
    """
    Calculates insider buying scores.
    
    Scoring factors:
    - Number of insider buys (more = higher)
    - Total value of buys (higher = better)
    - Insider role (CEO/CFO > Director > 10% owner)
    - Cluster buying (3+ insiders = bonus)
    - Recency (recent buys weighted more)
    """
    
    # Weights for different insider types
    ROLE_WEIGHTS = {
        'executive': 3.0,  # CEO, CFO, COO, CTO, President
        'director': 2.0,   # Board members
        'large_owner': 1.5,  # 10%+ owners
        'other': 1.0
    }
    
    # Value thresholds for scoring
    VALUE_TIERS = [
        (10_000_000, 40),   # $10M+ = 40 points
        (1_000_000, 30),    # $1M+ = 30 points
        (500_000, 20),      # $500K+ = 20 points
        (100_000, 15),      # $100K+ = 15 points
        (50_000, 10),       # $50K+ = 10 points
        (10_000, 5),        # $10K+ = 5 points
        (0, 2)              # Any amount = 2 points
    ]
    
    # Cluster bonus
    CLUSTER_THRESHOLD = 3  # 3+ unique insiders
    CLUSTER_BONUS = 15
    
    # Executive bonus
    EXECUTIVE_BONUS = 10
    
    def __init__(self):
        pass
    
    def score_transactions(self, transactions: List[InsiderTransaction]) -> List[InsiderScore]:
        """
        Calculate insider scores for all stocks in transactions.
        
        Args:
            transactions: List of insider transactions
            
        Returns:
            List of InsiderScore objects, sorted by score descending
        """
        # Group transactions by ticker
        by_ticker = defaultdict(list)
        for txn in transactions:
            by_ticker[txn.ticker].append(txn)
        
        # Calculate score for each ticker
        scores = []
        for ticker, txns in by_ticker.items():
            score = self._calculate_score(ticker, txns)
            if score.insider_score > 0:
                scores.append(score)
        
        # Sort by score descending
        scores.sort(key=lambda s: s.insider_score, reverse=True)
        
        return scores
    
    def _calculate_score(self, ticker: str, transactions: List[InsiderTransaction]) -> InsiderScore:
        """Calculate insider score for a single stock."""
        
        # Basic counts
        buy_count = len(transactions)
        total_value = sum(t.value for t in transactions)
        
        # Unique insiders (for cluster detection)
        unique_insiders = set(t.insider_name for t in transactions)
        is_cluster = len(unique_insiders) >= self.CLUSTER_THRESHOLD
        
        # Count by role
        exec_buys = sum(1 for t in transactions if t.is_executive)
        dir_buys = sum(1 for t in transactions if t.is_director and not t.is_executive)
        owner_buys = sum(1 for t in transactions if t.is_large_owner)
        
        # Company name (from first transaction)
        company_name = transactions[0].company_name if transactions else ticker
        
        # Calculate base score from value
        value_score = self._value_to_score(total_value)
        
        # Add role-weighted count score
        role_score = 0
        for txn in transactions:
            if txn.is_executive:
                role_score += self.ROLE_WEIGHTS['executive'] * 5
            elif txn.is_director:
                role_score += self.ROLE_WEIGHTS['director'] * 5
            elif txn.is_large_owner:
                role_score += self.ROLE_WEIGHTS['large_owner'] * 5
            else:
                role_score += self.ROLE_WEIGHTS['other'] * 5
        
        # Cap role score at 30
        role_score = min(role_score, 30)
        
        # Bonuses
        cluster_bonus = self.CLUSTER_BONUS if is_cluster else 0
        exec_bonus = self.EXECUTIVE_BONUS if exec_buys > 0 else 0
        
        # Total score (capped at 100)
        total_score = min(100, value_score + role_score + cluster_bonus + exec_bonus)
        
        # Generate notable events
        notable_events = self._generate_notable_events(transactions, is_cluster)
        
        # Determine signal
        signal = self._score_to_signal(total_score)
        
        return InsiderScore(
            ticker=ticker,
            company_name=company_name,
            insider_score=round(total_score, 1),
            insider_buy_count=buy_count,
            insider_buy_value=total_value,
            insider_cluster=is_cluster,
            executive_buys=exec_buys,
            director_buys=dir_buys,
            large_owner_buys=owner_buys,
            notable_events=notable_events,
            signal=signal
        )
    
    def _value_to_score(self, value: float) -> float:
        """Convert total buy value to score component."""
        for threshold, score in self.VALUE_TIERS:
            if value >= threshold:
                return score
        return 0
    
    def _score_to_signal(self, score: float) -> str:
        """Convert score to signal string."""
        if score >= 70:
            return "STRONG_BUY"
        elif score >= 50:
            return "BUY"
        else:
            return "NEUTRAL"
    
    def _generate_notable_events(self, transactions: List[InsiderTransaction], is_cluster: bool) -> List[str]:
        """Generate human-readable notable events."""
        events = []
        
        # Cluster alert
        if is_cluster:
            unique_count = len(set(t.insider_name for t in transactions))
            events.append(f"{unique_count} insiders bought in the same period")
        
        # Executive buys
        exec_txns = [t for t in transactions if t.is_executive]
        for txn in exec_txns[:2]:  # Limit to top 2
            events.append(f"{txn.insider_title} {txn.insider_name} bought ${txn.value:,.0f}")
        
        # Large buys (>$1M)
        large_buys = [t for t in transactions if t.value >= 1_000_000 and not t.is_executive]
        for txn in large_buys[:2]:
            events.append(f"{txn.insider_name} bought ${txn.value:,.0f}")
        
        # Total value summary
        total = sum(t.value for t in transactions)
        if total >= 100_000:
            events.append(f"Total insider buying: ${total:,.0f}")
        
        return events[:5]  # Limit to 5 events
    
    def get_top_picks(self, scores: List[InsiderScore], n: int = 5) -> List[InsiderScore]:
        """Get top N stocks by insider score."""
        return scores[:n]


def calculate_weekly_scores(transactions: List[InsiderTransaction]) -> List[Dict[str, Any]]:
    """
    Convenience function to calculate weekly scores.
    
    Args:
        transactions: List of insider transactions
        
    Returns:
        List of score dicts ready for storage
    """
    scorer = InsiderScorer()
    scores = scorer.score_transactions(transactions)
    
    # Convert to dicts
    return [
        {
            'ticker': s.ticker,
            'company_name': s.company_name,
            'insider_score': s.insider_score,
            'insider_buy_count': s.insider_buy_count,
            'insider_buy_value': s.insider_buy_value,
            'insider_cluster': s.insider_cluster,
            'executive_buys': s.executive_buys,
            'notable_events': s.notable_events,
            'signal': s.signal,
            'discovery_reason': f"Insider buying detected: {s.insider_buy_count} transactions, ${s.insider_buy_value:,.0f} total"
        }
        for s in scores
    ]


# Quick test
if __name__ == "__main__":
    from insider_fetcher import InsiderFetcher
    
    print("Fetching insider buys...")
    fetcher = InsiderFetcher(max_price=30, days_back=7)
    transactions = fetcher.fetch_insider_buys(tech_only=False)
    
    print(f"\nScoring {len(transactions)} transactions...")
    scorer = InsiderScorer()
    scores = scorer.score_transactions(transactions)
    
    print(f"\nTop 5 by insider score:")
    for i, score in enumerate(scores[:5], 1):
        print(f"  {i}. {score.ticker} ({score.company_name[:30]})")
        print(f"     Score: {score.insider_score}, Signal: {score.signal}")
        print(f"     Buys: {score.insider_buy_count}, Value: ${score.insider_buy_value:,.0f}")
        print(f"     Events: {score.notable_events[:2]}")
        print()
