import asyncio
from asyncio import tasks as _tasks

from data.futures_ws import FuturesDepthStream
from executor.position_manager import PositionManager

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
from strategy.obi_scalper import signal as obi_signal
from executor.order_executor import place_limit_maker, inject_client
from binance import AsyncClient

async def runner():
    monitor_task = asyncio.create_task(monitor_tasks(), name="TaskMonitor")

    # 1) AsyncClient 생성
    kwargs = {
        "api_key": settings.BINANCE_API_KEY,
        "api_secret": settings.BINANCE_SECRET,
        "testnet": settings.TESTNET,
    }
    client = await AsyncClient.create(**kwargs)
    inject_client(client)

    # symbols = await client.get_all_tickers()
    # log.info(f"all tickers: {symbols}")

    # 2) PositionManager 초기화
    pos_manager = PositionManager(client)
    await pos_manager.init()

    # 3) FuturesDepthStream 초기화
    stream = FuturesDepthStream(settings.SYMBOL)
    ws_task = asyncio.create_task(stream.run(), name="DepthStream")

    # 4) OBI 스캘핑
    try:
        while True:
            snap = stream.depth
            if snap:
                sig = obi_signal(snap)
                bid = float(snap["b"][0][0])
                ask = float(snap["a"][0][0])
                mid = (bid + ask) / 2

                if sig == "BUY":
                    order = await place_limit_maker("BUY", mid)
                    await pos_manager.register_order(order)
                elif sig == "SELL":
                    order = await place_limit_maker("SELL", mid)
                    await pos_manager.register_order(order)

            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        log.info('Runner cancelled, shutting down...')
    finally:
        ws_task.cancel()
        await client.close_connection()
        await pos_manager.close()


def _kill(loop: asyncio.AbstractEventLoop):
    for task in asyncio.all_tasks(loop):
        task.cancel()


async def monitor_tasks():
    while True:
        all_tasks = asyncio.all_tasks()
        log.info(f"[TaskMonitor] Total tasks: {len(all_tasks)}, running: {[t.get_name() for t in all_tasks]}")
        await asyncio.sleep(5)

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
