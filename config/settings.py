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

    # 호가 불균형 전략 파라미터
    DEPTH_LEVEL: int = 5
    OBI_LONG: float = 0.70
    OBI_SHORT: float = 0.30
    TP_PCT: float = 0.0005
    SL_PCT: float = 0.0005
    ORDER_TTL: float = 2.0

    # ★ 여기에만 고정: 사용할 코인 수량이 아니라 '얼마만큼의 코인 계정화폐(USDT/USDC)로 주문할지'
    QUOTE_ASSET: str = "USDT"      # "USDT" or "USDC"
    SIZE_QUOTE: float = 20        # ex: 20 USDT or 20 USDC

    @property
    def FUTURES_REST(self) -> str:
        return "https://testnet.binancefuture.com" if self.TESTNET else "https://fapi.binance.com"

    @property
    def FUTURES_WS(self) -> str:
        return "wss://fstream.binancefuture.com" if self.TESTNET else "wss://fstream.binance.com"


    model_config = {               # ← v2 방식의 설정
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

settings = Settings()