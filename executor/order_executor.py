from decimal import Decimal, ROUND_DOWN
from utils.logger import log
from config.settings import settings
from binance import AsyncClient

# 전역 AsyncClient 주입 및 Optional 선언
client: AsyncClient | None = None

# DRY_RUN 지원

def inject_client(c: AsyncClient):
    """AsyncClient 인스턴스 주입"""
    global client
    client = c


def _qty(usdt: float, price: float) -> str:
    """거래소 LOT_SIZE 규칙 대응: 소수 6자리로 내림"""
    qty = Decimal(usdt / price).quantize(Decimal("0.000001"), ROUND_DOWN)
    return format(qty, "f")

async def place_limit_maker(side: str, price: float):
    """
    spot 이면 spot LIMIT_MAKER, futures 면 futures post-only 지정가 자동 분기
    """
    qty_str = _qty(settings.SIZE_QUOTE, price)

    if settings.DRY_RUN:
        log.info(f"[DRY_RUN] {side} LIMIT_MAKER simulated: {settings.SYMBOL} @ {price}, qty={qty_str}")
        return {
            "orderId": -1,
            "symbol": settings.SYMBOL,
            "side": side,
            "type": "LIMIT_MAKER",
            "price": f"{price:.2f}",
            "origQty": qty_str,
            "status": "NEW"
        }

    assert client, "AsyncClient가 주입되지 않았습니다."
    if settings.MODE == "spot":
        order = await client.create_order(
            symbol=settings.SYMBOL,
            side=side,
            type="LIMIT_MAKER",
            timeInForce="GTC",
            quantity=qty_str,
            price=f"{price:.2f}",
            recvWindow=5000,
        )
    else:  # futures
        order = await client.futures_create_order(
            symbol=settings.SYMBOL,
            side=side,
            type="LIMIT",           # 지정가
            timeInForce="GTX",      # POST-ONLY
            quantity=qty_str,
            price=f"{price:.2f}",
            newOrderRespType="ACK",
            recvWindow=5000,
        )

    log.info(f"[Executor] {side} LIMIT_MAKER {order['orderId']} @ {price}, qty={qty_str}")
    return order

async def cancel_order(order_id: int):
    """주문 취소 (DRY_RUN 지원)"""
    if settings.DRY_RUN:
        log.info(f"[DRY RUN] Cancel orderId={order_id}")
        return {"orderId": order_id, "status": "CANCELED", "simulated": True}

    assert client, "AsyncClient not injected"
    resp = await client.cancel_order(symbol=settings.SYMBOL, orderId=order_id)
    log.info(f"Canceled order {order_id}: status={resp.get('status')}")
    return resp

async def get_open_orders():
    """현재 미체결 주문 조회 (DRY_RUN 지원)"""
    if settings.DRY_RUN:
        log.info("[DRY RUN] get_open_orders")
        return []

    assert client, "AsyncClient not injected"
    orders = await client.get_open_orders(symbol=settings.SYMBOL)
    return orders
