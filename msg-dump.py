import vk
import time
import math
from collections import deque
import tqdm
import json
import logging
import sys

MAX_COUNT = 200
FIELDS = 'first_name,last_name,screen_name,bdate,common_count,is_friend,photo_max_orig'
API_VERSION = '5.87'

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s | %(levelname)s : %(message)s',
                    level=logging.INFO, stream=sys.stdout)




def get_password_and_id():
    creds = json.load(open('creds.json'))
    return creds['pass'], creds['id']

password, id = get_password_and_id()

session = vk.AuthSession(app_id='6787646', user_login=id,
                         scope='messages', user_password=password) if password else vk.AuthSession()
vkapi = vk.API(session)



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


t = Throater()


def get_list(func, initial_offset=0, **kwargs):
    i = 0
    t.ready()
    things = func(v=API_VERSION, count=MAX_COUNT, offset=initial_offset, **kwargs)
    count = things['count']
    things = things['items']
    while len(things) < count - initial_offset:
        i += 1
        t.ready()
        new_things = func(v=API_VERSION, count=MAX_COUNT, offset=initial_offset + len(things), **kwargs)
        things.extend(new_things['items'])
    return things


def get_all_messages(peer_id, initial_offset=0):
    return get_list(vkapi.messages.getHistory, initial_offset, user_id=peer_id)


def get_all_convs(initial_offset=0):
    return get_list(vkapi.messages.getConversations, initial_offset)


def get_dm_and_chat_ids_from_convs(convs):
    direct_conv_ids = []
    chat_conv_ids = []
    for c in convs:
        peer = c['conversation']['peer']

        if peer['type'] == 'user':
            direct_conv_ids.append(peer['id'])
        else:
            chat_conv_ids.append(peer['id'])
    return direct_conv_ids, chat_conv_ids


def get_data_draft(ids):
    data = {'total_msg_count': 0, 'direct': {}, 'chat': {}, 'profiles': {}}
    for i in tqdm.tqdm_notebook(ids):
        t.ready()
        batch = vkapi.messages.getHistory(v=API_VERSION, count=MAX_COUNT, extended=1, fields=FIELDS, peer_id=i)
        count = batch['count']
        items = batch['items']
        profiles = batch.get('profiles', [])
        key = 'direct' if 2 * 10 ** 9 > i > 0 else 'chat'

        data['total_msg_count'] += count
        data[key][i] = {'count': count, 'items': items}
        for profile in profiles:
            data['profiles'][profile['id']] = profile

    return data


def estimate_requests(data):
    r = 0
    d = 0
    for v in list(data['direct'].values()) + list(data['chat'].values()):
        done = len(v['items'])
        left = v['count'] - done
        r += math.ceil(left / MAX_COUNT)
        l += left
    return r, l


def complete_data_draft(data):
    dmi = list(data['direct'].keys())
    ci = list(data['chat'].keys())
    dmi.sort(key=lambda x: data['direct'][x]['count'])
    ci.sort(key=lambda x: data['chat'][x]['count'])
    rn, l = estimate_requests(data)
    logger.info('Need to download {} messages in {} requests'.format(l, rn))
    with tqdm.tqdm_notebook(total=rn) as pbar:
        for user_id in dmi + ci:
            key = 'direct' if 2 * 10 ** 9 > user_id > 0 else 'chat'
            done = len(data[key][user_id]['items'])
            total = data[key][user_id]['count']
            if done >= total:
                continue
            expected_requests = math.ceil((total - done) / MAX_COUNT)
            data[key][user_id]['items'].extend(get_all_messages(user_id, done))
            pbar.update(expected_requests)

    return data


def get_all_messages_data():
    convs = get_all_convs()
    dmi, ci = get_dm_and_chat_ids_from_convs(convs)
    # dmi, ci = dmi[:5],ci[:5]
    logger.info('Starting fetch \n Collecting meta info and estimates')
    data = get_data_draft(dmi + ci)
    logger.info(
        'Meta info collected. \nTotal messages found: {}\nCollecting messages text'.format(data['total_msg_count']))
    data = complete_data_draft(data)
    return data


data = get_all_messages_data()

json.dump(data, open('nikkorobk_data_first_iteration.json', 'w'))
