class ProviderError(Exception):
    """Base class for AI provider errors."""
    pass

class HardwareError(Exception):
    """Raised when required hardware (e.g. GPU) is missing or fails."""
    def __init__(self, message="Required hardware (GPU) is unavailable", device="cuda"):
        self.message = message
        self.device = device
        super().__init__(self.message)

class ProviderQuotaError(ProviderError):
    """Raised when an AI provider's quota is exceeded or payment is required."""
    def __init__(self, message="Provider quota exceeded or payment required", provider_name="unknown"):
        self.message = message
        self.provider_name = provider_name
        super().__init__(self.message)

class ProviderNetworkError(ProviderError):
    """Raised when there's a persistent network issue with the provider."""
    pass
