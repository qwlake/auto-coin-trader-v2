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
    """LIMIT_MAKER 주문 실행 또는 시뮬레이션"""
    qty = _qty(settings.SIZE_USDT, price)
    order_params = {
        "symbol": settings.SYMBOL,
        "side": side,
        "type": "LIMIT_MAKER",
        "timeInForce": "GTC",
        "quantity": qty,
        "price": f"{price:.2f}",
        "recvWindow": 5000,
    }

    # 1) DRY_RUN 모드 처리
    if settings.DRY_RUN:
        log.info(f"[DRY RUN] {side} LIMIT_MAKER → {order_params}")
        # 모의 응답 생성
        return {
            "orderId": -1,
            "symbol": settings.SYMBOL,
            "side": side,
            "price": f"{price:.2f}",
            "origQty": qty,
            "status": "NEW",
            "simulated": True,
        }

    # 2) 실제 주문 실행
    assert client, "AsyncClient not injected"
    order = await client.create_order(**order_params)
    log.info(f"{side} LIMIT_MAKER orderId={order['orderId']} @ {price:.2f}")
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
