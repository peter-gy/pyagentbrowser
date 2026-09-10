def validate_screenshot_wait_ms(wait_ms: int) -> None:
    if wait_ms < 0:
        raise ValueError("wait_ms must be greater than or equal to 0")
