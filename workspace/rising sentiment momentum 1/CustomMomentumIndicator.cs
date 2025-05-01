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
#endregion


namespace QuantConnect.Algorithm.CSharp.Helpers
{
    public class CustomMomentumIndicator : TradeBarIndicator
    {
        private Symbol _symbol;
        private int _windowSize;
        public readonly AnnualizedExponentialSlopeIndicator AnnualizedSlope;
        public readonly ExponentialMovingAverage MovingAverage;
        public readonly GapIndicator Gap;
        public readonly AverageTrueRange Atr;

        public CustomMomentumIndicator(Symbol symbol, int annualizedSlopeWindow, int movingAverageWindow, int gapWindow, int atrWindow) : base($"CMI({symbol}, {annualizedSlopeWindow}, {movingAverageWindow}, {gapWindow})")
        {
            _symbol = symbol;
            AnnualizedSlope = new AnnualizedExponentialSlopeIndicator(annualizedSlopeWindow);
            MovingAverage = new ExponentialMovingAverage(movingAverageWindow);
            Gap = new GapIndicator(gapWindow);
            Atr = new AverageTrueRange(atrWindow);

            _windowSize = (new int[] { movingAverageWindow, annualizedSlopeWindow, gapWindow, atrWindow }).Max();
        }
        public Symbol Symbol { get { return _symbol; } }

        public override void Reset()
        {
            AnnualizedSlope.Reset();
            MovingAverage.Reset();
            Gap.Reset();
            Atr.Reset();
            base.Reset();
        }

        protected override decimal ComputeNextValue(TradeBar input)
        {
            AnnualizedSlope.Update(input.EndTime, input.Value);
            MovingAverage.Update(input.EndTime, input.Value);
            Gap.Update(input.EndTime, input.Value);
            Atr.Update(input);

            return AnnualizedSlope;
        }
        /// <summary>
        /// Are the indicators ready to be used?
        /// </summary>
        public override bool IsReady
        {
            get { return AnnualizedSlope.IsReady && MovingAverage.IsReady && Gap.IsReady && Atr.IsReady; }
        }
        /// <summary>
        /// Returns the Window of the indicator required to warm up indicator
        /// </summary>
        public int Window
        {
            get {return _windowSize;}
        }
        public new string ToDetailedString()
        {
            return $"Symbol:{_symbol} Slope:{AnnualizedSlope.ToDetailedString()} Average:{MovingAverage.ToDetailedString()} Gap:{Gap.ToDetailedString()} Atr:{Atr.ToDetailedString()} IsReady:{IsReady}";
        }
    }
}
