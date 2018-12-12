__all__ = [
    "BrowserInitError",
    "BrowserStagingError",
    "AutoBrowserError",
    "AutoTabError",
]


class BrowserStagingError(Exception):
    pass


class BrowserInitError(Exception):
    pass


class AutoBrowserError(Exception):
    pass


class AutoTabError(Exception):
    pass
