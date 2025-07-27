# OBI Scalping Strategy - Analysis & Optimization

## Current Strategy Overview

### Order Book Imbalance (OBI) Strategy
The system implements a scalping strategy based on order book imbalance signals:

**Signal Calculation:**
- OBI = bid_volume / (bid_volume + ask_volume) for top N levels
- Uses volume-weighted calculation: `sum(price * quantity)` for each side
- Current depth: 5 levels (configurable via `DEPTH_LEVEL`)

**Trading Thresholds:**
- LONG signal: OBI >= 0.70 (70% bid dominance)
- SHORT signal: OBI <= 0.30 (30% bid dominance)
- Neutral zone: 0.30 < OBI < 0.70 (no signal)

**Risk Management:**
- Take Profit: 0.05% (0.0005)
- Stop Loss: 0.05% (0.0005)
- Position Size: $20 USDT per trade
- Order TTL: 2.0 seconds (configured but not implemented)

## Strategy Performance Analysis

### Strengths
1. **Market Microstructure Focus**: OBI captures short-term liquidity imbalances
2. **Post-Only Execution**: Uses LIMIT_MAKER orders to capture spread
3. **Symmetric Risk**: Equal TP/SL distances reduce directional bias
4. **Real-time Processing**: WebSocket-based depth updates provide low latency

### Critical Issues Identified

#### 1. Signal Quality Problems
- **Static Thresholds**: 70/30% thresholds may not adapt to market volatility
- **No Smoothing**: Raw OBI signals can be noisy and generate false signals
- **Limited Context**: No consideration of market trends or volatility regimes

#### 2. Execution Risk
- **Market Impact**: Placing at mid-price may not provide edge over spread
- **Signal Lag**: 200ms sleep in main loop creates execution delays
- **No Order Management**: Missing ORDER_TTL implementation leads to stale orders

#### 3. Risk Management Deficiencies
- **Fixed Position Size**: $20 per trade regardless of volatility or account size
- **No Portfolio Limits**: No maximum exposure or daily loss limits
- **Symmetric TP/SL**: May not reflect true risk/reward asymmetries

#### 4. Performance Measurement Gaps
- **No Strategy Metrics**: Missing Sharpe ratio, win rate, average trade duration
- **No Drawdown Control**: No maximum drawdown protection
- **Limited Logging**: Insufficient data for performance analysis

## Optimization Recommendations

### Phase 1: Signal Enhancement (High Priority)

#### 1.1 Adaptive Thresholds
```python
# Dynamic threshold calculation based on rolling OBI statistics
def calc_adaptive_thresholds(obi_history: deque, lookback: int = 100):
    recent_obi = list(obi_history)[-lookback:]
    mean_obi = np.mean(recent_obi)
    std_obi = np.std(recent_obi)
    
    # Adaptive thresholds: mean ± 2 standard deviations
    long_threshold = min(0.75, mean_obi + 2 * std_obi)
    short_threshold = max(0.25, mean_obi - 2 * std_obi)
    
    return long_threshold, short_threshold
```

#### 1.2 Signal Smoothing
```python
# Exponential moving average smoothing to reduce noise
def smooth_obi(raw_obi: float, prev_smooth: float, alpha: float = 0.3):
    return alpha * raw_obi + (1 - alpha) * prev_smooth
```

#### 1.3 Multi-Timeframe Confluence
```python
# Require alignment across multiple depth levels
def multi_level_signal(depth_snap: dict):
    obi_5 = calc_obi(depth_snap, 5)
    obi_10 = calc_obi(depth_snap, 10)
    obi_20 = calc_obi(depth_snap, 20)
    
    # Require confluence across timeframes
    if all(obi > 0.65 for obi in [obi_5, obi_10, obi_20]):
        return "LONG"
    elif all(obi < 0.35 for obi in [obi_5, obi_10, obi_20]):
        return "SHORT"
    return None
```

### Phase 2: Execution Optimization (High Priority)

#### 2.1 Smart Order Placement
```python
# Place orders at better prices within the spread
def calc_optimal_price(depth_snap: dict, side: str, aggression: float = 0.3):
    bid = float(depth_snap["bids"][0][0])
    ask = float(depth_snap["asks"][0][0])
    spread = ask - bid
    
    if side == "BUY":
        # Place buy order closer to bid
        return bid + (spread * aggression)
    else:
        # Place sell order closer to ask
        return ask - (spread * aggression)
```

#### 2.2 Order Time-to-Live Implementation
```python
# Implement actual order TTL management
async def manage_order_ttl(order_id: int, ttl_seconds: float):
    await asyncio.sleep(ttl_seconds)
    try:
        await cancel_order(order_id)
        log.info(f"Cancelled stale order {order_id} after {ttl_seconds}s")
    except Exception as e:
        log.warning(f"Failed to cancel order {order_id}: {e}")
```

### Phase 3: Risk Management Enhancement (Medium Priority)

#### 3.1 Dynamic Position Sizing
```python
# Volatility-adjusted position sizing
def calc_position_size(volatility: float, base_size: float = 20.0):
    # Inverse volatility scaling
    vol_factor = 0.01 / max(volatility, 0.001)  # Target 1% volatility
    return min(base_size * vol_factor, base_size * 2.0)  # Cap at 2x base
```

#### 3.2 Portfolio Risk Limits
```python
# Add portfolio-level risk controls
MAX_DAILY_LOSS = -100.0  # Maximum daily loss in USDT
MAX_OPEN_POSITIONS = 5   # Maximum concurrent positions
MAX_NOTIONAL_EXPOSURE = 200.0  # Maximum total notional exposure
```

### Phase 4: Performance Monitoring (Medium Priority)

#### 4.1 Real-time Metrics Tracking
```python
class StrategyMetrics:
    def __init__(self):
        self.trades = []
        self.daily_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_equity = 0.0
    
    def update_metrics(self, trade_pnl: float):
        self.trades.append(trade_pnl)
        self.daily_pnl += trade_pnl
        
        # Update drawdown
        current_equity = sum(self.trades)
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, drawdown)
    
    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        winning_trades = sum(1 for pnl in self.trades if pnl > 0)
        return winning_trades / len(self.trades)
    
    @property
    def sharpe_ratio(self) -> float:
        if len(self.trades) < 2:
            return 0.0
        returns = np.array(self.trades)
        return np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0.0
```

## Implementation Priority

### Immediate (Week 1)
1. Fix ORDER_TTL implementation
2. Add adaptive thresholds
3. Implement smart order placement
4. Add basic portfolio limits

### Short-term (Week 2-3)
1. Add signal smoothing
2. Implement dynamic position sizing
3. Enhanced performance metrics
4. Multi-level confluence signals

### Medium-term (Month 1)
1. Regime detection system
2. Advanced order management
3. Comprehensive backtesting framework
4. Strategy parameter optimization

## Expected Performance Improvements

### Signal Quality
- **Reduced False Signals**: Adaptive thresholds and smoothing should reduce noise by ~30-40%
- **Better Entry Timing**: Multi-level confluence should improve entry precision
- **Market Adaptation**: Dynamic parameters will adapt to changing market conditions

### Execution Quality
- **Improved Fill Rates**: Smart order placement should increase fill probability by ~20-25%
- **Reduced Adverse Selection**: TTL management will prevent stale order execution
- **Better Risk-Adjusted Returns**: Enhanced risk management should improve Sharpe ratio

### Risk Management
- **Controlled Drawdowns**: Portfolio limits should cap maximum daily losses
- **Adaptive Sizing**: Volatility-adjusted sizing should normalize risk across market regimes
- **Better Capital Utilization**: Dynamic exposure management will optimize capital efficiency

## Backtesting Requirements

Before implementing optimizations in live trading:

1. **Historical Data Collection**: Gather 3-6 months of depth data for BTCUSDT
2. **Strategy Simulation**: Implement full execution simulation with realistic assumptions
3. **Parameter Optimization**: Use walk-forward analysis to find optimal parameters
4. **Out-of-Sample Testing**: Reserve 20% of data for final validation

## Risk Considerations

### Implementation Risks
- **Over-optimization**: Avoid curve-fitting to historical data
- **Latency Changes**: Monitor execution latency impact on performance
- **Market Regime Shifts**: Strategy may perform differently in trending vs ranging markets

### Operational Risks
- **System Downtime**: Ensure robust error handling and reconnection logic
- **API Rate Limits**: Monitor Binance API usage to avoid rate limiting
- **Position Reconciliation**: Implement position verification mechanisms

This strategy analysis provides a roadmap for systematic improvement of your OBI scalping system. The recommendations are prioritized by impact and implementation complexity, allowing for incremental enhancement while maintaining system stability.