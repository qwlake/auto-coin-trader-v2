import pytest
import asyncio
import sys
import os
from dotenv import load_dotenv

# Add the project root to sys.path for imports and change working directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Change working directory to project root before loading .env
original_cwd = os.getcwd()
os.chdir(project_root)

# Load .env files from project root
load_dotenv()
load_dotenv(".apikey")

# Restore original working directory
os.chdir(original_cwd)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the entire test session"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_settings():
    """Reset settings to default values after each test"""
    from config.settings import settings
    original_dry_run = getattr(settings, 'DRY_RUN', False)
    original_size_quote = getattr(settings, 'SIZE_QUOTE', 10.0)
    original_symbol = getattr(settings, 'SYMBOL', 'BTCUSDT')
    
    yield
    
    # Reset to original values
    settings.DRY_RUN = original_dry_run
    settings.SIZE_QUOTE = original_size_quote
    settings.SYMBOL = original_symbol
