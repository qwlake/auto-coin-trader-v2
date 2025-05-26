import asyncio, signal
from decimal import Decimal
from config.settings import settings
from utils.logger import log
from strategy.obi_scalper import signal as obi_signal
from data.market_ws import DepthStream
from executor.order_executor import place_limit_maker, inject_client
from binance import AsyncClient

async def runner():
    # 1) 바이낸스 클라이언트 생성
    client = await AsyncClient.create(
        api_key=settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_SECRET,
        testnet=settings.TESTNET,
    )
    inject_client(client)

    # 2) 실시간 depth 스트림 시작
    stream = DepthStream(client, settings.SYMBOL)
    ws_task = asyncio.create_task(stream.run())

    # 3) 전략 루프 (200 ms 간격)
    try:
        while True:
            snap = stream.depth
            if snap:
                sig = obi_signal(snap)
                bid = float(snap["bids"][0][0])
                ask = float(snap["asks"][0][0])
                mid = (bid + ask) / 2
                if sig == "LONG":
                    await place_limit_maker("BUY", mid)
                elif sig == "SHORT":
                    await place_limit_maker("SELL", mid)
            await asyncio.sleep(0.2)
    finally:
        await client.close_connection()
        ws_task.cancel()


def _kill(loop):
    for task in asyncio.all_tasks(loop):
        task.cancel()


if __name__ == "__main__":
    # 1) 새 이벤트 루프 생성 및 설정
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 2) 시그널 핸들러 등록
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: _kill(loop))

    # 3) 런너 실행
    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()
