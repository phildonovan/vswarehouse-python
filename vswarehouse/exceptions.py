class VSWarehouseError(Exception):
    pass


class AuthenticationError(VSWarehouseError):
    pass


class RateLimitError(VSWarehouseError):
    pass


class NotFoundError(VSWarehouseError):
    pass


class APIError(VSWarehouseError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")
