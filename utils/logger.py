import logging
import os
from datetime import datetime
from pathlib import Path

# ── 로그 디렉터리(logs/) 자동 생성 ──────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOG_DIR / f"bot_{datetime.utcnow():%Y%m%d}.log"

# ── 기본 로깅 설정 ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,                         # 필요시 DEBUG 로 변경
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler()                 # 터미널에도 동시에 출력
    ],
)

# ── 편하게 쓰기 위한 단일 로거 객체 ────────────────────────
log = logging.getLogger("crypto_bot")