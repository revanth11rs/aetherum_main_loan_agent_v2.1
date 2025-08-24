
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class AssetInput:
    symbol: str
    allocation_usd: float

@dataclass
class LoanRequest:
    assets: List[AssetInput]  # [{symbol, allocation_usd}]
    months: int = 6
    payout_currency: str = "USDC"
    bank: str = "American Bank"
    extra_context: Dict = None
