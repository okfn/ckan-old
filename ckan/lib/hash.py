import hmac
import hashlib

from pylons import config, request

secret = config['beaker.session.secret']

def get_message_hash(value):
    return hmac.new(secret, value, hashlib.sha1).hexdigest()

def get_redirect():
    '''Checks the return_to value against the hash, and if it
    is valid then returns the return_to for redirect. Otherwise
    it returns None.'''
    return_to = request.params.get('return_to')
    hash_given = request.params.get('hash', '')
    if not (return_to and hash_given):
        return None
    hash_expected = get_message_hash(return_to)
    if hash_given == hash_expected:
        return return_to.encode('utf-8')
    return None
