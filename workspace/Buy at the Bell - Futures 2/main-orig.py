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
from QuantConnect.Indicators import BollingerBands

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

        # Recreate "Serious RSI-Bolling Bandwidth Strategy.ipynb"
        #Russell-3000
        #2021-11-29
        #2023-11-28

        self.SetStartDate(2021,11,29)   #Set Start Date
        self.SetEndDate(2023,11,28)     #Set End Date
        self.SetCash(100000)             #Set Strategy Cash

        # Select resolution
        resolution = Resolution.Daily

        # what resolution should the data *added* to the universe be?
        self.UniverseSettings.Resolution = resolution

        # this add universe method accepts two parameters:
        # - coarse selection function: accepts an IEnumerable<CoarseFundamental> and returns an IEnumerable<Symbol>
        # - fine selection function: accepts an IEnumerable<FineFundamental> and returns an IEnumerable<Symbol>
        #self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        # ETFs
        # IWB iShares Russell 1000 ETF
        # IWM iShares Russell 2000 ETF
        # IWV iShares Russell 3000 ETF
        # SPY SPDR S&P 500

        self.etf = "IWB"
        
        self.AddUniverseSelection(ETFUniverseSelectionModel(self.UniverseSettings))
        self.SetAlpha(IntradayReversalAlphaModel(5, resolution))
        self._changes = None

        # Equally weigh securities in portfolio, based on insights
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())

        # Set Immediate Execution Model
        self.SetExecution(ImmediateExecutionModel())

        # Set Null Risk Management Model
        self.SetRiskManagement(NullRiskManagementModel())

        #Set WarmUp for Indicators
        self.SetWarmUp(30, resolution)

    # sort the data by daily dollar volume and take the top 'NumberOfSymbols'
    def CoarseSelectionFunction(self, coarse):       
        # Allows all Symbols through, no filtering applied
        return [coarse_data.Symbol for coarse_data in coarse]
    
    # sort the data by P/E ratio and take the top 'NumberOfSymbolsFine'
    def FineSelectionFunction(self, fine):
        # Allows all Symbols through, no filtering applied
        return [fine_data.Symbol for fine_data in fine]        

    ###
    ##def OnData(self, data):
    ##
    ##    if self.IsWarmingUp: 
    ##        return

    ##   # BUY THEM ALL!!
    ##    for security in self.ActiveSecurities.Values:
    ##        try:
    ##            self.SetHoldings(security.Symbol, 0.01)
    ##        except Exception as e:
    ##            self.Debug(e)

    # this event fires whenever we have changes to our universe
    def OnSecuritiesChanged(self, changes):
        self._changes = changes

# Outside of the algorithm class
class ETFUniverseSelectionModel(ETFConstituentsUniverseSelectionModel):
    def __init__(self, universe_settings: UniverseSettings = None) -> None:
        symbol = Symbol.Create("IWB", SecurityType.Equity, Market.USA)
        super().__init__(symbol, universe_settings, self.ETFConstituentsFilter)

    def ETFConstituentsFilter(self, constituents: List[ETFConstituentData]) -> List[Symbol]:
        selected = sorted([c for c in constituents if c.Weight],
            key=lambda c: c.Weight, reverse=True)
        result = [c.Symbol for c in selected]
        return result

class IntradayReversalAlphaModel(AlphaModel):
    '''Alpha model that uses a Price/SMA Crossover to create insights on Hourly Frequency.
    Frequency: Hourly data with 5-hour simple moving average.
    Strategy:
    Reversal strategy that goes Long when price crosses below SMA and Short when price crosses above SMA.
    The trading strategy is implemented only between 10AM - 3PM (NY time)'''

    # Initialize variables
    def __init__(self, period_sma = 5, resolution = Resolution.Daily):
        self.period_sma = period_sma
        self.resolution = resolution
        self.cache = {} # Cache for SymbolData
        self.Name = 'IntradayReversalAlphaModel'

    def Update(self, algorithm, data):
        # Set the time to close all positions at 3PM
        #timeToClose = algorithm.Time.replace(hour=15, minute=1, second=0)
        timeToClose = algorithm.Time.replace(day=20)

        insights = []
        for kvp in algorithm.ActiveSecurities:

            symbol = kvp.Key

            #if self.ShouldEmitInsight(algorithm, symbol) and symbol in self.cache:
            #if symbol in self.cache:
            price = kvp.Value.Price
            symbolData = self.cache[symbol]

            direction = InsightDirection.Up if symbolData.is_uptrend(price, algorithm) else InsightDirection.Down

            # Ignore signal for same direction as previous signal (when no crossover)
            if direction == symbolData.PreviousDirection:
                continue

            # Save the current Insight Direction to check when the crossover happens
            symbolData.PreviousDirection = direction
            
            # Generate insight
            #insights.append(Insight.Price(symbol, timeToClose, direction))
            #insights.append(Insight.Price(symbol, Resolution.Daily, 20, direction))

        return insights

    def OnSecuritiesChanged(self, algorithm, changes):
        '''Handle creation of the new security and its cache class.
        Simplified in this example as there is 1 asset.'''
        
        for security in changes.AddedSecurities:
            self.cache[security.Symbol] = SymbolData(algorithm, security.Symbol, self.period_sma, self.resolution)

        #for security in changes.RemovedSecurities:
        #    self.cache.pop(security.Symbol)
            
    def ShouldEmitInsight(self, algorithm, symbol):
        '''Time to control when to start and finish emitting (10AM to 3PM)'''
        timeOfDay = algorithm.Time.time()
        return algorithm.Securities[symbol].HasData and timeOfDay >= time(10) and timeOfDay <= time(15)

class SymbolData:
    def __init__(self, algorithm, symbol, period_sma, resolution):
        self.symbol = symbol
        self.PreviousDirection = InsightDirection.Flat
        self.priceSMA = algorithm.SMA(symbol, period_sma, resolution)        
            
        #Bollinger Bands
        # 30 bars
        self.bb = algorithm.BB(symbol, 30, 2, MovingAverageType.Simple, resolution)

        #Relative Strength Index
        # Last 14 candles
        self.rsi = algorithm.RSI(symbol, 14, resolution)
                
        #Average True Range
        self.atr = algorithm.ATR(symbol, 1, MovingAverageType.Simple, resolution)

        #RSI History
        self.rsi_window = RollingWindow[RelativeStrengthIndex](3)

        #Bollinger Bandwidth History
        # (Upper - Lower) / Middle
        self.bbandwidth_window = RollingWindow[BollingerBands](3)

        #ATR History
        self.atr_window = RollingWindow[AverageTrueRange](3)

        # Need to store some recent historical TradeBar data
        self.trade_bar_window = RollingWindow[TradeBar](3)


    def is_uptrend(self, price, algorithm):

        self.quant = 0
        self.investment = 1000

        # Get 3 previous Bars
        #From https://www.quantconnect.com/docs/v2/writing-algorithms/indicators/rolling-window        
        history_trade_bar = algorithm.History[TradeBar](self.symbol, 3, Resolution.Daily)

        # Warm up the quote bar rolling window with the previous 3 days of quote bar data
        for trade_bar in history_trade_bar:
            self.trade_bar_window.Add(trade_bar)

        if self.priceSMA.IsReady and self.bb.IsReady and self.rsi.IsReady and self.atr.IsReady:
            self.bbandwidth_window.Add(self.bb)
            self.rsi_window.Add(self.rsi)
            self.atr_window.Add(self.atr)

            if self.bbandwidth_window.Count < 3:                
                return

            self.bbandwidth = (self.bbandwidth_window[2].UpperBand.Current.Value - self.bbandwidth_window[2].LowerBand.Current.Value) / self.bbandwidth_window[2].MiddleBand.Current.Value
            #self.bbandwidth = (self.bb.UpperBand.Current.Value - self.bb.LowerBand.Current.Value) / self.bb.MiddleBand.Current.Value

            c0 = self.trade_bar_window[2].Close < self.trade_bar_window[2].Open
            c1 = self.trade_bar_window[2].Low < self.bbandwidth_window[2].LowerBand.Current.Value
            
            c3 = self.rsi_window[2].Current.Value < 25
            c4 = self.trade_bar_window[1].Close > self.trade_bar_window[1].Open
            c5 = self.trade_bar_window[1].Close > self.trade_bar_window[2].High
            c6 = self.bbandwidth >= 0.27

            c7 = self.trade_bar_window[0].Close < self.trade_bar_window[0].Open
            #c7 = self.trade_bar_window[0].Close == self.trade_bar_window[0].Close
                
            if c0 & c1 & c3 & c4 & c5 & c6 & c7:

                buyhere = False
                if buyhere == True:
                    self.quant = int((self.investment) / price)

                    # Buy orders
                    ticket = algorithm.MarketOrder(self.symbol, self.quant)

                    # From https://www.quantconnect.com/forum/discussion/1072/setting-a-stop-loss-and-take-profit/p2
                    # Should be entry price, not current price!
                    tp = price + (self.atr_window[1].Current.Price * 1.4)
                    stop = price - (self.atr_window[1].Current.Price * 1.8)
                
                    self.sl = algorithm.StopMarketOrder(self.symbol, -self.quant, stop)
                    self.tp = algorithm.LimitOrder(self.symbol, -self.quant, tp)

                    algorithm.Debug(f"Bought {{self.symbol.Value}} at {{price}}")
                
                return True

            return False
    

