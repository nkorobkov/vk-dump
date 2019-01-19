from Throater import Throater
import tqdm
import math
import logging
import sys
import os
import time
import json
from vk_utils import id_is_direct


class MsgProcessor:
    MAX_COUNT = 200
    FIELDS = 'first_name,last_name,screen_name,bdate,common_count,is_friend,photo_max,photo_50'

    def __init__(self, vkapi, save_path, min_len=0):
        self.vkapi = vkapi
        self.min_len = min_len
        self.save_path = save_path
        self.t = Throater()
        self.t.ready()
        self.sc_name = self.vkapi.account.getProfileInfo()['screen_name']
        self.filename_template = os.path.join(save_path, self.sc_name, "{}", 'messages.json')
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(format='%(message)s',
                            level=logging.INFO, stream=sys.stdout)

    def get_list(self, func, initial_offset=0, totalcount=10 ** 10, **kwargs):
        i = 0
        self.t.ready()
        things = func(count=self.MAX_COUNT, offset=initial_offset, **kwargs)
        count = min(things['count'] - initial_offset, totalcount)
        things = things['items']
        while len(things) < count:
            i += 1
            self.t.ready()
            new_things = func(count=min(self.MAX_COUNT, count - len(things)),
                              offset=initial_offset + len(things), **kwargs)
            things.extend(new_things['items'])
        return things

    def get_all_messages(self, peer_id, initial_offset=0, count=10 ** 10):
        return self.get_list(self.vkapi.messages.getHistory, initial_offset, user_id=peer_id, totalcount=count)

    def get_all_convs(self, initial_offset=0):
        return self.get_list(self.vkapi.messages.getConversations, initial_offset)

    def get_dm_and_chat_ids_from_convs(self, convs):
        direct_conv_ids = []
        chat_conv_ids = []
        for c in convs:
            peer = c['conversation']['peer']
            if peer['type'] == 'user':
                direct_conv_ids.append(peer['id'])
            else:
                chat_conv_ids.append(peer['id'])
        return direct_conv_ids, chat_conv_ids

    def get_data_draft(self, convs):
        data = {'total_new_msg_count': 0, 'items': {}}
        for c in tqdm.tqdm(convs):
            i = self.id_form_conv(c)
            self.t.ready()
            batch = self.vkapi.messages.getHistory(count=self.MAX_COUNT,
                                                   extended=1,
                                                   fields=self.FIELDS,
                                                   peer_id=i)
            new = batch['count'] - c['downloaded']
            data['total_new_msg_count'] += new
            batch['new'] = new
            data['items'][i] = batch
        return data

    def estimate_requests(self, data):
        r = 0
        l = 0
        for v in list(data['items'].values()):
            if v['count'] < self.min_len:
                continue
            done = len(v['items'])
            left = max(v['new'] - done, 0)
            r += math.ceil(left / self.MAX_COUNT)
            l += left
        return r, l

    def generate_full_conversations_from_draft(self, data):
        ids = list(data['items'].keys())
        ids.sort(key=lambda x: data['items'][x]['new'])
        rn, nm = self.estimate_requests(data)
        if rn > 0:
            self.logger.info('Need to download {} new messages in {} requests'.format(nm, rn))
            pbar = tqdm.tqdm(total=rn)
        for user_id in ids:
            obj = data['items'][user_id]
            total = obj['count']
            done = len(obj['items'])
            if total < self.min_len:
                continue
            if done >= total:
                yield user_id, obj
                continue
            if obj['new'] == obj['count']:
                # No dump present
                expected_requests = math.ceil((total - done) / self.MAX_COUNT)
                obj['items'].extend(self.get_all_messages(user_id, done))
                # here we might miss some info about attached messages authors.
                pbar.update(expected_requests)
                yield user_id, obj

            obj_old = json.load(open(self.filename_template.format(user_id)))
            done_old = obj_old['count']
            done_new = done
            new_messages = total - done_old
            obj_old['count'] = total
            if new_messages <= done_new:
                # no requests needed
                obj_old['items'] = obj['items'][:new_messages] + obj_old['items']
                # that is quite bad in terms of performance, TODO -- think of something better
            else:
                # need to query some new messages from the server
                expected_requests = math.ceil((new_messages - done_new) / self.MAX_COUNT)

                obj['items'].extend(self.get_all_messages(user_id, done_new, count=new_messages - done_new))
                # here we might miss some info about attached messages authors.
                obj_old['items'] = obj['items'][:new_messages] + obj_old['items']
                pbar.update(expected_requests)
            yield user_id, obj_old
        if rn > 0:
            pbar.close()

    def organize_filestructure(self, convs):
        dirname = os.path.join(self.save_path, self.sc_name)
        for c in convs:
            user_dirname = os.path.join(dirname, str(self.id_form_conv(c)))
            if not os.path.exists(user_dirname):
                os.makedirs(user_dirname)
        return dirname

    @staticmethod
    def id_form_conv(c):
        return c['conversation']['peer']['id']

    def separate_changed_conversations(self, convs):
        changed_convs = []
        for c in convs:
            filename = self.filename_template.format(self.id_form_conv(c))
            if not os.path.exists(filename):
                c['downloaded'] = 0
                changed_convs.append(c)
            else:
                saved_data = json.load(open(filename))
                last_saved_id = saved_data['items'][0]['id']
                if c['conversation']['last_message_id'] != last_saved_id:
                    c['downloaded'] = saved_data['count']
                    changed_convs.append(c)
        return changed_convs

    def update_convs(self, changed_convs):
        self.logger.info(
            'Updating {} changed conversations. Collecting meta info and estimates.'.format(len(changed_convs)))
        data = self.get_data_draft(changed_convs)

        self.logger.info('Meta info collected. Total new messages found: {}\nSaving messages text in {}'
                         .format(data['total_new_msg_count'], self.filename_template))
        for user_id, user_data in self.generate_full_conversations_from_draft(data):
            user_data['timestamp'] = time.time()
            filename = self.filename_template.format(user_id)
            with open(filename, 'w') as file:
                json.dump(user_data, file, ensure_ascii=False)

    def save_all_messages_data(self, direct_only=False, test_run=False):
        self.logger.info('Getting info about all conversations')
        convs = self.get_all_convs()
        convs_count = len(convs)
        if direct_only:
            convs = list(filter(lambda x: id_is_direct(self.id_form_conv(x)), convs))
        if test_run:
            convs = convs[:5]
        save_path = self.organize_filestructure(convs)
        changed_convs = self.separate_changed_conversations(convs)
        self.logger.info(
            'You got {} conversations. {} of them changed since last backup'.format(convs_count, len(changed_convs)))
        if changed_convs:
            self.update_convs(changed_convs)
        return save_path
