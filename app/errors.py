class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, retry_after: int | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after = retry_after

class EmailDeliveryError(Exception):
    """Raised when an OTP email cannot be delivered."""
