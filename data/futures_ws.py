import aiohttp, asyncio, json
from config.settings import settings

class FuturesDepthStream:
    def __init__(self, symbol: str):
        self.symbol = symbol.lower()
        self.depth = None

    async def run(self):
        url = f"{settings.FUTURES_WS}/{self.symbol}@depth@100ms"
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self.depth = json.loads(msg.data)
                    else:
                        break