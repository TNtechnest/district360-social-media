"""Simple user-agent string parser for session tracking."""

import re


def parse_user_agent(ua: str) -> dict:
    """Parse a user-agent string into device, browser, and OS info.

    Returns:
        Dict with keys: ``device``, ``device_type``, ``browser``, ``os``.
    """
    result = {'device': '', 'device_type': '', 'browser': '', 'os': ''}

    if not ua:
        return result

    ua_lower = ua.lower()

    if 'mobile' in ua_lower or 'android' in ua_lower:
        result['device_type'] = 'mobile'
    elif 'tablet' in ua_lower or 'ipad' in ua_lower:
        result['device_type'] = 'tablet'
    else:
        result['device_type'] = 'desktop'

    if 'windows' in ua_lower:
        result['os'] = 'Windows'
    elif 'mac os' in ua_lower or 'macintosh' in ua_lower:
        result['os'] = 'macOS'
    elif 'linux' in ua_lower:
        result['os'] = 'Linux'
    elif 'android' in ua_lower:
        result['os'] = 'Android'
    elif 'ios' in ua_lower or 'iphone' in ua_lower:
        result['os'] = 'iOS'
    elif 'chrome os' in ua_lower:
        result['os'] = 'ChromeOS'

    if 'chrome' in ua_lower and 'edg' not in ua_lower:
        result['browser'] = 'Chrome'
    elif 'firefox' in ua_lower:
        result['browser'] = 'Firefox'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        result['browser'] = 'Safari'
    elif 'edg' in ua_lower:
        result['browser'] = 'Edge'
    elif 'opera' in ua_lower:
        result['browser'] = 'Opera'

    # Extract device name from common patterns
    device_match = re.search(r'\((.*?)\)', ua)
    if device_match:
        result['device'] = device_match.group(1)[:255]

    return result
