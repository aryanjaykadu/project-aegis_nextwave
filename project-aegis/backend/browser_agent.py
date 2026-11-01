def file_disaster_report(lat: float, lon: float, severity: str) -> bool:
    """No government disaster-reporting endpoint is configured; never submit to a test site."""
    return False
