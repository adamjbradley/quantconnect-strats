/*
 * QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
 * Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect Corporation.
 * 
 * Licensed under the Apache License, Version 2.0 (the "License"); 
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
*/

using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;


namespace QuantConnect.Algorithm.CSharp
{
    /// <summary>
    /// In this algortihm we show how you can easily use the universe selection feature to fetch symbols
    /// to be traded using the AddUniverse method. This method accepts a function that will return the
    /// desired current set of symbols. Return Universe.Unchanged if no universe changes should be made
    /// </summary>
    public class DropboxUniverseSelectionAlgorithm : QCAlgorithm
    {
        // the changes from the previous universe selection
        private SecurityChanges _changes = SecurityChanges.None;
        // only used in backtest for caching the file results
        private readonly Dictionary<DateTime, List<string>> _backtestSymbolsPerDay = new Dictionary<DateTime, List<string>>();

        /// <summary>
        /// Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialized.
        /// </summary>
        /// <seealso cref="QCAlgorithm.SetStartDate(System.DateTime)"/>
        /// <seealso cref="QCAlgorithm.SetEndDate(System.DateTime)"/>
        /// <seealso cref="QCAlgorithm.SetCash(decimal)"/>
        public override void Initialize()
        {
            // this sets the resolution for data subscriptions added by our universe
            UniverseSettings.Resolution = Resolution.Daily;
            UniverseSettings.Leverage = 1m;

            // set our start and end for backtest mode
            SetStartDate(2010, 01, 01);
            SetEndDate(2018, 01, 01);
            SetBenchmark("SPY");

            // define a new custom universe that will trigger each day at midnight
            AddUniverse("my-dropbox-universe", Resolution.Daily, dateTime =>
            {
                const string liveUrl = @"https://docs.google.com/spreadsheets/d/12lUYUHYWNYhLBvJGcsXp2ZBXdJ7g3-Sspwvg0L62NAk/gviz/tq?tqx=out:csv&sheet=Live_CSV";
                const string backtestUrl = @"https://docs.google.com/spreadsheets/d/12lUYUHYWNYhLBvJGcsXp2ZBXdJ7g3-Sspwvg0L62NAk/gviz/tq?tqx=out:csv&sheet=Backtest_CSV";
                var url = LiveMode ? liveUrl : backtestUrl;
                using (var client = new WebClient())
                {
                    // handle live mode file format
                    if (LiveMode)
                    {
                        // fetch the file from dropbox
                        var file = client.DownloadString(url);
                        // if we have a file for today, break apart by commas and return symbols
                        if (file.Length > 0) return file.ToCsv();
                        // no symbol today, leave universe unchanged
                        return Universe.Unchanged;
                    }

                    // backtest - first cache the entire file
                    if (_backtestSymbolsPerDay.Count == 0)
                    {
                        // fetch the file from dropbox only if we haven't cached the result already
                        var file = client.DownloadString(url);

                        // split the file into lines and add to our cache
                        foreach (var line in file.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries))
                        {
                        	//All the values in the downloaded file are surrounded in quotes, the replace function strips out double quotes (") from the string.
                            var csv = line.Replace("\"","").ToCsv();  
                            var date = DateTime.ParseExact(csv[0], "yyyy-MM-dd", null);
                            var symbols = csv.Skip(1).ToList();
                            _backtestSymbolsPerDay[date] = symbols;
                        }
                    }

                    // if we have symbols for this date return them, else specify Universe.Unchanged
                    List<string> result;
                    if (_backtestSymbolsPerDay.TryGetValue(dateTime.Date, out result))
                    {
                        return result;
                    }
                    return Universe.Unchanged;
                }
            });
            
        }


        public void OnData(TradeBars data)
        {
            if (_changes == SecurityChanges.None) return;
            
            var count = 10;
            IEnumerable<Symbol> selection = 
				(
				from d in data.Values
				orderby d.Price descending
				select d.Symbol
				).Take(count);
			
            foreach (Security security in Securities.Values)
            {
            	if (selection.Contains(security.Symbol))
            	{
            		SetHoldings(security.Symbol, 1m/count);
            	}
            	else if (security.Invested)
            	{
            		Liquidate(security.Symbol);
            	}
            }

            // reset changes
            _changes = SecurityChanges.None;
        }

        // this event fires whenever we have changes to our universe
        public override void OnSecuritiesChanged(SecurityChanges changes)
        {
            _changes = changes;
        }
    }
}
