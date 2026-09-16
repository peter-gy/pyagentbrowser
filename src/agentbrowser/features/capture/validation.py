def validate_screenshot_wait_ms(wait_ms: int) -> None:
    if wait_ms < 0:
        raise ValueError("wait_ms must be greater than or equal to 0")


def validate_screenshot_threshold(threshold: float) -> None:
    if isinstance(threshold, bool) or not isinstance(threshold, int | float):
        raise TypeError("threshold must be a number")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
