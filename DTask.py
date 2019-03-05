import os
from urllib.request import urlretrieve
import requests


class LinkOutdatedException(Exception):
    pass

class DTask:

    def __init__(self, url, save_path, size = 1, peer_id = None, msg_id = None, filename = None):
        self.url = url
        self.save_path = save_path
        self.size = size
        self.peer_id = peer_id
        self.msg_id = msg_id
        if self.url:
            if filename is not None:
                self.filename = filename
            else:
                self.filename = self._get_filename_from_url()
            self.full_name = os.path.join(self.save_path, self.filename)
        self.should_be_executed = bool(self.url) and not os.path.exists(self.full_name)
        self.error = None

    def _get_filename_from_url(self):
        return self.url.split('/')[-1]

    def prepare_dir(self):
        if self.should_be_executed:
            if not os.path.exists(self.save_path):
                os.makedirs(self.save_path)

    def process(self):
        if self.should_be_executed:
            self.save_from_web2()
            return self.size
        return 0

    def save_from_web(self):
        # works really slow
        resp = requests.get(self.url, stream=True)
        if resp.status_code != 200:
            raise LinkOutdatedException('url responce is not 200')
        with open(self.full_name, 'wb') as f:
            for chunk in resp.iter_content():
                f.write(chunk)

    def save_from_web2(self):
        try:
            urlretrieve(self.url, self.full_name)
        except Exception as e:
            #print(e, self.url, self.msg_id, self.peer_id)
            raise LinkOutdatedException('problems retrieving file '+ str(e))


class NoFileDTask(DTask):

    def __init__(self):
        super().__init__('', '', 0)


