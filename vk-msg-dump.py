import argparse
import logging
from MsgProcessor import MsgProcessor
from AttachmentsProcessor import AttachmentsProcessor
from vk_utils import acquire_session

APP_ID = '6787646'
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Dumps all your conversations on vk.com to local folder',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-d', '--direct-only', action='store_true',
                    help='Download only direct messages ignoring group chats')
parser.add_argument('-t', '--test', action='store_true',
                    help='Limit number of downloaded conversations to 10 for configuration testing')
parser.add_argument('--save-path', default='dumps/',
                    help='Path to directory with downloaded messages')
parser.add_argument('--creds', type=open, default=None,
                    help='Path to json file containing your credentials for vk.com')
parser.add_argument('--min-len', type=int, default=0,
                    help='Minimal length of saved conversation')
parser.add_argument('-a', '--attachments', type=str, nargs='*',
                    help='Types of attachment to save',default=[])

if __name__ == '__main__':
    args = parser.parse_args()
    session = acquire_session(args.creds, APP_ID, 'messages', logger)
    vkapi = session.get_api()
    msg_processor = MsgProcessor(vkapi, save_path=args.save_path, min_len=args.min_len)
    dump_path = msg_processor.save_all_messages_data(direct_only=args.direct_only, test_run=args.test)
    at_processor = AttachmentsProcessor(dump_path=dump_path, types=set(args.attachments))
    at_processor.download(direct_only=args.direct_only, test_run=args.test)
