import asyncio
import time
from typing import Optional
import aiosqlite
from binance import AsyncClient
from config.settings import settings
from utils.logger import log

class OrderTracker:
    """
    주문 상태를 주기적으로 조회하고 DB에 기록합니다.
    """
    def __init__(self, client: AsyncClient, db_path: str = None, interval: float = 1.0):
        self.client = client
        self.db_path = db_path or "storage/orders.db"
        self.interval = interval  # 초 단위 폴링 주기
        self._task: Optional[asyncio.Task] = None

    async def _init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    price REAL,
                    quantity REAL,
                    status TEXT,
                    created_at INTEGER,
                    filled_qty REAL DEFAULT 0
                )
                """
            )
            await db.commit()

    async def add(self, order: dict):
        # 주문 생성 후 호출: DB에 새로운 주문 저장
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO orders(order_id, symbol, side, price, quantity, status, created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (
                    order["orderId"],
                    order["symbol"],
                    order["side"],
                    float(order.get("price", 0)),
                    float(order.get("origQty", 0)),
                    order.get("status", ""),
                    int(time.time() * 1000),
                ),
            )
            await db.commit()

    async def _update_once(self):
        async with aiosqlite.connect(self.db_path) as db:
            # 미체결/부분체결 주문만 조회
            cursor = await db.execute(
                "SELECT order_id FROM orders WHERE status IN ('NEW','PARTIALLY_FILLED')"
            )
            rows = await cursor.fetchall()
            for (order_id,) in rows:
                try:
                    order = await self.client.get_order(
                        symbol=settings.SYMBOL,
                        orderId=order_id,
                    )
                except Exception as e:
                    log.error(f"OrderTracker: 주문 조회 실패 (order_id={order_id}): {e}")
                    continue
                status = order.get("status")
                filled = float(order.get("executedQty", 0))
                await db.execute(
                    "UPDATE orders SET status=?, filled_qty=? WHERE order_id=?",
                    (status, filled, order_id),
                )
                await db.commit()
                # 포지션 관리 or 후처리 로직
                if status in ("FILLED", "CANCELED"):
                    log.info(f"OrderTracker: order_id={order_id} status={status}")
                    # TODO: 포지션 업데이트 콜백 호출 등

    async def start(self):
        # DB 초기화
        await self._init_db()
        # 백그라운드로 업데이트 루프 시작
        self._task = asyncio.create_task(self._loop())
        return self._task

    async def _loop(self):
        try:
            while True:
                await self._update_once()
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            log.info("OrderTracker: 폴링 루프 취소됨")
            raise

# 유틸 함수: main.py 에서 사용
async def start_order_tracker(client: AsyncClient, interval: float = 1.0):
    tracker = OrderTracker(client, interval=interval)
    return await tracker.start()
