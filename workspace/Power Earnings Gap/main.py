from AlgorithmImports import *

class PowerEarningsGap(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2023, 1, 1)
        self.SetCash(100000000)

        # add SPY so that we can use it in the schedule rule below
        self.SPY = self.AddEquity('SPY', Resolution.Minute).Symbol

        # build a universe using the CoarseFilter and FineFilter functions defined below
        self.AddUniverse(self.CoarseFilter, self.FineFilter)

        self.SPY = self.AddEquity("SPY").Symbol
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 1), self.AfterMarketOpen)


    def CoarseFilter(self, universe):
        # filter universe, ensure DollarVolume is above a certain threshold
        # also filter by assets that have fundamental data
        universe = [asset for asset in universe if asset.DollarVolume > 1000000 and asset.Price > 1 and asset.HasFundamentalData]
        
        # sort universe by highest dollar volume
        sortedByDollarVolume = sorted(universe, key=lambda asset: asset.DollarVolume, reverse=True)
        
        # only select the first 500
        topSortedByDollarVolume = sortedByDollarVolume[:500]

        # we must return a list of the symbol objects only
        symbolObjects = [asset.Symbol for asset in topSortedByDollarVolume]

        # this line is not necessary, but we will use it for debugging to see a list of ticker symbols
        tickerSymbolValuesOnly = [symbol.Value for symbol in symbolObjects]

        return symbolObjects

    def FineFilter(self, coarseUniverse):
        yesterday = self.Time - timedelta(days=1)

        fineUniverse = [asset.Symbol for asset in coarseUniverse if asset.EarningReports.FileDate == yesterday and asset.MarketCap > 5e8]

        tickerSymbolValuesOnly = [symbol.Value for symbol in fineUniverse]

        return fineUniverse


    def AfterMarketOpen(self):
        for security in self.ActiveSecurities.Values:
            symbol = security.Symbol

            if symbol == self.SPY:
                continue

            historyData = self.History(symbol, 2, Resolution.Daily)
            historyHourlyData = self.History(symbol, 24, Resolution.Hour)

            self.set
            try:
                openDayAfterEarnings = historyData['open'][-1]
                closeDayAfterEarnings = historyData['close'][-1]
                highDayAfterEarnings = historyData['high'][-1]
                closeDayBeforeEarnings = historyData['close'][-2]
            except:
                self.Debug(f"History data unavailable for {symbol.Value}")
                continue

            priceGap = openDayAfterEarnings - closeDayBeforeEarnings
            percentGap = priceGap / closeDayBeforeEarnings
            closeStrength = (closeDayAfterEarnings - openDayAfterEarnings) / (highDayAfterEarnings - openDayAfterEarnings)

            '''
            if percentGap > 0.02 and percentGap < 0.8:
                self.MarketOrder(symbol, (-1000/closeDayAfterEarnings))
            '''
            if percentGap > 0.8:
                self.Debug(f"{symbol.Value} gapped up by {percentGap} - {closeDayBeforeEarnings} {openDayAfterEarnings}")

                #if closeDayAfterEarnings > closeDayBeforeEarnings and closeStrength > 0.5:
                if closeDayAfterEarnings > closeDayBeforeEarnings:
                    self.Debug(f"{symbol.Value} closed strong!")
                    self.MarketOrder(symbol, +1000/closeDayAfterEarnings)
                else:
                    self.Debug(f"{symbol.Value} faded after earnings")
            
            '''
            if percentGap < -0.02 and percentGap > -0.08:
                #if closeDayAfterEarnings < closeDayBeforeEarnings and closeStrength < -0.5:
                if closeDayAfterEarnings < closeDayBeforeEarnings:
                    self.Debug(f"{symbol.Value} gapped down by {percentGap} - {closeDayBeforeEarnings} {openDayAfterEarnings}")
                    self.MarketOrder(symbol, +1000/closeDayAfterEarnings)
            '''
            
            if percentGap < 0.08:
                    self.MarketOrder(symbol, -1000/closeDayAfterEarnings)

            '''
            self.Debug(f"{symbol.Value} gapped up by {percentGap} - {closeDayBeforeEarnings} {openDayAfterEarnings}")

            if closeDayAfterEarnings > closeDayBeforeEarnings:
                self.Debug(f"{symbol.Value} closed strong!")
                self.MarketOrder(symbol, 100)
            else:
                self.Debug(f"{symbol.Value} faded after earnings")
                self.MarketOrder(symbol, -100)
            '''