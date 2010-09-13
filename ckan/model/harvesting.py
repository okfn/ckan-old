import datetime
from meta import *

from types import make_uuid
from core import *
from domain_object import DomainObject

__all__ = [
    'HarvestSource', 'harvest_source_table'
    'HarvestingJob', 'harvesting_job_table'
]

class DomainObject(DomainObject):

    key_attr = 'id'

#    def delete(self):
#        self.purge()

    @classmethod 
    def get(self, key, default=Exception, attr=None):
        """Finds a single entity in the register."""
        if attr == None:
            attr = self.key_attr
        kwds = {attr: key}
        o = self.filter(**kwds).first()
        if o:
            return o
        if default != Exception:
            return default
        else:
            raise Exception, "%s not found: %s" % (self.__name__, key)

    @classmethod 
    def filter(self, **kwds): 
        query = Session.query(self).autoflush(False)
        return query.filter_by(**kwds)

    @classmethod 
    def create_record(self, model_session, **kwds):
        # Create an object instance.
        domain_object = self.create_instance(**kwds)
        # Create a record for the object.
        model_session.add(domain_object)
        model_session.commit()
        # Return the object.
        return domain_object

    @classmethod 
    def create_instance(self, **kwds):
        # Initialise object key attribute.
        if self.key_attr not in kwds:
            kwds[self.key_attr] = self.create_key()
        # Create an object instance.
        domain_object = self(**kwds)
        return domain_object

    @classmethod 
    def create_key(self, **kwds):
        # By default, it's a new UUID.
        return make_uuid()


class HarvestSource(DomainObject): pass
    

class HarvestingJob(DomainObject): pass

    
harvest_source_table = Table('harvest_source', metadata,
        Column('id', types.UnicodeText, primary_key=True, default=make_uuid),
        Column('status', types.UnicodeText, default=u'New'),
        Column('url', types.UnicodeText, unique=True, nullable=False),
        Column('description', types.UnicodeText, default=u''),                      
        Column('user_ref', types.UnicodeText, default=u''),
        Column('publisher_ref', types.UnicodeText, default=u''),
        Column('created', DateTime, default=datetime.datetime.utcnow),
)

harvesting_job_table = Table('harvesting_job', metadata,
        Column('id', types.UnicodeText, primary_key=True, default=make_uuid),
        Column('status', types.UnicodeText, default=u''),
        Column('created', DateTime, default=datetime.datetime.utcnow),
        Column('user_ref', types.UnicodeText, nullable=False),
        Column('report', types.UnicodeText, default=u''),                     
        Column('source_id', UnicodeText, ForeignKey('harvest_source.id')), 
)

mapper(HarvestSource, harvest_source_table, properties={ })

mapper(HarvestingJob, harvesting_job_table, properties={ })

