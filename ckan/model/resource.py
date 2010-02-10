from meta import *
from types import make_uuid
import vdm.sqlalchemy
from sqlalchemy.ext.orderinglist import ordering_list

from core import DomainObject, Package, package_table, Revision, State

package_resource_table = Table(
    'package_resource', metadata,
    Column('id', types.UnicodeText, primary_key=True, default=make_uuid),
    Column('package_id', types.UnicodeText, ForeignKey('package.id')),
    Column('url', types.UnicodeText, nullable=False),
    Column('format', types.UnicodeText),
    Column('description', types.UnicodeText),
    Column('hash', types.UnicodeText),
    Column('position', types.Integer),
    )

vdm.sqlalchemy.make_table_stateful(package_resource_table)
resource_revision_table = vdm.sqlalchemy.make_revisioned_table(package_resource_table)

class PackageResource(vdm.sqlalchemy.RevisionedObjectMixin,
                      vdm.sqlalchemy.StatefulObjectMixin,
                      DomainObject):
    def __init__(self, package_id=None, url=u'', format=u'', description=u'', hash=u''):
        if package_id:
            self.package_id = package_id
        self.url = url
        self.format = format
        self.description = description
        self.hash = hash
        
    def __repr__(self):
        return '<PackageResource id=%s package_id=%s url=%s description=%s>' % (self.id, self.package_id, self.url, self.description)

    @staticmethod
    def get_columns():
        return ('url', 'format', 'description', 'hash')

mapper(PackageResource, package_resource_table, properties={
    'package':orm.relation(Package,
        backref=orm.backref('resources',
                            collection_class=ordering_list('position'),
                            order_by=[package_resource_table.c.position],
                            cascade='all, delete, delete-orphan',
                            ),
                       )
    },
    order_by=[package_resource_table.c.package_id],
    extension = vdm.sqlalchemy.Revisioner(resource_revision_table)       
)
    
vdm.sqlalchemy.modify_base_object_mapper(PackageResource, Revision, State)
PackageResourceRevision= vdm.sqlalchemy.create_object_version(
    mapper, PackageResource, resource_revision_table)
