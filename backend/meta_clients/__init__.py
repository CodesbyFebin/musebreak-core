"""Open-weight Meta client adapters — integrate with backend.open_source (Part 2)."""
from .open_weights import OpenWeightsRouter
from .gateway import MetaGatewayClient

__all__ = ["OpenWeightsRouter", "MetaGatewayClient"]
