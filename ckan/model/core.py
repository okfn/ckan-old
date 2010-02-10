import datetime

from pylons import config
from meta import *
import vdm.sqlalchemy

from types import make_uuid
import full_search

## VDM-specific tables

revision_table = vdm.sqlalchemy.make_revision_table(metadata)

## Our Domain Object Tables

license_table = Table('license', metadata,
        Column('id', types.Integer, primary_key=True),
        Column('name', types.Unicode(100)),
        )

package_table = Table('package', metadata,
        Column('id', types.UnicodeText, primary_key=True, default=make_uuid),
        Column('name', types.Unicode(100), unique=True, nullable=False),
        Column('title', types.UnicodeText),
        Column('version', types.Unicode(100)),
        Column('url', types.UnicodeText),
        Column('author', types.UnicodeText),
        Column('author_email', types.UnicodeText),
        Column('maintainer', types.UnicodeText),
        Column('maintainer_email', types.UnicodeText),                      
        Column('notes', types.UnicodeText),
        Column('license_id', types.Integer, ForeignKey('license.id')),
)

tag_table = Table('tag', metadata,
        Column('id', types.UnicodeText, primary_key=True, default=make_uuid),
        Column('name', types.Unicode(100), unique=True, nullable=False),
)

package_tag_table = Table('package_tag', metadata,
        Column('id', types.UnicodeText, primary_key=True, default=make_uuid),
        Column('package_id', types.UnicodeText, ForeignKey('package.id')),
        Column('tag_id', types.UnicodeText, ForeignKey('tag.id')),
        )


vdm.sqlalchemy.make_table_stateful(license_table)
vdm.sqlalchemy.make_table_stateful(package_table)
vdm.sqlalchemy.make_table_stateful(package_tag_table)
package_revision_table = vdm.sqlalchemy.make_revisioned_table(package_table)
# TODO: this has a composite primary key ...
package_tag_revision_table = vdm.sqlalchemy.make_revisioned_table(package_tag_table)


## -------------------
## Mapped classes

# TODO: replace this (or at least inherit from) standard SqlalchemyMixin in vdm
class DomainObject(object):
    
    text_search_fields = []

    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def by_name(self, name, autoflush=True):
        obj = Session.query(self).autoflush(autoflush).filter_by(name=name).first()
        return obj

    @classmethod
    def text_search(self, query, term):
        register = self
        make_like = lambda x,y: x.ilike('%' + y + '%')
        q = None
        for field in self.text_search_fields:
            attr = getattr(register, field)
            q = or_(q, make_like(attr, term))
        return query.filter(q)

    @classmethod
    def active(self):
        return Session.query(self).filter_by(state=State.ACTIVE)

    def purge(self):
        sess = orm.object_session(self)
        if hasattr(self, '__revisioned__'): # only for versioned objects ...
            # this actually should auto occur due to cascade relationships but
            # ...
            for rev in self.all_revisions:
                sess.delete(rev)
        sess.delete(self)

    def as_dict(self):
        _dict = {}
        table = orm.class_mapper(self.__class__).mapped_table
        for col in table.c:
            val = getattr(self, col.name)
            if isinstance(val, datetime.date):
                val = str(val)
            _dict[col.name] = val
        return _dict

    def __str__(self):
        return self.__unicode__().encode('utf8')

    def __unicode__(self):
        repr = u'<%s' % self.__class__.__name__
        table = orm.class_mapper(self.__class__).mapped_table
        for col in table.c:
            repr += u' %s=%s' % (col.name, getattr(self, col.name))
        repr += '>'
        return repr

    def __repr__(self):
        return self.__unicode__()

        
class License(DomainObject):
    def isopen(self):
        if self.name and \
           (self.name.startswith('OKD Compliant')
            or
            self.name.startswith('OSI Approved')
            ):
            return True
        return False

class Package(vdm.sqlalchemy.RevisionedObjectMixin,
        vdm.sqlalchemy.StatefulObjectMixin,
        DomainObject):
    
    text_search_fields = ['name', 'title']

    @classmethod
    def search_by_name(self, text_query):
        text_query = text_query
        return Session.query(self).filter(self.name.contains(text_query.lower()))

    def add_resource(self, url, format=u'', description=u'', hash=u''):
        import resource
        self.resources.append(resource.PackageResource(
            package_id=self.id,
            url=url,
            format=format,
            description=description,
            hash=hash))

    def add_tag_by_name(self, tagname, autoflush=True):
        if not tagname:
            return
        tag = Tag.by_name(tagname, autoflush=autoflush)
        if not tag:
            tag = Tag(name=tagname)
        if not tag in self.tags:
            self.tags.append(tag)

    @property
    def tags_ordered(self):
        ourcmp = lambda tag1, tag2: cmp(tag1.name, tag2.name)
        return sorted(self.tags, cmp=ourcmp)

    def isopen(self):
        if self.license and self.license.isopen():
            return True
        return False

    def get_average_rating(self):
        total = 0
        for rating in self.ratings:
            total += rating.rating
        if total == 0:
            return None
        else:
            return total / len(self.ratings)

    def as_dict(self):
        _dict = DomainObject.as_dict(self)
        _dict['tags'] = [tag.name for tag in self.tags]
        _dict['groups'] = [group.name for group in self.groups]
        if self.license:
            _dict['license'] = self.license.name
        else:
            _dict['license'] = ''
        _dict['extras'] = dict([(extra.key, extra.value) for key, extra in self._extras.items()])
        _dict['ratings_average'] = self.get_average_rating()
        _dict['ratings_count'] = len(self.ratings)
        _dict['resources'] = [{'url':res.url, 'format':res.format, 'description':res.description} for res in self.resources]
        _dict['download_url'] = self.resources[0].url if self.resources else ''
        ckan_host = config.get('ckan_host', None)
        if ckan_host:
            _dict['ckan_url'] = 'http://%s/package/%s' % (ckan_host, self.name)
        return _dict
        

class Tag(DomainObject):
    def __init__(self, name=''):
        self.name = name

    # not versioned so same as purge
    def delete(self):
        self.purge()

    @classmethod
    def search_by_name(self, text_query):
        text_query = text_query.strip().lower()
        return Session.query(self).filter(self.name.contains(text_query))

    @property
    def packages_ordered(self):
        ourcmp = lambda pkg1, pkg2: cmp(pkg1.name, pkg2.name)
        return sorted(self.packages, cmp=ourcmp)

    def __repr__(self):
        return '<Tag %s>' % self.name


class PackageTag(vdm.sqlalchemy.RevisionedObjectMixin,
        vdm.sqlalchemy.StatefulObjectMixin,
        DomainObject):
    def __init__(self, package=None, tag=None, state=None, **kwargs):
        self.package = package
        self.tag = tag
        self.state = state
        for k,v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return '<PackageTag %s %s>' % (self.package, self.tag)

class System(DomainObject):
    def __str__(self):
        return 'System'
    def purge(self):
        pass

# VDM-specific domain objects
State = vdm.sqlalchemy.State
State.all = [ State.ACTIVE, State.DELETED ]
Revision = vdm.sqlalchemy.make_Revision(mapper, revision_table)

mapper(License, license_table,
    order_by=license_table.c.id)

mapper(Package, package_table, properties={
    'license':relation(License),
    # delete-orphan on cascade does NOT work!
    # Why? Answer: because of way SQLAlchemy/our code works there are points
    # where PackageTag object is created *and* flushed but does not yet have
    # the package_id set (this cause us other problems ...). Some time later a
    # second commit happens in which the package_id is correctly set.
    # However after first commit PackageTag does not have Package and
    # delete-orphan kicks in to remove it!
    'package_tags':relation(PackageTag, backref='package',
        cascade='all, delete', #, delete-orphan',
        ),
    'package_search':relation(full_search.PackageSearch,
        cascade='all, delete', #, delete-orphan',
        ),
    },
    order_by=package_table.c.name,
    extension = [vdm.sqlalchemy.Revisioner(package_revision_table),
                 full_search.SearchVectorTrigger()]
    )

mapper(Tag, tag_table, properties={
    'package_tags':relation(PackageTag, backref='tag',
        cascade='all, delete, delete-orphan',
        )
    },
    order_by=tag_table.c.name,
    )

mapper(PackageTag, package_tag_table, properties={
    },
    order_by=package_tag_table.c.id,
    extension = [vdm.sqlalchemy.Revisioner(package_tag_revision_table),
                 full_search.SearchVectorTrigger()],
    )

vdm.sqlalchemy.modify_base_object_mapper(Package, Revision, State)
vdm.sqlalchemy.modify_base_object_mapper(PackageTag, Revision, State)
PackageRevision = vdm.sqlalchemy.create_object_version(mapper, Package,
        package_revision_table)
PackageTagRevision = vdm.sqlalchemy.create_object_version(mapper, PackageTag,
        package_tag_revision_table)

from vdm.sqlalchemy.base import add_stateful_versioned_m2m 
vdm.sqlalchemy.add_stateful_versioned_m2m(Package, PackageTag, 'tags', 'tag',
        'package_tags')
vdm.sqlalchemy.add_stateful_versioned_m2m_on_version(PackageRevision, 'tags')
vdm.sqlalchemy.add_stateful_versioned_m2m(Tag, PackageTag, 'packages', 'package',
        'package_tags')


