from labels import zone_label
from units import fahrenheit_to_celsius


def status(zone: str, fahrenheit: float) -> str:
    return f"{zone_label(zone)}: {fahrenheit_to_celsius(fahrenheit):.1f} C"
