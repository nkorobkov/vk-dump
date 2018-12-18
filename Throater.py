import time
from collections import deque

class Throater:

    def __init__(self, mrc=3, ti=1.5):
        self.total_sleep = 0
        self.time_interval = ti
        self.max_req_c = mrc
        self.history = deque([0] * self.max_req_c)

    def ready(self):
        now = time.time()
        self.history.append(now)
        prev = self.history.popleft()
        to_sleep = prev + self.time_interval - now
        if to_sleep > 0:
            self.total_sleep += to_sleep
            time.sleep(to_sleep)
        return