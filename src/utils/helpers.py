"""
Helper utilities for the Financial Research Analyst Agent.
"""

from decimal import Decimal
from typing import Any, Optional, Union

_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}


def format_currency(value: Union[int, float, Decimal], currency: str = "USD") -> str:
    """Format a number as currency with magnitude suffixes."""
    sym = _CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    abs_v = abs(value)
    if abs_v >= 1e12:
        return f"{sym}{value / 1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{sym}{value / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{sym}{value / 1e6:.2f}M"
    if abs_v >= 1e3:
        return f"{sym}{value / 1e3:.2f}K"
    return f"{sym}{value:,.2f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format a decimal number as percentage (0.15 -> '15.00%')."""
    return f"{value * 100:.{decimals}f}%"


def format_large_number(value: Union[int, float]) -> str:
    """Format large numbers with T/B/M/K suffixes."""
    abs_v = abs(value)
    if abs_v >= 1e12:
        return f"{value / 1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{value / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{value / 1e6:.2f}M"
    if abs_v >= 1e3:
        return f"{value / 1e3:.2f}K"
    return f"{value:,.0f}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default on zero or invalid inputs."""
    try:
        return numerator / denominator if denominator else default
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def calculate_percentage_change(old_value: float, new_value: float) -> Optional[float]:
    """Calculate percentage change between two values."""
    return ((new_value - old_value) / abs(old_value)) * 100 if old_value else None


def clean_numeric(value: Any) -> Optional[float]:
    """Clean and convert a value to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").replace("$", "").replace("%", "").strip())
        except ValueError:
            return None
    return None


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    return text if len(text) <= max_length else f"{text[:max_length - len(suffix)]}{suffix}"
