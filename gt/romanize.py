"""拼音：以 uroman 把文字轉成拉丁字母。https://pypi.org/project/uroman/"""

_uroman = None                                   # uroman 的資料，第一次使用時才載入（約 1 秒）


def romanize(text):
    """text 的拉丁字母拼音；與 text 相同時（原文已是拉丁字母）回傳空字串。"""
    global _uroman
    if _uroman is None:
        import uroman
        _uroman = uroman.Uroman()
    roman = _uroman.romanize_string(text)
    return "" if roman == text else roman
