import logging
import blinker

from ckan.model.notifier import DomainObjectNotification, Notification
from ckan.model.notifier import ROUTING_KEYS, DomainObjectNotificationOperation
from ckan.lib.async_notifier import AsyncConsumer
from common import SearchError

log = logging.getLogger(__name__)


class SearchIndexWorker(AsyncConsumer):
    """
    Waits for async notifications about package updates and sends them to SearchIndexer.
    In tests, this class is instantiated and then run(). In deployment, this file is 
    opened in its own process/shell.
    """
    
    def __init__ (self, backend):
        queue_name = 'search_indexer'
        routing_key = '*'
        super(SearchIndexWorker, self).__init__(queue_name, routing_key)
        self.backend = backend

    def callback(self, notification):
        self.dispatch_notification(notification, self.backend)
      
    @classmethod     
    def dispatch_notification(cls, notification, backend):
        """ Call the appropriate index method for a given notification. """
        if not isinstance(notification, DomainObjectNotification):
            return
        log.debug("Search received notification: %s" % notification)
        try:
            index = backend.index_for(notification.domain_object_class)
            op = notification['operation']
            if op == 'new':
                index.insert_dict(notification.domain_object)
            elif op == 'changed':
                index.update_dict(notification.domain_object)
            elif op == 'deleted':
                index.remove(notification.domain_object)
            else:
                log.warn("Unknown operation: %s" % op)
        except Exception, ex:
            log.exception(ex)


def update_index(sender, **notification_dict):
    from ckan.lib.search import get_backend
    notification = Notification.recreate_from_dict(notification_dict)
    SearchIndexWorker.dispatch_notification(notification, get_backend())

def setup_synchronous_indexing():
    for routing_key in ROUTING_KEYS:
        signal = blinker.signal(routing_key)
        signal.connect(update_index)

def remove_synchronous_indexing():
    for routing_key in ROUTING_KEYS:
        signal = blinker.signal(routing_key)
        signal.disconnect(update_index)


