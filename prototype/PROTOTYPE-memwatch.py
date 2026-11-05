"""PROTOTYPE：背景取樣本程序＋所有子程序的記憶體（RSS），記錄峰值。"""
import threading
import time

import psutil


class MemWatch:
    def __init__(self, interval=0.05):
        self.interval, self.peak, self._stop = interval, 0, threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _sample(self):
        me = psutil.Process()
        total = me.memory_info().rss
        for c in me.children(recursive=True):
            try:
                total += c.memory_info().rss
            except psutil.Error:
                pass
        return total

    def _run(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, self._sample())
            time.sleep(self.interval)

    def __enter__(self):
        self.peak = self._sample()
        self._t.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._t.join()


def mb(n):
    return f"{n / 1024 / 1024:.0f}MB"
