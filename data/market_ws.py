import asyncio
from binance import AsyncClient
from binance.streams import BinanceSocketManager

class DepthStream:
    def __init__(self, client: AsyncClient, symbol: str):
        self.client = client
        self.symbol = symbol.lower()
        self.depth = None          # 최신 depth 스냅샷

    async def run(self):
        bm = BinanceSocketManager(self.client)
        # partial depth: level=N, speed=100 ms
        async with bm.depth_socket(self.symbol, depth=settings.DEPTH_LEVEL, interval="100ms") as stream:
            async for msg in stream:
                self.depth = msg    # strategy 가 바로 사용
