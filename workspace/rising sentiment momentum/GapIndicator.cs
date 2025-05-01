#region imports
    using System;
    using System.Collections;
    using System.Collections.Generic;
    using System.Linq;
    using System.Globalization;
    using System.Drawing;
    using QuantConnect;
    using QuantConnect.Algorithm.Framework;
    using QuantConnect.Algorithm.Framework.Selection;
    using QuantConnect.Algorithm.Framework.Alphas;
    using QuantConnect.Algorithm.Framework.Portfolio;
    using QuantConnect.Algorithm.Framework.Execution;
    using QuantConnect.Algorithm.Framework.Risk;
    using QuantConnect.Parameters;
    using QuantConnect.Benchmarks;
    using QuantConnect.Brokerages;
    using QuantConnect.Util;
    using QuantConnect.Interfaces;
    using QuantConnect.Algorithm;
    using QuantConnect.Indicators;
    using QuantConnect.Data;
    using QuantConnect.Data.Consolidators;
    using QuantConnect.Data.Custom;
    using QuantConnect.DataSource;
    using QuantConnect.Data.Fundamental;
    using QuantConnect.Data.Market;
    using QuantConnect.Data.UniverseSelection;
    using QuantConnect.Notifications;
    using QuantConnect.Orders;
    using QuantConnect.Orders.Fees;
    using QuantConnect.Orders.Fills;
    using QuantConnect.Orders.Slippage;
    using QuantConnect.Scheduling;
    using QuantConnect.Securities;
    using QuantConnect.Securities.Equity;
    using QuantConnect.Securities.Future;
    using QuantConnect.Securities.Option;
    using QuantConnect.Securities.Forex;
    using QuantConnect.Securities.Crypto;
    using QuantConnect.Securities.Interfaces;
    using QuantConnect.Storage;
    using QuantConnect.Data.Custom.AlphaStreams;
    using QCAlgorithmFramework = QuantConnect.Algorithm.QCAlgorithm;
    using QCAlgorithmFrameworkBridge = QuantConnect.Algorithm.QCAlgorithm;
    using MathNet.Numerics;
    using MathNet.Numerics.Statistics;
#endregion



/// <summary>
///  Indicator to indicate the percentage (0.10 = 10%) of which a security gapped over the last period;
/// </summary>
namespace QuantConnect.Algorithm.CSharp.Helpers
{
    public class GapIndicator : WindowIndicator<IndicatorDataPoint>
    {
        public GapIndicator(int period)
            : base("GAP(" + period + ")", period)
        {
        }

        public GapIndicator(string name, int period)
            : base(name, period)
        {
        }
        public override bool IsReady
        {
            get { return Samples >= Period; }
        }

        protected override decimal ComputeNextValue(IReadOnlyWindow<IndicatorDataPoint> window, IndicatorDataPoint input)
        {
            if (window.Count < 3) return 0m;

            var diff = new double[window.Count];

            // load input data for regression
            for (int i = 0; i < window.Count - 1; i++)
            {
                diff[i] = (double)((window[i + 1] - window[i]) / (window[i] == 0 ? 1 : window[i].Value));
            }
            return (decimal) diff.MaximumAbsolute();
        }
    }
}
