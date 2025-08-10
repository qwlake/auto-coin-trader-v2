# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Basic Rules

- All files you've modified should be committed to git with a descriptive message at the end of each step. The branch name should be claude.
- Complex requests should be broken down into smaller tasks.
- Thinkable requests should be preprocessed using gemini(e.g. gemini -p {prompt}).
- Manage strategies using the `STRATEGY.md` file.

## Documentation

- **Strategy Documentation**: Refer to `docs/STRATEGY.md` and related files in `docs/` folder for strategy-specific documentation
- **GUI Development**: Refer to `GUI_README.md` for comprehensive GUI development and usage instructions
- **VWAP Strategy**: See `docs/vwap.v1.step1.md` and `docs/vwap.v1.step2.md` for VWAP implementation details

## Project Overview

This is a cryptocurrency trading bot that implements multiple trading strategies:
1. **Order Book Imbalance (OBI) Scalping**: Monitors market depth and trades on order book imbalances
2. **VWAP Mean Reversion**: Uses Volume Weighted Average Price for mean reversion signals

The bot supports futures trading on Binance with both strategies running independently.

## Environment Setup

Create a `.env` file with:
```
BINANCE_API_KEY=YOUR_KEY
BINANCE_SECRET=YOUR_SECRET
```

## Commands

**Run the bot:**
```bash
python main.py
```

**Install dependencies:**
```bash
uv sync
```

**Run GUI (Streamlit dashboard):**
```bash
python run_gui.py
```

**Run tests:**
```bash
uv run pytest
```

## Architecture

The system follows an event-driven architecture with these core components:

### Configuration (`config/`)
- **`base_settings.py`**: Base configuration class using Pydantic settings
- **`obi_settings.py`**: OBI strategy specific settings (OBI_LONG/OBI_SHORT thresholds)
- **`vwap_settings.py`**: VWAP strategy specific settings (VWAP_DEVIATION thresholds)
- **`settings.py`**: Main settings loader with environment variable support
- Key parameters: `SYMBOL`, `TP_PCT`/`SL_PCT`, `SIZE_QUOTE` (amount in quote currency per order)

### Data Layer (`data/`)
- **`futures_ws.py`**: WebSocket streams for market data
  - `FuturesDepthStream`: Basic order book depth stream for OBI strategy
  - `EnhancedFuturesStream`: Enhanced stream with kline data for VWAP strategy

### Strategy Layer (`strategy/`)
- **`base_strategy.py`**: Abstract base class defining strategy interface
- **`obi_scalper.py`**: Order Book Imbalance scalping strategy
  - `calc_obi()`: Calculates OBI ratio from depth data
  - `obi_signal()`: Returns "BUY"/"SELL" signals when OBI exceeds thresholds
- **`vwap_mean_reversion.py`**: VWAP-based mean reversion strategy
  - Calculates VWAP from kline data with warmup period
  - Generates signals when price deviates significantly from VWAP
- **`indicators.py`**: Technical indicators (VWAP calculation)

### Execution Layer (`executor/`)
- **`order_executor.py`**: Places futures limit maker orders via Binance API
  - Uses futures LIMIT + GTX (post-only) order types
  - Includes DRY_RUN mode for testing
  - Global client injection pattern
- **`position_manager.py`**: Manages order lifecycle and position tracking
  - SQLite database with tables: `pending_orders`, `active_positions`, `closed_positions`
  - Background monitoring loop for order fills and TP/SL conditions
  - Strategy-aware position tracking (OBI vs VWAP)

### Main Loop (`main.py`)
- **Multi-strategy runner**: Supports both OBI and VWAP strategies
- **`run_obi_strategy()`**: OBI strategy execution loop
- **`run_vwap_strategy()`**: VWAP strategy execution loop with warmup handling
- Task monitoring and graceful shutdown with signal handlers
- Dependency injection of AsyncClient into executor

### GUI Dashboard (`gui/`)
- **Streamlit-based web interface** accessible via `python run_gui.py`
- Real-time monitoring of positions, orders, and strategy performance
- Interactive charts and data visualization with Plotly
- **Comprehensive documentation**: See `GUI_README.md` for detailed usage, customization, and troubleshooting

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

### Test Framework
- **pytest** with async support (`pytest-asyncio`) for comprehensive testing
- Test environment configured with `.env` file loading
- Test suite covers order execution, position management, and strategy logic
- Run tests: `uv run pytest`

### Development Features  
- **DRY_RUN mode**: Environment variable controlled simulation mode
- **GUI Dashboard**: Real-time monitoring and debugging via Streamlit interface
- **Logging**: Comprehensive logging with configurable levels
- **Memory monitoring**: Strategy state and performance tracking

### Project Structure
```
auto-coin-trader-v2/
├── config/          # Configuration management
├── data/            # WebSocket data streams  
├── executor/        # Order execution and position management
├── strategy/        # Trading strategies (OBI, VWAP)
├── gui/            # Streamlit dashboard
├── test/           # Test suite
├── utils/          # Utilities (logging, etc.)
└── docs/           # Strategy documentation
```