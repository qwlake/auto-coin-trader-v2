from config.settings import settings
from utils.logger import log
from typing import Optional
from .indicators import VWAPCalculator, ADXCalculator, VWAPBandCalculator, VolatilityMonitor


class VWAPMeanReversionStrategy:
    """
    VWAP Mean Reversion Trading Strategy
    
    Implements mean reversion logic using VWAP as the central anchor point.
    Uses ADX for market regime filtering and volatility monitoring for safety.
    
    Entry Logic:
    - LONG: Price below lower band and below VWAP (mean reversion opportunity)
    - SHORT: Price above upper band and above VWAP (mean reversion opportunity)
    
    Market Regime Filtering:
    - Only trade in sideways markets (ADX < trend threshold)
    - Avoid strong trending markets (ADX > strong trend threshold)
    
    Safety Mechanisms:
    - Volatility-based trading halts
    - Minimum warmup period before activation
    """
    
    def __init__(self):
        # Initialize all indicators
        self.vwap_calc = VWAPCalculator()
        self.adx_calc = ADXCalculator(period=settings.ADX_PERIOD)
        self.band_calc = VWAPBandCalculator(
            window_size=settings.VWAP_STDDEV_PERIOD,
            multiplier=settings.VWAP_BAND_MULTIPLIER
        )
        self.volatility_monitor = VolatilityMonitor(
            threshold=settings.VOLATILITY_THRESHOLD,
            halt_duration=settings.VOLATILITY_HALT_DURATION
        )
        
        # Strategy state
        self.ready = False
        self.warmup_trades = 0
        self.min_warmup_trades = 100  # Minimum trades before strategy activation
        self.current_price = 0.0
        self.current_vwap = 0.0
        self.current_upper_band = 0.0
        self.current_lower_band = 0.0
        self.current_adx = None
    
    def update_trade(self, price: float, volume: float):
        """Update indicators with new trade data"""
        if price <= 0 or volume <= 0:
            return
            
        # Update VWAP
        self.current_vwap = self.vwap_calc.update(price, volume)
        self.current_price = price
        
        # Update bands
        if self.current_vwap > 0:
            self.current_upper_band, self.current_lower_band = self.band_calc.update(price, self.current_vwap)
        
        # Update volatility monitor
        self.volatility_monitor.update_price(price)
        
        # Track warmup progress
        self.warmup_trades += 1
        if self.warmup_trades >= self.min_warmup_trades:
            self.ready = True
    
    def update_kline(self, high: float, low: float, close: float):
        """Update ADX with new kline data"""
        if high <= 0 or low <= 0 or close <= 0:
            return
            
        self.current_adx = self.adx_calc.update(high, low, close)
    
    def signal(self) -> Optional[str]:
        """Generate trading signal based on VWAP mean reversion logic"""
        if not self.ready:
            log.debug("[VWAP Strategy] Strategy not ready, warmup in progress")
            return None
            
        # Safety checks
        if self.volatility_monitor.is_trading_halted():
            log.info("[VWAP Strategy] Trading halted due to volatility")
            return None
        
        if self.current_adx is None:
            log.debug("[VWAP Strategy] ADX not available yet")
            return None
            
        # Market regime filter
        if self.current_adx >= settings.ADX_STRONG_TREND_THRESHOLD:
            log.debug(f"[VWAP Strategy] Strong trend detected (ADX={self.current_adx:.2f}), no trading")
            return None
            
        if self.current_adx >= settings.ADX_TREND_THRESHOLD:
            log.debug(f"[VWAP Strategy] Developing trend (ADX={self.current_adx:.2f}), monitoring")
            return None
        
        # Validate indicator values
        if not all([
            self.current_price > 0,
            self.current_vwap > 0,
            self.current_upper_band > 0,
            self.current_lower_band > 0
        ]):
            log.debug("[VWAP Strategy] Indicators not ready")
            return None
        
        # Mean reversion signal generation
        if (self.current_price >= self.current_upper_band and 
            self.current_price > self.current_vwap):
            log.info(f"[VWAP Strategy] SHORT signal: price={self.current_price:.2f}, "
                    f"upper_band={self.current_upper_band:.2f}, vwap={self.current_vwap:.2f}, "
                    f"adx={self.current_adx:.2f}")
            return "SHORT"  # Mean reversion: price too high
            
        elif (self.current_price <= self.current_lower_band and 
              self.current_price < self.current_vwap):
            log.info(f"[VWAP Strategy] LONG signal: price={self.current_price:.2f}, "
                    f"lower_band={self.current_lower_band:.2f}, vwap={self.current_vwap:.2f}, "
                    f"adx={self.current_adx:.2f}")
            return "LONG"   # Mean reversion: price too low
        
        return None
    
    def is_ready(self) -> bool:
        """Check if strategy has enough data to generate signals"""
        return (self.ready and 
                self.current_adx is not None and 
                self.current_vwap > 0 and
                self.current_upper_band > 0 and
                self.current_lower_band > 0)
    
    def get_indicator_data(self) -> dict:
        """Get current values of all indicators for external use"""
        return {
            'vwap': self.current_vwap,
            'upper_band': self.current_upper_band,
            'lower_band': self.current_lower_band,
            'adx': self.current_adx,
            'is_halted': self.volatility_monitor.is_trading_halted(),
            'current_price': self.current_price,
            'warmup_trades': self.warmup_trades,
            'ready': self.ready
        }
    
    def check_session_reset(self) -> bool:
        """Reset VWAP at configured hour (default: 00:00 UTC)"""
        from datetime import datetime
        
        now = datetime.utcnow()
        reset_time = now.replace(hour=settings.SESSION_RESET_HOUR, minute=0, second=0, microsecond=0)
        
        if now >= reset_time and self.vwap_calc.last_reset < reset_time:
            log.info(f"[VWAP Strategy] Daily session reset at {now}")
            self.vwap_calc.reset_session()
            
            # Reset strategy state for new session
            self.ready = False
            self.warmup_trades = 0
            self.current_vwap = 0.0
            self.current_upper_band = 0.0
            self.current_lower_band = 0.0
            
            return True
        return False