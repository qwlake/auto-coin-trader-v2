from decimal import Decimal, ROUND_DOWN
from utils.logger import log
from config.settings import settings
from binance import AsyncClient

# ── 클라이언트는 main.py 에서 생성 후 주입 ──────────────────
client: AsyncClient | None = None   # 타입 힌트

def inject_client(c: AsyncClient):
    """main.py 쪽에서 생성한 AsyncClient 인스턴스를 받아 저장"""
    global client
    client = c

def _qty(usdt: float, price: float) -> str:
    """거래소 LOT_SIZE 규칙을 피하기 위해 6자리 반올림"""
    qty = Decimal(usdt / price).quantize(Decimal("0.000001"), ROUND_DOWN)
    return format(qty, "f")

async def place_limit_maker(side: str, price: float):
    assert client, "AsyncClient not injected"
    order = await client.create_order(
        symbol=settings.SYMBOL,
        side=side,
        type="LIMIT_MAKER",
        timeInForce="GTC",
        quantity=_qty(settings.SIZE_USDT, price),
        price=f"{price:.2f}",
        recvWindow=5000,
    )
    log.info(f"{side} LIMIT_MAKER {order['orderId']} @ {price}")
    return order