 # QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from AlgorithmImports import *

### <summary>
### Strategy example algorithm using CAPE - a bubble indicator dataset saved in dropbox. CAPE is based on a macroeconomic indicator(CAPE Ratio),
### we are looking for entry/exit points for momentum stocks CAPE data: January 1990 - December 2014
### Goals:
### Capitalize in overvalued markets by generating returns with momentum and selling before the crash
### Capitalize in undervalued markets by purchasing stocks at bottom of trough
### </summary>
### <meta name="tag" content="strategy example" />
### <meta name="tag" content="custom data" />
class SleepyRedJackal(QCAlgorithm):

    def initialize(self):

        # ETFs
        # IWB iShares Russell 1000 ETF
        # IWM iShares Russell 2000 ETF
        # IWV iShares Russell 3000 ETF
        # SPY SPDR S&P 500

        self.etf = "IWV"
        
        self.AddUniverseSelection(ETFUniverseSelectionModel(self.UniverseSettings))
        self._changes = None

        # Equally weigh securities in portfolio, based on insights
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())

        # Set Immediate Execution Model
        self.SetExecution(ImmediateExecutionModel())

        # Set Null Risk Management Model
        self.SetRiskManagement(NullRiskManagementModel())

        #Set WarmUp for Indicators
        self.SetWarmUp(30, Resolution.DAILY)


 # Outside of the algorithm class
class ETFUniverseSelectionModel(ETFConstituentsUniverseSelectionModel):
    def __init__(self, universe_settings: UniverseSettings = None) -> None:
        symbol = Symbol.Create("IWV", SecurityType.Equity, Market.USA)
        super().__init__(symbol, universe_settings, self.ETFConstituentsFilter)

    def ETFConstituentsFilter(self, constituents: List[ETFConstituentData]) -> List[Symbol]:
        selected = sorted([c for c in constituents if c.Weight],
            key=lambda c: c.Weight, reverse=True)
        result = [c.Symbol for c in selected]
        return result
