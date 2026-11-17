"""Google 搜索：搜尋網址的組合，搜尋文字經網址編碼。"""

from gt.search import google_search_url


def test_google_search_url_puts_text_in_q():
    assert google_search_url("potato") == "https://www.google.com/search?q=potato"


def test_google_search_url_encodes_special_characters():
    assert google_search_url("a b&c/金鑰\n#1?") == "https://www.google.com/search?q=a+b%26c%2F%E9%87%91%E9%91%B0%0A%231%3F"
