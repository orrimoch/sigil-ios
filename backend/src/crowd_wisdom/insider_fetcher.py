"""
REC-251: OpenInsider Data Fetcher

Fetches insider buying transactions from OpenInsider.
Filters: Tech sector, price < $30, BUYS only.
"""

import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Optional
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class InsiderTransaction:
    """Single insider buying transaction."""
    filing_date: date
    trade_date: date
    ticker: str
    company_name: str
    insider_name: str
    insider_title: str  # CEO, CFO, Dir, 10%, etc.
    trade_type: str  # P = Purchase, S = Sale
    price: float
    quantity: int
    shares_owned: int
    ownership_change_pct: float
    value: float
    
    @property
    def is_executive(self) -> bool:
        """Check if insider is C-suite executive."""
        exec_titles = ['CEO', 'CFO', 'COO', 'CTO', 'President', 'Pres']
        return any(t in self.insider_title for t in exec_titles)
    
    @property
    def is_director(self) -> bool:
        """Check if insider is a director."""
        return 'Dir' in self.insider_title
    
    @property
    def is_large_owner(self) -> bool:
        """Check if 10%+ owner."""
        return '10%' in self.insider_title


class InsiderFetcher:
    """
    Fetches insider transactions from OpenInsider.
    
    URL Pattern:
    http://openinsider.com/screener?s=&o=&pl=&ph=30&ll=&lh=&fd=7&...
    
    Key params:
    - ph=30: Price high (max $30)
    - fd=7: Filing in last 7 days
    - pt=1: Purchase transactions only
    """
    
    BASE_URL = "http://openinsider.com/screener"
    
    # Tech sector SIC codes (simplified - major tech ranges)
    TECH_SIC_CODES = [
        (3570, 3579),  # Computer and office equipment
        (3600, 3699),  # Electronic equipment
        (4800, 4899),  # Communications
        (7370, 7379),  # Computer programming/software
    ]
    
    def __init__(self, max_price: float = 30.0, days_back: int = 7):
        self.max_price = max_price
        self.days_back = days_back
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def fetch_insider_buys(self, tech_only: bool = True) -> List[InsiderTransaction]:
        """
        Fetch recent insider buying transactions.
        
        Args:
            tech_only: If True, filter to tech sector only
            
        Returns:
            List of InsiderTransaction objects
        """
        params = {
            's': '',  # Symbol (empty = all)
            'o': '',  # Owner (empty = all)
            'pl': '',  # Price low
            'ph': str(int(self.max_price)),  # Price high
            'll': '',  # Holdings low
            'lh': '',  # Holdings high
            'fd': str(self.days_back),  # Filing in last N days
            'td': '',  # Trade date
            'xp': '1',  # Exclude private transactions
            'vl': '',  # Value low
            'vh': '',  # Value high
            'pt': '1',  # Purchase transactions only (1=buy)
            'tc': '1',  # Transaction code
            'sc': '1',  # Show companies
        }
        
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            transactions = self._parse_html(response.text)
            
            if tech_only:
                transactions = self._filter_tech_sector(transactions)
            
            logger.info(f"Fetched {len(transactions)} insider transactions")
            return transactions
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch from OpenInsider: {e}")
            return []
    
    def _parse_html(self, html: str) -> List[InsiderTransaction]:
        """Parse OpenInsider HTML table into transactions."""
        soup = BeautifulSoup(html, 'html.parser')
        transactions = []
        
        # Find the main data table
        table = soup.find('table', class_='tinytable')
        if not table:
            logger.warning("Could not find data table in OpenInsider response")
            return []
        
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            try:
                txn = self._parse_row(row)
                if txn:
                    transactions.append(txn)
            except Exception as e:
                logger.debug(f"Failed to parse row: {e}")
                continue
        
        return transactions
    
    def _parse_row(self, row) -> Optional[InsiderTransaction]:
        """Parse a single table row into InsiderTransaction."""
        cells = row.find_all('td')
        if len(cells) < 13:
            return None
        
        try:
            # Extract data from cells
            filing_date_str = cells[1].get_text(strip=True)
            trade_date_str = cells[2].get_text(strip=True)
            
            ticker_link = cells[3].find('a')
            ticker = ticker_link.get_text(strip=True) if ticker_link else cells[3].get_text(strip=True)
            
            company_link = cells[4].find('a')
            company_name = company_link.get_text(strip=True) if company_link else cells[4].get_text(strip=True)
            
            insider_link = cells[5].find('a')
            insider_name = insider_link.get_text(strip=True) if insider_link else cells[5].get_text(strip=True)
            
            insider_title = cells[6].get_text(strip=True)
            trade_type = cells[7].get_text(strip=True)
            
            price_str = cells[8].get_text(strip=True).replace('$', '').replace(',', '')
            price = float(price_str) if price_str else 0.0
            
            qty_str = cells[9].get_text(strip=True).replace('+', '').replace(',', '').replace('-', '')
            quantity = int(qty_str) if qty_str else 0
            
            owned_str = cells[10].get_text(strip=True).replace(',', '')
            shares_owned = int(owned_str) if owned_str else 0
            
            change_str = cells[11].get_text(strip=True).replace('%', '').replace('+', '')
            ownership_change = float(change_str) if change_str and change_str != 'New' else 100.0
            
            value_str = cells[12].get_text(strip=True).replace('$', '').replace(',', '').replace('+', '')
            value = float(value_str) if value_str else 0.0
            
            # Parse dates
            filing_date = self._parse_date(filing_date_str)
            trade_date = self._parse_date(trade_date_str)
            
            if not filing_date or not trade_date:
                return None
            
            # Only include purchases (P = Purchase)
            if trade_type != 'P' and 'P' not in trade_type:
                return None
            
            return InsiderTransaction(
                filing_date=filing_date,
                trade_date=trade_date,
                ticker=ticker,
                company_name=company_name,
                insider_name=insider_name,
                insider_title=insider_title,
                trade_type=trade_type,
                price=price,
                quantity=quantity,
                shares_owned=shares_owned,
                ownership_change_pct=ownership_change,
                value=value
            )
            
        except (ValueError, IndexError) as e:
            logger.debug(f"Error parsing row: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string in various formats."""
        if not date_str:
            return None
        
        # Try different date formats
        formats = ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y']
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str[:10], fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _filter_tech_sector(self, transactions: List[InsiderTransaction]) -> List[InsiderTransaction]:
        """
        Filter transactions to tech sector only.
        Uses company name keywords as proxy (proper SIC lookup would need SEC data).
        """
        tech_keywords = [
            'software', 'tech', 'digital', 'data', 'cloud', 'cyber', 
            'semiconductor', 'chip', 'computing', 'network', 'internet',
            'ai', 'artificial', 'machine', 'automation', 'robot',
            'saas', 'platform', 'systems', 'solutions', 'analytics',
            'communications', 'wireless', 'mobile', 'app', 'gaming'
        ]
        
        tech_companies = []
        for txn in transactions:
            company_lower = txn.company_name.lower()
            if any(kw in company_lower for kw in tech_keywords):
                tech_companies.append(txn)
        
        return tech_companies
    
    def get_cluster_buys(self, transactions: List[InsiderTransaction], min_insiders: int = 3) -> dict:
        """
        Detect cluster buying - multiple insiders buying same stock.
        
        Args:
            transactions: List of transactions
            min_insiders: Minimum insiders for cluster (default 3)
            
        Returns:
            Dict of ticker -> list of transactions
        """
        by_ticker = {}
        for txn in transactions:
            if txn.ticker not in by_ticker:
                by_ticker[txn.ticker] = []
            by_ticker[txn.ticker].append(txn)
        
        # Filter to clusters
        clusters = {
            ticker: txns 
            for ticker, txns in by_ticker.items() 
            if len(set(t.insider_name for t in txns)) >= min_insiders
        }
        
        return clusters


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetcher = InsiderFetcher(max_price=30, days_back=7)
    
    print("Fetching insider buys...")
    transactions = fetcher.fetch_insider_buys(tech_only=False)
    
    print(f"\nFound {len(transactions)} transactions")
    for txn in transactions[:10]:
        print(f"  {txn.ticker}: {txn.insider_name} ({txn.insider_title}) bought ${txn.value:,.0f}")
