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

class SmaCrossUniverseSelectionAlgorithm(QCAlgorithm):
    '''Provides an example where WarmUpIndicator method is used to warm up indicators
    after their security is added and before (Universe Selection scenario)'''

    count = 10
    tolerance = 0.01
    targetPercent = 1 / count
    averages = dict()

    def Initialize(self, filterFineData = True, universeSettings = None):

        super().Initialize(filterFineData,  universeSettings)


        self.UniverseSettings.Leverage = 2
        self.UniverseSettings.Resolution = Resolution.Daily

        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2019, 1, 1)
        self.SetCash(1000000)

        self.EnableAutomaticIndicatorWarmUp = True

        ibm = self.AddEquity("IBM", Resolution.Minute).Symbol
        ibmSma = self.SMA(ibm, 40)
        self.Log(f"{ibmSma.Name}: {ibmSma.Current.Time} - {ibmSma}. IsReady? {ibmSma.IsReady}")

        spy = self.AddEquity("SPY", Resolution.Hour).Symbol
        spySma = self.SMA(spy, 10)     # Data point indicator
        spyAtr = self.ATR(spy, 10,)    # Bar indicator
        spyVwap = self.VWAP(spy, 10)   # TradeBar indicator
        self.Log(f"SPY    - Is ready? SMA: {spySma.IsReady}, ATR: {spyAtr.IsReady}, VWAP: {spyVwap.IsReady}")

        eur = self.AddForex("EURUSD", Resolution.Hour).Symbol
        eurSma = self.SMA(eur, 20, Resolution.Daily)
        eurAtr = self.ATR(eur, 20, MovingAverageType.Simple, Resolution.Daily)
        self.Log(f"EURUSD - Is ready? SMA: {eurSma.IsReady}, ATR: {eurAtr.IsReady}")

        self.AddUniverse(self.CoarseSmaSelector)

        # Since the indicators are ready, we will receive error messages
        # reporting that the algorithm manager is trying to add old information
        self.SetWarmUp(10)

    def CoarseSmaSelector(self, coarse):

        score = dict()
        for cf in coarse:
            if not cf.HasFundamentalData:
               continue
            symbol = cf.Symbol
            price = cf.AdjustedPrice




            # grab the SMA instance for this symbol
            avg = self.averages.setdefault(symbol, SimpleMovingAverage(100))
            self.WarmUpIndicator(symbol, avg, Resolution.Daily)
            # Update returns true when the indicators are ready, so don't accept until they are
            if avg.Update(cf.EndTime, price):
               value = avg.Current.Value
               # only pick symbols who have their price over their 100 day sma
               if value > price * self.tolerance:
                    score[symbol] = (value - price) / ((value + price) / 2)

        # prefer symbols with a larger delta by percentage between the two averages
        sortedScore = sorted(score.items(), key=lambda kvp: kvp[1], reverse=True)
        return [x[0] for x in sortedScore[:self.count]]

    def OnSecuritiesChanged(self, changes):
        for security in changes.RemovedSecurities:
            if security.Invested:
                self.Liquidate(security.Symbol)

        for security in changes.AddedSecurities:
            self.SetHoldings(security.Symbol, self.targetPercent)





    def SelectFine(self, algorithm, fine):
        '''Performs fine selection for the QC500 constituents
        The company's headquarter must in the U.S.
        The stock must be traded on either the NYSE or NASDAQ
        At least half a year since its initial public offering
        The stock's market cap must be greater than 500 million'''

        sortedBySector = sorted([x for x in fine if x.CompanyReference.CountryId == "USA"
                                        and x.CompanyReference.PrimaryExchangeID in ["NYS","NAS"]
                                        and (algorithm.Time - x.SecurityReference.IPODate).days > 180
                                        and x.MarketCap > 5e8],
                               key = lambda x: x.CompanyReference.IndustryTemplateCode)

        count = len(sortedBySector)

        # If no security has met the QC500 criteria, the universe is unchanged.
        # A new selection will be attempted on the next trading day as self.lastMonth is not updated
        if count == 0:
            return Universe.Unchanged

        # Update self.lastMonth after all QC500 criteria checks passed
        self.lastMonth = algorithm.Time.month

        percent = self.numberOfSymbolsFine / count
        sortedByDollarVolume = []

        # select stocks with top dollar volume in every single sector
        for code, g in groupby(sortedBySector, lambda x: x.CompanyReference.IndustryTemplateCode):
            y = sorted(g, key = lambda x: self.dollarVolumeBySymbol[x.Symbol], reverse = True)
            c = ceil(len(y) * percent)
            sortedByDollarVolume.extend(y[:c])

        sortedByDollarVolume = sorted(sortedByDollarVolume, key = lambda x: self.dollarVolumeBySymbol[x.Symbol], reverse=True)
        return [x.Symbol for x in sortedByDollarVolume[:self.numberOfSymbolsFine]]


