"""Provider adapters registry."""

from providers.base import CaptchaProvider, CaptchaProviderMeta
from providers.halligan_provider import HalliganProvider
from providers.dynamic_provider import DynamicProvider

__all__ = [
    "CaptchaProvider",
    "CaptchaProviderMeta",
    "HalliganProvider",
    "DynamicProvider",
]
