from Throater import Throater
import tqdm
import math
import logging
import sys
import os
import time
import json


class MsgProcessor:
    MAX_COUNT = 200
    FIELDS = 'first_name,last_name,screen_name,bdate,common_count,is_friend,photo_max,photo_50'
    API_VERSION = '5.87'

    def __init__(self, vkapi):
        self.vkapi = vkapi
        self.t = Throater()
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(format='%(asctime)s | %(levelname)s : %(message)s',
                            level=logging.INFO, stream=sys.stdout)

    def get_list(self, func, initial_offset=0, **kwargs):
        i = 0
        self.t.ready()
        things = func(v=self.API_VERSION, count=self.MAX_COUNT, offset=initial_offset, **kwargs)
        count = things['count']
        things = things['items']
        while len(things) < count - initial_offset:
            i += 1
            self.t.ready()
            new_things = func(v=self.API_VERSION, count=self.MAX_COUNT, offset=initial_offset + len(things), **kwargs)
            things.extend(new_things['items'])
        return things

    def get_all_messages(self, peer_id, initial_offset=0):
        return self.get_list(self.vkapi.messages.getHistory, initial_offset, user_id=peer_id)

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

    def get_data_draft(self, ids):
        data = {'total_msg_count': 0, 'items': {}}
        for i in tqdm.tqdm(ids):
            self.t.ready()
            batch = self.vkapi.messages.getHistory(v=self.API_VERSION,
                                                   count=self.MAX_COUNT,
                                                   extended=1,
                                                   fields=self.FIELDS,
                                                   peer_id=i)
            count = batch['count']
            data['total_msg_count'] += count
            data['items'][i] = batch
        return data

    def estimate_requests(self, data, min_len=None):
        r = 0
        l = 0
        for v in list(data['items'].values()):
            if min_len is not None and v['count'] < min_len:
                continue
            done = len(v['items'])
            left = v['count'] - done
            r += math.ceil(left / self.MAX_COUNT)
            l += left
        return r, l

    def generate_full_conversations_from_draft(self, data, min_len=None):
        ids = list(data['items'].keys())

        ids.sort(key=lambda x: data['items'][x]['count'])
        rn, l = self.estimate_requests(data, min_len)
        self.logger.info('Need to download {} messages in {} requests'.format(l, rn))
        with tqdm.tqdm(total=rn) as pbar:
            for user_id in ids:
                obj = data['items'][user_id]
                done = len(obj['items'])
                total = obj['count']
                if min_len is not None and total < min_len:
                    continue
                if done >= total:
                    yield user_id, obj
                    continue
                expected_requests = math.ceil((total - done) / self.MAX_COUNT)

                obj['items'].extend(self.get_all_messages(user_id, done))
                # here we might miss some info about attached messages authors.
                pbar.update(expected_requests)
                yield user_id, obj

    def organize_filestructure(self, save_path):
        self.t.ready()
        sc_name = self.vkapi.account.getProfileInfo(v=self.API_VERSION)['screen_name']
        dirname = os.path.join(save_path, sc_name)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        else:
            i = 1
            while True:
                new_dn = dirname + '_' + str(i)
                if not os.path.exists(new_dn):
                    os.makedirs(new_dn)
                    dirname = new_dn
                    break
                i += 1
        return os.path.join(dirname, "{}.json")

    def save_all_messages_data(self, save_path, direct_only=False, test_run=False, min_len=None):
        self.logger.info('Getting info about all conversations')
        convs = self.get_all_convs()
        dmi, ci = self.get_dm_and_chat_ids_from_convs(convs)
        if direct_only:
            ci = []
        if test_run:
            dmi, ci = dmi[:5], ci[:5]
        self.logger.info('Starting fetch \n Collecting meta info and estimates')
        data = self.get_data_draft(dmi + ci)
        name_template = self.organize_filestructure(save_path)

        self.logger.info('Meta info collected. \nTotal messages found: {}\Saving messages text in {}'
                         .format(data['total_msg_count'], name_template))
        for user_id, user_data in self.generate_full_conversations_from_draft(data, min_len):
            user_data['timestamp'] = time.time()
            with open(name_template.format(user_id), 'w') as file:
                json.dump(user_data, file, ensure_ascii=False)
