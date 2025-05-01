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
    using MathNet.Numerics.LinearAlgebra;
#endregion

namespace QuantConnect.Algorithm.CSharp.Helpers
{
    public class AnnualizedExponentialSlopeIndicator : WindowIndicator<IndicatorDataPoint>
    {
        /// <summary>
        /// Array representing the time.
        /// </summary>
        private readonly double[] t;

        public AnnualizedExponentialSlopeIndicator(int period)
            : base("AESI(" + period + ")", period)
        {
            t = Vector<double>.Build.Dense(period, i => i + 1).ToArray();
        }

        public AnnualizedExponentialSlopeIndicator(string name, int period)
            : base(name, period)
        {
            t = Vector<double>.Build.Dense(period, i => i + 1).ToArray();
        }
        
        protected override decimal ComputeNextValue(IReadOnlyWindow<IndicatorDataPoint> window, IndicatorDataPoint input)
        {
            // Until the window is ready, the indicator returns the input value.
            if (window.Samples <= window.Size) return 0m;

            // Sort the window by time, convert the observations to double and transform it to an array
            var series = window
                .OrderBy(i => i.Time)
                .Select(i => Convert.ToDouble(Math.Log(Convert.ToDouble(i.Value))))
                .ToArray();
            // Fit OLS
            // solves y=a + b*x via linear regression
            // http://numerics.mathdotnet.com/Regression.html
            var ols = Fit.Line(x: t, y: series);
            var intercept = ols.Item1;
            var slope = ols.Item2;

            // compute rsquared
            var rsquared = GoodnessOfFit.RSquared(t.Select(x => intercept + slope * x), series);

            // anything this small can be viewed as flat
            if (double.IsNaN(slope) || Math.Abs(slope) < 1e-25) return 0m;

            // trading days per year for us equities
            const int dayCount = 252;

            // annualize dy/dt
            var annualSlope = ((Math.Pow(Math.Exp(slope), dayCount)) - 1) * 100;

            // scale with rsquared
            annualSlope = annualSlope * rsquared;

            if (annualSlope >= (double)decimal.MaxValue || annualSlope <= (double)decimal.MinValue)
            {
                annualSlope = 0;
            }
            return Convert.ToDecimal(annualSlope);
        }
    }
}
