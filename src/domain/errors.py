
class AppError(Exception):
    status_code = 400
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        if status_code:
            self.status_code = status_code
        self.message = message

class BadRequest(AppError):
    status_code = 400

class UpstreamError(AppError):
    status_code = 502
