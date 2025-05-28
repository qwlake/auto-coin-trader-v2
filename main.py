import asyncio
from asyncio import tasks as _tasks

# ── monkey-patch for PyCharm debug ────────────────────────
_OriginalTask = asyncio.Task
class PatchedTask(_OriginalTask):
    def __init__(self, *args, **kwargs):
        kwargs.pop("eager_start", None)
        super().__init__(*args, **kwargs)
asyncio.Task = PatchedTask
_tasks.Task    = PatchedTask
# ──────────────────────────────────────────────────────────

import asyncio
import signal

from config.settings import settings
from utils.logger import log
from data.market_ws import DepthStream
from strategy.obi_scalper import signal as obi_signal
from executor.order_executor import place_limit_maker, inject_client
from executor.order_tracker import OrderTracker
from binance import AsyncClient

async def runner():
    # 1) Binance 클라이언트 초기화
    client = await AsyncClient.create(
        api_key=settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_SECRET,
        testnet=settings.TESTNET,
    )
    inject_client(client)

    # 2) OrderTracker 인스턴스 생성 및 시작
    tracker = OrderTracker(client, interval=1.0)
    tracker_task = await tracker.start()  # 백그라운드로 폴링 루프 시작

    # 3) DepthStream 실행
    stream = DepthStream(client, settings.SYMBOL)
    ws_task = asyncio.create_task(stream.run())

    try:
        # 4) 전략 루프
        while True:
            snap = stream.depth
            if snap:
                sig = obi_signal(snap)
                bid = float(snap["bids"][0][0])
                ask = float(snap["asks"][0][0])
                mid = (bid + ask) / 2
                if sig == 'LONG':
                    order = await place_limit_maker('BUY', mid)
                    await tracker.add(order)  # 주문 DB에 기록
                elif sig == 'SHORT':
                    order = await place_limit_maker('SELL', mid)
                    await tracker.add(order)
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        log.info('Runner cancelled, shutting down...')
    finally:
        # 5) 클린업: 스트림 및 트래커 종료
        if client:
            await client.close_connection()
        ws_task.cancel()
        tracker_task.cancel()


def _kill(loop: asyncio.AbstractEventLoop):
    for task in asyncio.all_tasks(loop):
        task.cancel()

if __name__ == '__main__':
    # 이벤트 루프 생성 및 설정
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 시그널 핸들러 등록
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: _kill(loop))

    # runner 실행
    try:
        loop.run_until_complete(runner())
    finally:
        loop.close()
