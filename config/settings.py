from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API
    BINANCE_API_KEY: str
    BINANCE_SECRET: str
    TESTNET: bool = True

    # Dry run
    DRY_RUN: bool = False

    # 심볼 (ex: "BTCUSDT" 또는 "BTCUSDC_PERP")
    SYMBOL: str = "BTCUSDT"
    
    # Strategy Selection
    STRATEGY_TYPE: str = "OBI"  # "OBI" or "VWAP"

    # 호가 불균형 전략 파라미터 (OBI Strategy)
    DEPTH_LEVEL: int = 5
    OBI_LONG: float = 0.70
    OBI_SHORT: float = 0.30
    TP_PCT: float = 0.0005
    SL_PCT: float = 0.0005
    ORDER_TTL: float = 2.0

    # ★ 여기에만 고정: 사용할 코인 수량이 아니라 '얼마만큼의 코인 계정화폐(USDT/USDC)로 주문할지'
    QUOTE_ASSET: str = "USDT"      # "USDT" or "USDC"
    SIZE_QUOTE: float = 20        # ex: 20 USDT or 20 USDC
    
    # VWAP Mean Reversion Strategy Parameters
    VWAP_BAND_MULTIPLIER: float = 1.5
    VWAP_STDDEV_PERIOD: int = 20
    VWAP_PROFIT_TARGET: float = 0.006  # 0.6%
    VWAP_STOP_LOSS: float = 0.003      # 0.3%
    
    # ADX Parameters
    ADX_PERIOD: int = 14
    ADX_TREND_THRESHOLD: float = 20.0
    ADX_STRONG_TREND_THRESHOLD: float = 40.0
    
    # Volatility Monitor
    VOLATILITY_THRESHOLD: float = 0.0015  # 0.15%
    VOLATILITY_HALT_DURATION: int = 600   # 10 minutes
    
    # Session Management
    SESSION_RESET_HOUR: int = 0  # UTC hour to reset VWAP

    model_config = {               # ← v2 방식의 설정
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()
print(settings)
