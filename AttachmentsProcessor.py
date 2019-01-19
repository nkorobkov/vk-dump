import logging
from DTask import *
from DTasksProcessor import DTaskProcessor
import glob
import tqdm
import json
import os, sys
from collections import defaultdict
from vk_utils import id_is_direct


class AttachmentsProcessor:
    SUPPORTED_TYPES = {'photo', 'audio'}

    AUDIO_SIZE_COEF = 28624
    IMG_SIZE_COEF = 0.24
    BYTE_IN_MB = 1048576

    def __init__(self, dump_path, types):
        self.dump_path = dump_path
        self.types = types.intersection(self.SUPPORTED_TYPES)
        self.size_f_by_type = defaultdict(lambda x: lambda y: 0, '')
        self.register_size_f()
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(format='%(message)s',
                            level=logging.INFO, stream=sys.stdout)

    def get_photo_info(self, photo_at):
        ph = photo_at['photo']['sizes'][-1]
        size = (ph['width'] * ph['height'] * self.IMG_SIZE_COEF / self.BYTE_IN_MB)
        url = ph['url']
        return size, url

    def get_audio_info(self, audio_at):
        size = (audio_at['audio']['duration'] * self.AUDIO_SIZE_COEF / self.BYTE_IN_MB)
        url = audio_at['audio']['url'].split('?')[0]
        return size, url

    def register_size_f(self):
        self.size_f_by_type['photo'] = self.get_photo_info
        self.size_f_by_type['audio'] = self.get_audio_info

    def make_save_path(self, user_id, att):
        return os.path.join(self.dump_path, user_id, att)

    def make_task(self, at, user_id, msg_id):
        att = at['type']
        if att in self.types:
            save_path = self.make_save_path(user_id, att)
            size, url = self.size_f_by_type.get(att)(at)
            dt = DTask(url, save_path, size, user_id, msg_id)
            return dt
        return NoFileDTask()

    def get_download_tasks(self, direct_only, test_run):
        tasks_by_type = defaultdict(list)
        files_list = glob.glob(os.path.join(self.dump_path, '*/messages.json'))
        if test_run:
            files_list = files_list[:5]
        self.logger.info('Extracting attachments info from {} files'.format(len(files_list)))
        for file in tqdm.tqdm(files_list):
            user_id = (os.path.basename(os.path.dirname(file)))
            if direct_only and not id_is_direct(user_id):
                continue
            conv = json.load(open(file))
            for msg in conv['items']:
                msg_id = msg.get('id', None)
                for at in msg['attachments']:
                    task = self.make_task(at, user_id, msg_id)
                    if task.should_be_executed:
                        att = at.get('type')
                        tasks_by_type[att].append(task)
        return tasks_by_type

    def extract_info_from_tasks(self, tasks_by_type):
        info = {'count': 0, 'size': 0., 'items': {}}
        for type, tasks in tasks_by_type.items():
            n = len(tasks)
            s = sum(map(lambda x: x.size, tasks))
            info['count'] += n
            info['size'] += s
            info['items'][type] = {'count': n, 'size': s}
        return info

    def log_info(self,info):
        self.logger.info('{} new attachments found, total size: {:.2f} Mb.'.format(info.get('count'), info.get('size')))

        for t, ti in info['items'].items():
            self.logger.info('{} ({:.2f} Mb) -- {}'.format(ti['count'], ti['size'], t))

    def download(self, direct_only, test_run):
        if not self.types:
            self.logger.info("No attachments download scheduled. Pass valid attachment types to download attachments.")
            return
        tasks_by_type = self.get_download_tasks(direct_only, test_run)
        info = self.extract_info_from_tasks(tasks_by_type)
        self.log_info(info)

        for type, tasks in tasks_by_type.items():
            type_info = info['items'][type]
            if type_info['count']:
                self.logger.info('Downloading {} ({:.2f} Mb)'.format(type, info['items'][type]['size']))
                dt_processor = DTaskProcessor(tasks)
                failed_tasks = dt_processor.process_tasks()

        if tasks_by_type.items():
            success = len(tasks) - len(failed_tasks)
            self.logger.info('{} attachments are downloaded. {} tasks failed'.format(success, len(failed_tasks)))
