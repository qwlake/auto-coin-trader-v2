import asyncio
from binance import AsyncClient, BinanceSocketManager

from config.settings import settings
from utils.logger import log


class DepthStream:
    def __init__(self, client: AsyncClient, symbol: str):
        self.client = client
        self.symbol = symbol.lower()
        self.depth = None          # 최신 depth 스냅샷

    async def run(self):
        try:
            bm = BinanceSocketManager(self.client)
            # partial depth: level=N, speed=100 ms
            async with bm.depth_socket(self.symbol, depth=settings.DEPTH_LEVEL, interval=100) as stream:
                while True:
                    msg = await stream.recv()
                    # msg is a dict like {'bids': [...], 'asks': [...], ...}
                    self.depth = msg
        except asyncio.CancelledError:
            log.info("DepthStream: cancelled")
            raise

        except Exception as e:
            log.exception("DepthStream error")
            raise e
