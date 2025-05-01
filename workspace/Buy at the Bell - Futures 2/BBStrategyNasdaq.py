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
from System.Collections.Generic import List

### <summary>
### Demonstration of using coarse and fine universe selection together to filter down a smaller universe of stocks.
### </summary>
### <meta name="tag" content="using data" />
### <meta name="tag" content="universes" />
### <meta name="tag" content="coarse universes" />
### <meta name="tag" content="fine universes" />
class CoarseFineFundamentalComboAlgorithm(QCAlgorithm):

    def Initialize(self):
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialized.'''

        self.SetStartDate(2014,1,1)  #Set Start Date
        self.SetEndDate(2015,1,1)    #Set End Date
        self.SetCash(500000)            #Set Strategy Cash

        # what resolution should the data *added* to the universe be?
        self.UniverseSettings.Resolution = Resolution.Daily

        # this add universe method accepts two parameters:
        # - coarse selection function: accepts an IEnumerable<CoarseFundamental> and returns an IEnumerable<Symbol>
        # - fine selection function: accepts an IEnumerable<FineFundamental> and returns an IEnumerable<Symbol>
        #self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        # ETFs
        # IWB iShares Russell 1000 ETF
        # IWM iShares Russell 2000 ETF
        # IWV iShares Russell 3000 ETF    =
        # SPY SPDR S&P 500

        self.etf = "IWB"
        self.securities = self.AddUniverseSelection(ETFUniverseSelectionModel(self.UniverseSettings, self.etf))

        self._changes = None

    # sort the data by daily dollar volume and take the top 'NumberOfSymbols'
    def CoarseSelectionFunction(self, coarse):       
        # Allows all Symbols through, no filtering applied
        return [coarse_data.Symbol for coarse_data in coarse]
    
    # sort the data by P/E ratio and take the top 'NumberOfSymbolsFine'
    def FineSelectionFunction(self, fine):
        # Allows all Symbols through, no filtering applied
        return [fine_data.Symbol for fine_data in fine]
        

    def OnData(self, data):
        # if we have no changes, do nothing
        if self.securities is None: return

        # BUY THEM ALL
        for security in self.securities:
            self.SetHoldings(security.Symbol, 0.001)

    # this event fires whenever we have changes to our universe
    def OnSecuritiesChanged(self, changes):
        self._changes = changes


# Outside of the algorithm class
class ETFUniverseSelectionModel(ETFConstituentsUniverseSelectionModel, etf):
    def __init__(self, universe_settings: UniverseSettings = None) -> None:
        symbol = Symbol.Create(etf, SecurityType.Equity, Market.USA)
        super().__init__(symbol, universe_settings, self.ETFConstituentsFilter)

    def ETFConstituentsFilter(self, constituents: List[ETFConstituentData]) -> List[Symbol]:
        selected = sorted([c for c in constituents if c.Weight],
            key=lambda c: c.Weight, reverse=True)[:10]
        return [c.Symbol for c in selected]
