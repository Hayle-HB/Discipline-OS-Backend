class AppError(Exception):
    def __init__(self, error: str, status_code: int = 400, code: str | None = None):
        self.error = error
        self.status_code = status_code
        self.code = code
        super().__init__(error)
