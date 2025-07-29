import asyncio
from binance import AsyncClient, BinanceSocketManager

from config.settings import settings
from utils.logger import log


class FuturesDepthStream:
    def __init__(self, symbol: str):
        self.symbol = symbol.lower()
        self.depth = None

    async def run(self):
        try:
            # Create AsyncClient for futures
            kwargs = {
                "api_key": settings.BINANCE_API_KEY,
                "api_secret": settings.BINANCE_SECRET,
                "testnet": settings.TESTNET,
            }
            client = await AsyncClient.create(**kwargs)
            
            try:
                bm = BinanceSocketManager(client)
                # Use futures depth stream
                async with bm.futures_depth_socket(self.symbol) as stream:
                    while True:
                        msg = await stream.recv()
                        # Transform message to match original format expected by strategy
                        # BinanceSocketManager returns {'bids': [...], 'asks': [...], ...}
                        # but strategy expects {'b': [...], 'a': [...], ...}
                        if 'bids' in msg and 'asks' in msg:
                            self.depth = {
                                'b': msg['bids'],
                                'a': msg['asks']
                            }
            finally:
                await client.close_connection()
        except asyncio.CancelledError:
            log.info("FuturesDepthStream: cancelled")
            raise
        except Exception as e:
            log.exception("FuturesDepthStream error")
            raise e