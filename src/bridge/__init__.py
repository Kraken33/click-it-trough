"""
Bridge module for communication with physical iPhone via WebDriverAgent (WDA).
"""
from .wda_client import WDAClient
from .device_manager import DeviceManager

__all__ = ["WDAClient", "DeviceManager"]
