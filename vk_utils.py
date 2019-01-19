import json
import vk_api

API_VERSION = '5.87'

class VKLoginError(Exception):
    pass


def get_password_and_id(creds):
    creds = json.load(creds)
    try:
        return creds['pass'], creds['id']
    except KeyError as e:
        raise VKLoginError('Credentials file does not contain proper keys (id, pass), check {}'.format(creds.name))


def acquire_session_from_user(logger, app_id, scope):
    attempt = 0
    while -1 < attempt < 3:
        id = input('We need to login to your vk profile\n' +
                   'Please type in your phone number or rerun with --creds key\n')
        password = input('Password:\n') if id else ''
        try:
            session = vk_api.VkApi(app_id=app_id, login=id,
                                   scope=scope, password=password, api_version=API_VERSION)
            session.auth()
            attempt = -1
        except vk_api.exceptions.BadPassword:
            attempt += 1
            logger.error('Seems like some of your credentials are wrong. Please try again.\n')
    if attempt == 3:
        raise VKLoginError("You tried to enter password three times. Exiting.\n")

    return session


def acquire_session(creds, app_id, scope, logger):
    if creds is not None:
        password, id = get_password_and_id(creds)
        try:
            session = vk_api.VkApi(app_id=app_id, login=id,
                                   scope=scope, password=password, api_version=API_VERSION)
            session.auth()
        except vk_api.exceptions.BadPassword:
            raise VKLoginError('Credentials from {} are not correct. Please check your id and password'
                               .format(creds.name))
    else:
        session = acquire_session_from_user(logger, app_id=app_id, scope=scope)
    return session


def id_is_direct(id):
    return 0 < id < 2000000000
