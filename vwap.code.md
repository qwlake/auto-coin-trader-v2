# VWAP Mean Reversion Strategy - Technical Implementation Specification

## 1. Strategy Overview & Requirements

### Core Strategy Concept
- **Mean Reversion Strategy**: Trade against price deviations from VWAP with expectation of price reversion
- **Market Regime Filter**: Use ADX to distinguish between trending and sideways markets
- **Risk Management**: Tight profit/loss targets with volatility-based position sizing
- **Execution Method**: Limit orders for entry, market orders for exit

### Performance Targets
- **Win Rate**: Minimum 39.8% to achieve profitability after fees
- **Profit Target**: +0.6% per winning trade
- **Loss Limit**: -0.3% per losing trade
- **Fee Structure**: 0.02% maker (entry), 0.05% taker (exit when needed)
- **Net Profit**: +0.56% per win, -0.37% per loss

### Market Conditions
- **Optimal Environment**: Low volatility sideways markets (ADX < 20)
- **Avoid**: Strong trending markets (ADX > 40)
- **Safety Mechanism**: Halt trading during high volatility spikes (≥0.15% in 5 seconds)

## 2. Technical Indicators Needed

### 2.1 VWAP (Volume Weighted Average Price)
```
Mathematical Definition:
VWAP = Σ(Price × Volume) / Σ(Volume)

Implementation Requirements:
- Rolling calculation over trading session (reset at session start)
- Use typical price: (High + Low + Close) / 3
- Maintain running sums of (price × volume) and volume
- Update on every tick/trade data
- Memory efficient: avoid storing all historical data
```

**Data Structure:**
```python
class VWAPCalculator:
    cumulative_pv: float  # price × volume sum
    cumulative_volume: float  # volume sum
    current_vwap: float
    session_start: datetime
```

### 2.2 ADX (Average Directional Index)
```
Calculation Steps:
1. True Range (TR) = max(High-Low, abs(High-PrevClose), abs(Low-PrevClose))
2. Directional Movement:
   - +DM = High - PrevHigh (if positive and > abs(Low - PrevLow), else 0)
   - -DM = PrevLow - Low (if positive and > abs(High - PrevHigh), else 0)
3. Smoothed averages (14-period typical):
   - ATR = EMA(TR, 14)
   - +DI = 100 × EMA(+DM, 14) / ATR
   - -DI = 100 × EMA(-DM, 14) / ATR
4. DX = 100 × abs(+DI - -DI) / (+DI + -DI)
5. ADX = EMA(DX, 14)

Interpretation:
- ADX < 20: Weak trend (sideways market) → Trade allowed
- 20 ≤ ADX < 40: Developing trend → Monitor closely
- ADX ≥ 40: Strong trend → Halt trading
```

### 2.3 Standard Deviation Bands
```
VWAP Bands Calculation:
- Upper Band = VWAP + (StdDev × Multiplier)
- Lower Band = VWAP - (StdDev × Multiplier)

Standard Deviation:
- Use price deviations from VWAP over rolling window
- Window size: 20-50 periods (configurable)
- Update on each new price tick
- Multiplier: 1.0-2.0 (configurable, affects band width)
```

### 2.4 Volatility Monitor
```
5-Second Volatility Calculation:
volatility_5s = abs(current_price - price_5s_ago) / price_5s_ago

Requirements:
- Maintain price buffer for last 5 seconds
- Calculate on every price update
- Trigger safety halt if ≥ 0.15%
- Reset mechanism after 10-minute pause
```

## 3. Data Pipeline Requirements

### 3.1 Required Market Data Streams

**Primary Data Source:**
- **Futures WebSocket Stream**: Already available via `futures_ws.py`
- **Trade Stream**: Individual trades for VWAP calculation
- **Kline Stream**: 1-second or 1-minute candles for ADX calculation
- **Depth Stream**: Current order book for execution (already available)

**Data Stream Integration:**
```python
# Extend existing futures_ws.py
class FuturesDataStream:
    def __init__(self):
        self.vwap_calculator = VWAPCalculator()
        self.adx_calculator = ADXCalculator()
        self.volatility_monitor = VolatilityMonitor()
        self.band_calculator = BandCalculator()
    
    async def handle_trade_data(self, trade_data):
        # Update VWAP with each trade
        
    async def handle_kline_data(self, kline_data):
        # Update ADX with each 1m candle close
        
    async def handle_price_update(self, price):
        # Update volatility monitor and bands
```

### 3.2 Data Storage and Buffering

**In-Memory Buffers:**
- **VWAP State**: Cumulative values only (no historical storage)
- **ADX Buffer**: Last 28 periods (14 for calculation + 14 for smoothing)
- **Price History**: Last 5 seconds for volatility calculation
- **Band Calculation**: Last 20-50 price points for standard deviation

**Persistent Storage:**
- **Session Tracking**: VWAP reset times in database
- **Performance Metrics**: Win/loss ratios, profitability tracking
- **Configuration**: Strategy parameters in settings

### 3.3 Real-time vs Historical Data Usage

**Real-time Components:**
- VWAP calculation (trade-by-trade updates)
- Volatility monitoring (continuous price tracking)
- Entry/exit signal generation

**Historical Components:**
- ADX calculation (requires 28+ historical periods)
- Standard deviation bands (requires 20-50 historical prices)
- Initial warm-up period before strategy activation

## 4. Core Strategy Logic Flow

### 4.1 Initialization Sequence
```
1. Load configuration parameters
2. Initialize technical indicators with warm-up data
3. Establish WebSocket connections
4. Wait for indicator stabilization (minimum 30 data points)
5. Begin strategy execution
```

### 4.2 Main Trading Loop
```python
async def main_strategy_loop():
    while trading_active:
        # 1. Data Updates
        update_vwap(latest_trade)
        update_adx(latest_kline)
        update_volatility(current_price)
        update_bands(current_price)
        
        # 2. Safety Checks
        if check_volatility_halt():
            pause_trading(600)  # 10 minutes
            continue
            
        # 3. Market Regime Filter
        if adx_value > 40:
            cancel_all_orders()
            continue
            
        if adx_value > 20:
            continue  # Wait for sideways market
            
        # 4. Signal Generation
        signal = generate_entry_signal()
        if signal:
            place_limit_order(signal)
            
        # 5. Position Management
        monitor_active_positions()
        
        await asyncio.sleep(0.1)  # 100ms cycle
```

### 4.3 Entry Signal Logic
```python
def generate_entry_signal():
    current_price = get_current_price()
    vwap = get_current_vwap()
    upper_band = vwap + (std_dev * band_multiplier)
    lower_band = vwap - (std_dev * band_multiplier)
    
    # ADX filter must pass
    if adx_value >= 20:
        return None
        
    # Check band boundaries
    if current_price >= upper_band and current_price > vwap:
        return "SHORT"  # Price above VWAP at upper band
    elif current_price <= lower_band and current_price < vwap:
        return "LONG"   # Price below VWAP at lower band
        
    return None
```

### 4.4 Exit Condition Evaluation
```python
def check_exit_conditions(position):
    current_price = get_current_price()
    entry_price = position.entry_price
    side = position.side
    
    # Profit/Loss targets
    if side == "LONG":
        profit_target = entry_price * 1.006  # +0.6%
        stop_loss = entry_price * 0.997      # -0.3%
        
        if current_price >= profit_target:
            return "PROFIT_TARGET"
        elif current_price <= stop_loss:
            return "STOP_LOSS"
            
    elif side == "SHORT":
        profit_target = entry_price * 0.994  # -0.6%
        stop_loss = entry_price * 1.003      # +0.3%
        
        if current_price <= profit_target:
            return "PROFIT_TARGET"
        elif current_price >= stop_loss:
            return "STOP_LOSS"
    
    # VWAP reversion check
    vwap = get_current_vwap()
    if (side == "LONG" and current_price >= vwap) or \
       (side == "SHORT" and current_price <= vwap):
        return "VWAP_REVERSION"
        
    return None
```

## 5. Integration Architecture

### 5.1 Integration with Existing Bot Structure

**New Strategy Module** (`strategy/vwap_mean_reversion.py`):
```python
class VWAPMeanReversionStrategy:
    def __init__(self):
        self.vwap_calc = VWAPCalculator()
        self.adx_calc = ADXCalculator(period=14)
        self.volatility_monitor = VolatilityMonitor()
        self.band_calc = BandCalculator()
        self.trading_halted = False
        self.halt_until = None
        
    def update_indicators(self, trade_data, kline_data):
        # Update all technical indicators
        
    def generate_signal(self):
        # Return LONG/SHORT/None based on strategy rules
        
    def should_halt_trading(self):
        # Check volatility and ADX conditions
```

**Enhanced WebSocket Handler** (`data/futures_ws.py` modifications):
```python
# Add to existing FuturesWebSocket class
async def _handle_trade_stream(self, msg):
    # Process individual trades for VWAP
    trade_data = {
        'price': float(msg['p']),
        'quantity': float(msg['q']),
        'timestamp': int(msg['T'])
    }
    self.strategy.update_vwap(trade_data)

async def _handle_kline_stream(self, msg):
    # Process kline data for ADX
    if msg['k']['x']:  # Kline is closed
        kline_data = {
            'high': float(msg['k']['h']),
            'low': float(msg['k']['l']),
            'close': float(msg['k']['c']),
            'volume': float(msg['k']['v'])
        }
        self.strategy.update_adx(kline_data)
```

### 5.2 Database Schema Modifications

**New Configuration Table:**
```sql
CREATE TABLE vwap_strategy_config (
    id INTEGER PRIMARY KEY,
    vwap_band_multiplier REAL DEFAULT 1.5,
    adx_period INTEGER DEFAULT 14,
    adx_trend_threshold REAL DEFAULT 20.0,
    adx_strong_trend_threshold REAL DEFAULT 40.0,
    volatility_threshold REAL DEFAULT 0.0015,
    volatility_halt_duration INTEGER DEFAULT 600,
    profit_target_pct REAL DEFAULT 0.006,
    stop_loss_pct REAL DEFAULT 0.003,
    session_reset_hour INTEGER DEFAULT 0
);
```

**Enhanced Position Tracking:**
```sql
-- Add columns to existing tables
ALTER TABLE active_positions ADD COLUMN strategy_type TEXT DEFAULT 'VWAP';
ALTER TABLE active_positions ADD COLUMN vwap_at_entry REAL;
ALTER TABLE closed_positions ADD COLUMN strategy_type TEXT DEFAULT 'VWAP';
ALTER TABLE closed_positions ADD COLUMN exit_reason TEXT;  -- 'PROFIT', 'LOSS', 'VWAP_REVERSION'
```

### 5.3 Configuration Parameters

**New Settings** (extend `config/settings.py`):
```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # VWAP Strategy Parameters
    STRATEGY_TYPE: str = "VWAP"  # "OBI" or "VWAP"
    
    # VWAP Specific
    VWAP_BAND_MULTIPLIER: float = 1.5
    VWAP_STDDEV_PERIOD: int = 20
    
    # ADX Parameters
    ADX_PERIOD: int = 14
    ADX_TREND_THRESHOLD: float = 20.0
    ADX_STRONG_TREND_THRESHOLD: float = 40.0
    
    # Volatility Monitor
    VOLATILITY_THRESHOLD: float = 0.0015  # 0.15%
    VOLATILITY_HALT_DURATION: int = 600   # 10 minutes
    
    # Entry/Exit
    VWAP_PROFIT_TARGET: float = 0.006     # 0.6%
    VWAP_STOP_LOSS: float = 0.003         # 0.3%
    
    # Session Management
    SESSION_RESET_HOUR: int = 0  # UTC hour to reset VWAP
```

## 6. Implementation Challenges & Solutions

### 6.1 Performance Considerations

**Challenge**: Real-time indicator calculations with minimal latency
**Solution**: 
- Use incremental calculations (avoid recalculating entire history)
- Implement circular buffers for fixed-size historical data
- Pre-allocate memory structures
- Use numpy arrays for mathematical operations

**Challenge**: Multiple WebSocket streams coordination
**Solution**:
- Single asyncio event loop with multiple stream handlers
- Shared state objects with thread-safe updates
- Queue-based message processing for high-frequency data

### 6.2 Latency Optimization

**Data Processing Pipeline:**
```python
# Minimize processing in WebSocket callback
async def on_trade_update(self, trade_data):
    # Quick data validation and queuing
    if self.is_valid_trade(trade_data):
        await self.trade_queue.put(trade_data)

# Separate processing task
async def process_trade_data(self):
    while True:
        trade_data = await self.trade_queue.get()
        self.update_indicators(trade_data)  # Bulk processing
        signal = self.check_signals()       # Signal generation
        if signal:
            await self.execute_trade(signal)
```

**Execution Optimization:**
- Pre-calculate position sizes
- Maintain WebSocket connection pools
- Use connection keepalive
- Implement order retry mechanisms

### 6.3 Memory Management

**Fixed-Size Buffers:**
```python
from collections import deque

class FixedBuffer:
    def __init__(self, size):
        self.buffer = deque(maxlen=size)
        self.size = size
    
    def add(self, value):
        self.buffer.append(value)
    
    def is_full(self):
        return len(self.buffer) == self.size
```

**Memory-Efficient VWAP:**
```python
class VWAPCalculator:
    def __init__(self):
        self.cumulative_pv = 0.0
        self.cumulative_volume = 0.0
        self.last_reset = datetime.now()
    
    def update(self, price, volume):
        self.cumulative_pv += price * volume
        self.cumulative_volume += volume
        return self.cumulative_pv / self.cumulative_volume if self.cumulative_volume > 0 else 0
```

### 6.4 Error Handling Approaches

**Graceful Degradation:**
```python
class StrategyState:
    INITIALIZING = "initializing"
    WARMING_UP = "warming_up"
    ACTIVE = "active"
    HALTED = "halted"
    ERROR = "error"

async def safe_strategy_execution(self):
    try:
        if self.state == StrategyState.ERROR:
            await self.attempt_recovery()
            
        if not self.indicators_ready():
            self.state = StrategyState.WARMING_UP
            return
            
        signal = self.generate_signal()
        if signal and self.state == StrategyState.ACTIVE:
            await self.execute_signal(signal)
            
    except IndicatorError as e:
        log.warning(f"Indicator calculation error: {e}")
        # Continue with available indicators
    except NetworkError as e:
        log.error(f"Network error: {e}")
        self.state = StrategyState.ERROR
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        self.state = StrategyState.ERROR
```

**Data Validation:**
```python
def validate_trade_data(self, trade_data):
    required_fields = ['price', 'quantity', 'timestamp']
    for field in required_fields:
        if field not in trade_data:
            raise ValueError(f"Missing required field: {field}")
    
    if trade_data['price'] <= 0 or trade_data['quantity'] <= 0:
        raise ValueError("Invalid price or quantity")
    
    # Timestamp freshness check
    age = time.time() - trade_data['timestamp'] / 1000
    if age > 5:  # 5 seconds old
        raise ValueError("Stale trade data")
```

## 7. Testing & Validation Strategy

### 7.1 Backtesting Requirements

**Historical Data Needs:**
- Trade-by-trade data for accurate VWAP calculation
- 1-minute OHLCV data for ADX calculation
- Order book snapshots for realistic execution simulation
- Minimum 3-6 months of data across different market conditions

**Backtesting Framework:**
```python
class VWAPBacktester:
    def __init__(self, start_date, end_date, initial_capital):
        self.strategy = VWAPMeanReversionStrategy()
        self.portfolio = Portfolio(initial_capital)
        self.performance_metrics = PerformanceTracker()
    
    async def run_backtest(self, trade_data, kline_data):
        for timestamp in self.get_timerange():
            # Simulate real-time data feed
            trades = self.get_trades_at_time(trade_data, timestamp)
            klines = self.get_klines_at_time(kline_data, timestamp)
            
            # Update strategy indicators
            self.strategy.update(trades, klines)
            
            # Generate and execute signals
            signal = self.strategy.generate_signal()
            if signal:
                execution_result = self.simulate_execution(signal, timestamp)
                self.portfolio.update(execution_result)
            
            # Update performance tracking
            self.performance_metrics.update(self.portfolio.current_value, timestamp)
    
    def get_results(self):
        return {
            'total_return': self.portfolio.total_return,
            'sharpe_ratio': self.performance_metrics.sharpe_ratio,
            'max_drawdown': self.performance_metrics.max_drawdown,
            'win_rate': self.performance_metrics.win_rate,
            'profit_factor': self.performance_metrics.profit_factor
        }
```

### 7.2 Performance Metrics to Track

**Strategy Performance:**
- Win Rate (target: ≥39.8%)
- Profit Factor (gross profit / gross loss)
- Average Trade Duration
- Maximum Consecutive Losses
- Return per Trade
- Risk-Adjusted Returns (Sharpe Ratio)

**Risk Metrics:**
- Maximum Drawdown
- Value at Risk (VaR)
- Position Sizing Effectiveness
- Volatility of Returns

**Execution Quality:**
- Order Fill Rates
- Slippage Analysis
- Latency Measurements
- Market Impact Assessment

### 7.3 Validation Approaches

**Walk-Forward Analysis:**
```python
class WalkForwardValidator:
    def __init__(self, train_period_days=90, test_period_days=30):
        self.train_period = train_period_days
        self.test_period = test_period_days
    
    def validate(self, data, start_date, end_date):
        results = []
        current_date = start_date
        
        while current_date < end_date:
            # Define training and testing periods
            train_start = current_date
            train_end = train_start + timedelta(days=self.train_period)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_period)
            
            # Train strategy parameters
            train_data = self.get_data_range(data, train_start, train_end)
            optimal_params = self.optimize_parameters(train_data)
            
            # Test with optimized parameters
            test_data = self.get_data_range(data, test_start, test_end)
            performance = self.backtest_with_params(test_data, optimal_params)
            
            results.append({
                'test_period': (test_start, test_end),
                'performance': performance,
                'parameters': optimal_params
            })
            
            current_date = test_end
        
        return results
```

**Live Trading Validation:**
- Paper trading mode with real market data
- Small position size live testing
- Performance comparison with backtesting results
- Slippage and execution cost analysis

**Stress Testing:**
- High volatility period simulation
- Market crash scenarios
- Extended sideways market conditions
- Network disruption handling

### 7.4 Monitoring and Alerting

**Real-time Monitoring Dashboard:**
```python
class StrategyMonitor:
    def __init__(self):
        self.metrics = {
            'trades_today': 0,
            'current_pnl': 0.0,
            'win_rate_today': 0.0,
            'current_drawdown': 0.0,
            'indicator_health': True
        }
    
    def update_metrics(self, trade_result):
        # Update all relevant metrics
        pass
    
    def check_alerts(self):
        alerts = []
        
        # Performance alerts
        if self.metrics['current_drawdown'] > 0.05:  # 5% drawdown
            alerts.append("High drawdown detected")
        
        if self.metrics['win_rate_today'] < 0.3 and self.metrics['trades_today'] > 10:
            alerts.append("Low win rate detected")
        
        # Technical alerts
        if not self.metrics['indicator_health']:
            alerts.append("Indicator calculation issues")
        
        return alerts
```

This comprehensive technical specification provides all the implementation details needed to develop the VWAP mean reversion strategy while integrating seamlessly with the existing trading bot architecture. The strategy maintains the core risk management principles while adding sophisticated market regime detection and volatility controls.