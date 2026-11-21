"""聆聽的播放：系統語音（QTextToSpeech）與 OpenAI 回傳的 mp3（QMediaPlayer）。只在 UI 執行緒使用。"""

from PySide6.QtCore import QBuffer, QIODevice, QLocale, QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtTextToSpeech import QTextToSpeech


class Speaker(QObject):
    """locales() 給 speech.prepare 比對；say() 以系統語音唸出，play() 播放 mp3；stop() 停止兩者。"""

    failed = Signal(str)                         # 播放失敗的原因
    started = Signal()                           # 系統語音開始唸出或 mp3 開始播放
    finished = Signal()                          # 系統語音唸完（或被停止）或 mp3 播到結尾

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tts = None                         # 第一次聆聽時才建立
        self._player = None
        self._buffer = QBuffer(self)             # 播放中的 mp3 內容
        self._speaking = False                   # 系統語音進入 Speaking 後為 True

    def locales(self):
        """系統語音可用的 locale（QLocale.name() 格式，例如 "zh_TW"）。"""
        if self._tts is None:
            self._tts = QTextToSpeech(self)
            self._tts.errorOccurred.connect(lambda _reason, text: self.failed.emit(text))
            self._tts.stateChanged.connect(self._tts_state)
        return [loc.name() for loc in self._tts.availableLocales()]

    def _tts_state(self, state):
        """Speaking 時送出 started；由 Speaking 回到 Ready 時送出 finished。"""
        if state == QTextToSpeech.State.Speaking:
            self._speaking = True
            self.started.emit()
        elif state == QTextToSpeech.State.Ready and self._speaking:
            self._speaking = False
            self.finished.emit()

    def say(self, text, locale):
        """以 locale（locales() 回傳的名稱）的系統語音唸出 text。"""
        self._tts.setLocale(QLocale(locale))
        self._tts.say(text)

    def play(self, audio):
        """播放 mp3 內容 audio（bytes）。"""
        if self._player is None:
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(QAudioOutput(self))
            self._player.errorOccurred.connect(lambda _error, text: self.failed.emit(text))
            self._player.playbackStateChanged.connect(
                lambda state: state == QMediaPlayer.PlaybackState.PlayingState and self.started.emit())
            self._player.mediaStatusChanged.connect(
                lambda status: status == QMediaPlayer.MediaStatus.EndOfMedia and self.finished.emit())
        self._player.setSource(QUrl())               # 先放開上一段，才能換 buffer 的內容
        self._buffer.close()
        self._buffer.setData(audio)
        self._buffer.open(QIODevice.ReadOnly)
        self._player.setSourceDevice(self._buffer, QUrl("speech.mp3"))
        self._player.play()

    def stop(self):
        if self._tts is not None:
            self._tts.stop()
        if self._player is not None:
            self._player.stop()
