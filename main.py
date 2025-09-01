import asyncio
from asyncio import tasks as _tasks

from data.futures_ws import FuturesDepthStream, EnhancedFuturesStream
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
from strategy.obi_scalper import OBIScalperStrategy
from strategy.vwap_mean_reversion import VWAPMeanReversionStrategy
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

    # 2) PositionManager 초기화
    pos_manager = PositionManager()
    await pos_manager.init()

    # 3) Strategy initialization based on configuration
    if settings.STRATEGY_TYPE == "VWAP":
        log.info("[Main] Starting VWAP Mean Reversion Strategy")
        await run_vwap_strategy(pos_manager)
    else:
        log.info("[Main] Starting OBI Scalping Strategy")
        await run_obi_strategy(pos_manager)


async def run_vwap_strategy(pos_manager: PositionManager):
    """Run VWAP Mean Reversion Strategy"""
    strategy = VWAPMeanReversionStrategy()
    stream = EnhancedFuturesStream(settings.SYMBOL, strategy)
    ws_task = asyncio.create_task(stream.run(), name="EnhancedStream")
    
    try:
        while True:
            # Wait for strategy warmup
            if not strategy.is_ready():
                await asyncio.sleep(1.0)
                continue
            
            # Generate signal using VWAP strategy
            sig = strategy.signal()
            
            if sig in ["LONG", "SHORT"]:
                # Get current VWAP for context
                indicator_data = strategy.get_indicator_data()
                current_price = indicator_data.get('current_price', 0)
                current_vwap = indicator_data.get('vwap', 0)
                
                if current_price > 0:
                    # Place limit order at current price
                    order_side = "BUY" if sig == "LONG" else "SELL"
                    order = await place_limit_maker(order_side, current_price)
                    
                    # Register with position manager (enhanced with VWAP context)
                    await pos_manager.register_order(
                        order, 
                        strategy_type="VWAP", 
                        vwap_at_entry=current_vwap
                    )
                    
                    # Enhanced logging with VWAP context
                    log.info(f"[VWAP Strategy] {sig} order placed: price={current_price:.2f}, vwap={current_vwap:.2f}")
            
            await asyncio.sleep(0.2)  # Same cycle time as OBI strategy
            
    except asyncio.CancelledError:
        log.info('VWAP strategy cancelled, shutting down...')
    finally:
        ws_task.cancel()
        await pos_manager.close()


async def run_obi_strategy(pos_manager: PositionManager):
    """Run OBI Scalping Strategy"""
    strategy = OBIScalperStrategy()
    stream = FuturesDepthStream(settings.SYMBOL)
    ws_task = asyncio.create_task(stream.run(), name="DepthStream")
    
    try:
        while True:
            snap = stream.depth
            if snap and "b" in snap and "a" in snap and len(snap["b"]) > 0 and len(snap["a"]) > 0:
                # Update strategy with new depth data
                strategy.update_depth(snap)
                
                sig = strategy.signal()
                bid = float(snap["b"][0][0])
                ask = float(snap["a"][0][0])
                mid = (bid + ask) / 2

                if sig == "LONG":
                    order = await place_limit_maker("BUY", mid)
                    await pos_manager.register_order(order, strategy_type="OBI")
                elif sig == "SHORT":
                    order = await place_limit_maker("SELL", mid)
                    await pos_manager.register_order(order, strategy_type="OBI")

            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        log.info('OBI strategy cancelled, shutting down...')
    finally:
        ws_task.cancel()
        await pos_manager.close()


def _kill(loop: asyncio.AbstractEventLoop):
    for task in asyncio.all_tasks(loop):
        task.cancel()


async def monitor_tasks():
    while True:
        all_tasks = asyncio.all_tasks()
        
        # Categorize tasks by name
        named_tasks = []
        unnamed_task_info = []
        
        for task in all_tasks:
            name = task.get_name()
            if name.startswith('Task-'):
                # Get coroutine info for unnamed tasks
                coro = task.get_coro()
                coro_name = coro.__name__ if hasattr(coro, '__name__') else str(coro)
                
                # Try to get filename from coroutine
                try:
                    filename = coro.cr_frame.f_code.co_filename if hasattr(coro, 'cr_frame') else 'unknown'
                    filename = filename.split('/')[-1] if '/' in filename else filename  # Just filename, not full path
                    unnamed_task_info.append(f"{name}({coro_name}@{filename})")
                except:
                    unnamed_task_info.append(f"{name}({coro_name})")
            else:
                named_tasks.append(name)
        
        # Create informative log message
        if unnamed_task_info:
            log.debug(f"[TaskMonitor] Total: {len(all_tasks)} | Named: {named_tasks} | Unnamed: {unnamed_task_info}")
        else:
            log.debug(f"[TaskMonitor] Total: {len(all_tasks)} | Running: {named_tasks}")
        
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
