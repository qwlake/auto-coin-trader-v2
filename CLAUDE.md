# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Basic Rules

- All files you've modified should be committed to git with a descriptive message at the end of each step. The branch name should be claude.
- Don't write any code or files before user requested it.
- Complex requests should be broken down into smaller tasks.
- Thinkable requests should be preprocessed using gemini(e.g. gemini -p {prompt}).
- Manage strategies using the `STRATEGY.md` file.

## Project Overview

This is a cryptocurrency trading bot that implements an Order Book Imbalance (OBI) scalping strategy. The bot monitors market depth data from Binance and places limit orders when order book imbalance exceeds configured thresholds. It supports futures trading only.

## Environment Setup

Create a `.env` file with:
```
BINANCE_API_KEY=YOUR_KEY
BINANCE_SECRET=YOUR_SECRET
TESTNET=True
```

## Commands

**Run the bot:**
```bash
python main.py
```

**Install dependencies:**
```bash
poetry install
```

## Architecture

The system follows an event-driven architecture with these core components:

### Configuration (`config/settings.py`)
- Uses Pydantic settings with environment variable loading
- Key parameters: `SYMBOL`, `OBI_LONG`/`OBI_SHORT` thresholds, `TP_PCT`/`SL_PCT`
- `SIZE_QUOTE`: Amount in quote currency (USDT/USDC) to trade per order

### Data Layer (`data/`)
- **`futures_ws.py`**: Futures market depth WebSocket stream maintaining real-time order book snapshots in `depth` attribute

### Strategy (`strategy/obi_scalper.py`)
- **`calc_obi()`**: Calculates order book imbalance ratio from depth data
- **`signal()`**: Returns "LONG"/"SHORT" signals when OBI exceeds thresholds
- OBI = bid_volume / (bid_volume + ask_volume) for top N levels

### Execution Layer (`executor/`)
- **`order_executor.py`**: Places futures limit maker orders via Binance API
  - Uses futures LIMIT + GTX (post-only) order types
  - Includes DRY_RUN mode for testing
  - Uses global client injection pattern
- **`position_manager.py`**: Manages order lifecycle and position tracking
  - SQLite database with three tables: `pending_orders`, `active_positions`, `closed_positions`
  - Background monitoring loop checks order fills and TP/SL conditions
  - Automatically closes positions when profit/loss thresholds are hit

### Main Loop (`main.py`)
1. Creates AsyncClient and injects it into executor
2. Initializes PositionManager with database
3. Starts futures WebSocket depth stream
4. Continuously monitors OBI signals and places orders
5. Handles graceful shutdown with signal handlers

## Key Design Patterns

- **Dependency Injection**: AsyncClient is injected into executor module
- **Event-Driven**: WebSocket streams push depth updates, strategy consumes them
- **State Persistence**: All order and position state stored in SQLite database
- **Separation of Concerns**: Clear boundaries between data, strategy, execution, and position management

## Database Schema

The SQLite database (`storage/orders.db`) tracks:
- `pending_orders`: Orders placed but not yet filled
- `active_positions`: Filled orders awaiting TP/SL
- `closed_positions`: Completed trades with PnL

## Testing and Development

The bot includes DRY_RUN mode controlled by environment variable. When enabled, orders are simulated rather than sent to exchange.