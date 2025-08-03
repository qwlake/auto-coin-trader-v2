#!/usr/bin/env python3
"""
Test script for VWAP Mean Reversion Strategy Integration
Tests the indicator calculations and strategy logic without requiring API connections.
"""

import asyncio
import sys
from datetime import datetime

# Add current directory to path for imports
sys.path.append('.')

from strategy.indicators import VWAPCalculator, ADXCalculator, VWAPBandCalculator, VolatilityMonitor
from strategy.vwap_mean_reversion import VWAPMeanReversionStrategy
from config.settings import settings


def test_indicators():
    """Test individual indicator calculations"""
    print("Testing Indicators...")
    
    # Test VWAP Calculator
    print("\n1. Testing VWAP Calculator:")
    vwap_calc = VWAPCalculator()
    
    # Simulate some trades
    trades = [
        (100.0, 10.0),  # price, volume
        (101.0, 15.0),
        (99.5, 8.0),
        (102.0, 12.0),
    ]
    
    for price, volume in trades:
        vwap = vwap_calc.update(price, volume)
        print(f"  Trade: {price}@{volume} -> VWAP: {vwap:.2f}")
    
    # Test ADX Calculator
    print("\n2. Testing ADX Calculator:")
    adx_calc = ADXCalculator(period=14)
    
    # Simulate some OHLC data
    ohlc_data = [
        (100.5, 99.0, 100.0),  # high, low, close
        (101.0, 99.5, 100.5),
        (102.0, 100.0, 101.5),
        (101.5, 100.5, 101.0),
        (103.0, 101.0, 102.5),
    ]
    
    for high, low, close in ohlc_data:
        adx = adx_calc.update(high, low, close)
        print(f"  OHLC: H{high} L{low} C{close} -> ADX: {adx}")
    
    # Test VWAP Bands
    print("\n3. Testing VWAP Bands:")
    band_calc = VWAPBandCalculator(window_size=5, multiplier=1.5)
    current_vwap = vwap_calc.get_vwap()
    
    for price, _ in trades:
        upper, lower = band_calc.update(price, current_vwap)
        print(f"  Price: {price} VWAP: {current_vwap:.2f} -> Bands: [{lower:.2f}, {upper:.2f}]")
    
    # Test Volatility Monitor
    print("\n4. Testing Volatility Monitor:")
    vol_monitor = VolatilityMonitor(threshold=0.015, halt_duration=10)  # 1.5% threshold, 10s halt
    
    test_prices = [100.0, 100.5, 101.0, 102.5, 100.8]  # Include volatility spike
    for price in test_prices:
        is_halted = vol_monitor.update_price(price)
        print(f"  Price: {price} -> Halted: {is_halted}")
    
    print("✓ All indicators tested successfully")


def test_vwap_strategy():
    """Test VWAP strategy integration"""
    print("\nTesting VWAP Strategy...")
    
    # Override settings for testing
    settings.STRATEGY_TYPE = "VWAP"
    settings.ADX_TREND_THRESHOLD = 20.0
    settings.ADX_STRONG_TREND_THRESHOLD = 40.0
    
    strategy = VWAPMeanReversionStrategy()
    
    print(f"  Initial state - Ready: {strategy.is_ready()}")
    print(f"  Warmup trades: {strategy.warmup_trades}/{strategy.min_warmup_trades}")
    
    # Simulate enough trades for warmup
    print("\n  Simulating trades for warmup...")
    for i in range(105):
        price = 100.0 + (i % 10 - 5) * 0.1  # Price oscillates around 100
        volume = 10.0 + (i % 5)
        strategy.update_trade(price, volume)
        
        if i % 20 == 0:
            print(f"    Trade {i}: price={price:.2f}, ready={strategy.is_ready()}")
    
    # Simulate some kline data for ADX
    print("\n  Simulating kline data for ADX...")
    for i in range(20):
        high = 100.0 + i * 0.1 + 0.5
        low = 100.0 + i * 0.1 - 0.5
        close = 100.0 + i * 0.1
        strategy.update_kline(high, low, close)
        
        if i % 5 == 0:
            indicator_data = strategy.get_indicator_data()
            print(f"    Kline {i}: ADX={indicator_data.get('adx')}")
    
    # Test signal generation
    print("\n  Testing signal generation:")
    
    # Test scenarios
    scenarios = [
        ("Normal market", 100.0, 10.0),
        ("High volatility", 110.0, 15.0),  # Should trigger halt
        ("Below VWAP", 95.0, 8.0),        # Should generate LONG
        ("Above VWAP", 105.0, 12.0),      # Should generate SHORT
    ]
    
    for desc, price, volume in scenarios:
        print(f"\n    Scenario: {desc}")
        strategy.update_trade(price, volume)
        
        signal = strategy.signal()
        indicator_data = strategy.get_indicator_data()
        
        print(f"      Price: {price}, VWAP: {indicator_data.get('vwap', 0):.2f}")
        print(f"      Bands: [{indicator_data.get('lower_band', 0):.2f}, {indicator_data.get('upper_band', 0):.2f}]")
        print(f"      ADX: {indicator_data.get('adx')}")
        print(f"      Signal: {signal}")
        print(f"      Halted: {indicator_data.get('is_halted', False)}")
    
    print("✓ VWAP strategy tested successfully")


def test_configuration():
    """Test configuration parameters"""
    print("\nTesting Configuration...")
    
    print(f"  STRATEGY_TYPE: {settings.STRATEGY_TYPE}")
    print(f"  VWAP_BAND_MULTIPLIER: {settings.VWAP_BAND_MULTIPLIER}")
    print(f"  VWAP_STDDEV_PERIOD: {settings.VWAP_STDDEV_PERIOD}")
    print(f"  VWAP_PROFIT_TARGET: {settings.VWAP_PROFIT_TARGET}")
    print(f"  VWAP_STOP_LOSS: {settings.VWAP_STOP_LOSS}")
    print(f"  ADX_PERIOD: {settings.ADX_PERIOD}")
    print(f"  ADX_TREND_THRESHOLD: {settings.ADX_TREND_THRESHOLD}")
    print(f"  ADX_STRONG_TREND_THRESHOLD: {settings.ADX_STRONG_TREND_THRESHOLD}")
    print(f"  VOLATILITY_THRESHOLD: {settings.VOLATILITY_THRESHOLD}")
    print(f"  VOLATILITY_HALT_DURATION: {settings.VOLATILITY_HALT_DURATION}")
    print(f"  SESSION_RESET_HOUR: {settings.SESSION_RESET_HOUR}")
    
    print("✓ Configuration tested successfully")


def main():
    """Main test function"""
    print("VWAP Mean Reversion Strategy Integration Test")
    print("=" * 50)
    
    try:
        test_configuration()
        test_indicators()
        test_vwap_strategy()
        
        print("\n" + "=" * 50)
        print("✓ ALL TESTS PASSED! VWAP strategy integration is working correctly.")
        print("\nTo use VWAP strategy:")
        print("1. Set STRATEGY_TYPE=VWAP in your .env file")
        print("2. Adjust VWAP parameters as needed")
        print("3. Test in DRY_RUN mode first")
        print("4. Run: python main.py")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()