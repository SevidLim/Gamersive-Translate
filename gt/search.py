"""Google 搜索：組合搜尋網址。純邏輯，不依賴 Qt。"""

import urllib.parse

SEARCH_URL = "https://www.google.com/search"


def google_search_url(text):
    """以 Google 搜尋 text 的網址，text 經網址編碼。"""
    return f"{SEARCH_URL}?{urllib.parse.urlencode({'q': text})}"
