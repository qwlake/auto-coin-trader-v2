import math
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Tuple


class VWAPCalculator:
    """
    Volume Weighted Average Price Calculator
    
    Calculates VWAP using a rolling time window: VWAP = Σ(Price × Volume) / Σ(Volume)
    over the specified time window (default: 5 minutes)
    """
    
    def __init__(self, window_minutes: int = 5):
        self.window_minutes = window_minutes
        self.window_seconds = window_minutes * 60
        
        # Store trades with timestamps for rolling window calculation
        self.trades = deque()  # (timestamp, price, volume, pv) tuples
        self.current_vwap: float = 0.0
        self.last_reset: datetime = datetime.now()
        
    def update(self, price: float, volume: float) -> float:
        """Update VWAP with new trade data"""
        if price <= 0 or volume <= 0:
            return self.current_vwap
        
        current_time = time.time()
        pv = price * volume
        
        # Add new trade
        self.trades.append((current_time, price, volume, pv))
        
        # Remove trades outside the window
        cutoff_time = current_time - self.window_seconds
        while self.trades and self.trades[0][0] < cutoff_time:
            self.trades.popleft()
        
        # Calculate VWAP
        self.current_vwap = self._calculate_vwap()
        return self.current_vwap
    
    def _calculate_vwap(self) -> float:
        """Calculate VWAP from trades in the current window"""
        if not self.trades:
            return 0.0
            
        total_pv = sum(trade[3] for trade in self.trades)  # Sum of price * volume
        total_volume = sum(trade[2] for trade in self.trades)  # Sum of volume
        
        if total_volume > 0:
            return total_pv / total_volume
        return 0.0
    
    def get_vwap(self) -> float:
        """Get current VWAP value"""
        return self.current_vwap
    
    def get_trade_count(self) -> int:
        """Get number of trades in current window"""
        return len(self.trades)
    
    def reset_session(self):
        """Reset VWAP calculator (clear all trades)"""
        self.trades.clear()
        self.current_vwap = 0.0
        self.last_reset = datetime.now()


class ADXCalculator:
    """
    Average Directional Index Calculator
    
    Calculates ADX for trend strength measurement using True Range and 
    Directional Movement indicators with EMA smoothing.
    """
    
    def __init__(self, period: int = 14):
        self.period = period
        self.highs = deque(maxlen=period + 1)
        self.lows = deque(maxlen=period + 1) 
        self.closes = deque(maxlen=period + 1)
        self.tr_values = deque(maxlen=period)
        self.plus_dm_values = deque(maxlen=period)
        self.minus_dm_values = deque(maxlen=period)
        self.dx_values = deque(maxlen=period)
        self.current_adx: Optional[float] = None
    
    def update(self, high: float, low: float, close: float) -> Optional[float]:
        """Update ADX with new OHLC data from kline stream"""
        if high <= 0 or low <= 0 or close <= 0 or high < low:
            return self.current_adx
            
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        
        if len(self.closes) < 2:
            return None
            
        # Calculate True Range and Directional Movement
        prev_close = self.closes[-2]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        self.tr_values.append(tr)
        
        if len(self.highs) >= 2:
            high_diff = high - self.highs[-2]
            low_diff = self.lows[-2] - low
            
            plus_dm = max(high_diff, 0) if high_diff > low_diff else 0
            minus_dm = max(low_diff, 0) if low_diff > high_diff else 0
            
            self.plus_dm_values.append(plus_dm)
            self.minus_dm_values.append(minus_dm)
        
        if len(self.tr_values) >= self.period:
            return self._calculate_adx()
        
        return None
    
    def _calculate_adx(self) -> float:
        """Calculate ADX using EMA smoothing"""
        # Calculate smoothed TR, +DM, -DM
        atr = sum(self.tr_values) / len(self.tr_values)
        plus_di = 100 * (sum(self.plus_dm_values) / len(self.plus_dm_values)) / atr if atr > 0 else 0
        minus_di = 100 * (sum(self.minus_dm_values) / len(self.minus_dm_values)) / atr if atr > 0 else 0
        
        # Calculate DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        self.dx_values.append(dx)
        
        # Calculate ADX (EMA of DX)
        if len(self.dx_values) >= self.period:
            adx = sum(self.dx_values) / len(self.dx_values)
            self.current_adx = adx
            return adx
        
        return self.current_adx or 0
    
    def get_adx(self) -> Optional[float]:
        """Get current ADX value"""
        return self.current_adx


class VWAPBandCalculator:
    """
    VWAP Standard Deviation Bands Calculator
    
    Calculates upper and lower bands around VWAP using standard deviation
    of price deviations from VWAP over a rolling window.
    """
    
    def __init__(self, window_size: int = 20, multiplier: float = 1.5):
        self.window_size = window_size
        self.multiplier = multiplier
        self.price_deviations = deque(maxlen=window_size)
        self.current_std: float = 0.0
    
    def update(self, current_price: float, vwap: float) -> Tuple[float, float]:
        """Update bands with new price and VWAP data"""
        if vwap > 0 and current_price > 0:
            # Calculate percentage deviation from VWAP instead of absolute deviation
            pct_deviation = (current_price - vwap) / vwap
            self.price_deviations.append(pct_deviation)
            
            if len(self.price_deviations) >= 2:
                # Calculate standard deviation of percentage deviations from VWAP
                mean_dev = sum(self.price_deviations) / len(self.price_deviations)
                variance = sum((d - mean_dev) ** 2 for d in self.price_deviations) / len(self.price_deviations)
                self.current_std = math.sqrt(variance)
                
                # Ensure minimum standard deviation for practical trading (0.1% minimum)
                self.current_std = max(self.current_std, 0.001)
        
        # Calculate upper and lower bands using percentage-based standard deviation
        # Convert back to absolute prices
        upper_band = vwap * (1 + (self.current_std * self.multiplier))
        lower_band = vwap * (1 - (self.current_std * self.multiplier))
        
        return upper_band, lower_band
    
    def get_bands(self, vwap: float) -> Tuple[float, float]:
        """Get current upper and lower bands"""
        upper_band = vwap * (1 + (self.current_std * self.multiplier))
        lower_band = vwap * (1 - (self.current_std * self.multiplier))
        return upper_band, lower_band


class VolatilityMonitor:
    """
    Volatility Monitor for Trading Halt Mechanism
    
    Monitors price volatility over 5-second windows and triggers trading
    halts when volatility exceeds configured thresholds.
    """
    
    def __init__(self, threshold: float = 0.0015, halt_duration: int = 600):
        self.threshold = threshold  # 0.15% volatility threshold
        self.halt_duration = halt_duration  # 10 minutes halt duration
        self.price_buffer = deque(maxlen=100)  # Store (price, timestamp) pairs
        self.is_halted = False
        self.halt_until: Optional[datetime] = None
    
    def update_price(self, price: float) -> bool:
        """Update with new price and check volatility threshold"""
        if price <= 0:
            return self.is_halted
            
        current_time = datetime.utcnow()
        self.price_buffer.append((price, current_time))
        
        # Check if we're still in halt period
        if self.is_halted and self.halt_until:
            if current_time < self.halt_until:
                return True  # Still halted
            else:
                self.is_halted = False
                self.halt_until = None
        
        # Calculate 5-second volatility
        volatility = self._calculate_5s_volatility(current_time)
        
        # Check threshold
        if volatility >= self.threshold:
            self.is_halted = True
            self.halt_until = current_time + timedelta(seconds=self.halt_duration)
            return True
        
        return False
    
    def _calculate_5s_volatility(self, current_time: datetime) -> float:
        """Calculate price volatility over last 5 seconds"""
        if len(self.price_buffer) < 2:
            return 0.0
        
        # Find price from 5 seconds ago
        cutoff_time = current_time - timedelta(seconds=5)
        current_price = self.price_buffer[-1][0]
        
        # Find the closest price to 5 seconds ago
        price_5s_ago = None
        for price, timestamp in reversed(self.price_buffer):
            if timestamp <= cutoff_time:
                price_5s_ago = price
                break
        
        if price_5s_ago is None or price_5s_ago == 0:
            return 0.0
        
        # Calculate volatility
        return abs(current_price - price_5s_ago) / price_5s_ago
    
    def is_trading_halted(self) -> bool:
        """Check if trading is currently halted due to volatility"""
        if self.is_halted and self.halt_until:
            if datetime.utcnow() >= self.halt_until:
                self.is_halted = False
                self.halt_until = None
        return self.is_halted