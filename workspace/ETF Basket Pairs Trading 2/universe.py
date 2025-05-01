#region imports
from AlgorithmImports import *
#endregion

class SectorETFUniverseSelectionModel(ETFConstituentsUniverseSelectionModel):
    def __init__(self, universe_settings: UniverseSettings = None) -> None:
        # Select the tech sector ETF constituents to get correlated assets
        symbol = Symbol.Create("IYM", SecurityType.Equity, Market.USA)
        super().__init__(symbol, universe_settings, self.ETFConstituentsFilter)

    def ETFConstituentsFilter(self, constituents: List[ETFConstituentData]) -> List[Symbol]:
        # Get the 10 securities with the largest weight in the index to reduce slippage and keep speed of the algorithm
        selected = sorted([c for c in constituents if c.Weight], 
                          key=lambda c: c.Weight, reverse=True)
        return [c.Symbol for c in selected[:10]]

