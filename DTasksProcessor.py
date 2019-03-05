
from multiprocessing import Pool
import tqdm
from DTask import *
from typing import Iterable
import time

def process_task(task: DTask):
    try:
        r = (True, task.process())
    except LinkOutdatedException as e:
        task.error = e
        r = (False, task)
    return r

class DTaskProcessor:

    def __init__(self, tasks: Iterable[DTask]):
        self.tasks = tasks

    def prepare_dirs(self):
        for t in self.tasks:
            t.prepare_dir()

    def process_tasks(self):
        if self.tasks:
            failed_tasks = []
            sizes = map(lambda x: x.size, self.tasks)
            sum_size = int(sum(sizes))
            self.prepare_dirs()
            with tqdm.tqdm(total=sum_size) as td:
                with Pool(processes=8) as p:
                    for r in p.imap_unordered(process_task, self.tasks):
                        if not r[0]:
                            failed_tasks.append(r[1])
                            td.update(r[1].size)
                        else:
                            td.update(r[1].size)
            return failed_tasks
