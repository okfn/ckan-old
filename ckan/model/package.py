import datetime
from time import mktime, gmtime

from sqlalchemy.sql import select, and_, union, expression
from sqlalchemy.orm import eagerload_all
from pylons import config
from meta import *
import vdm.sqlalchemy

from types import make_uuid
from core import *
from license import License, LicenseRegister
from domain_object import DomainObject

__all__ = ['Package', 'package_table', 'package_revision_table',
           'PACKAGE_NAME_MAX_LENGTH', 'PACKAGE_VERSION_MAX_LENGTH']

PACKAGE_NAME_MAX_LENGTH = 100
PACKAGE_VERSION_MAX_LENGTH = 100
## Our Domain Object Tables
package_table = Table('package', metadata,
        Column('id', types.UnicodeText, primary_key=True, default=make_uuid),
        Column('name', types.Unicode(PACKAGE_NAME_MAX_LENGTH),
               nullable=False, unique=True),
        Column('title', types.UnicodeText),
        Column('version', types.Unicode(PACKAGE_VERSION_MAX_LENGTH)),
        Column('url', types.UnicodeText),
        Column('author', types.UnicodeText),
        Column('author_email', types.UnicodeText),
        Column('maintainer', types.UnicodeText),
        Column('maintainer_email', types.UnicodeText),                      
        Column('notes', types.UnicodeText),
        Column('license_id', types.UnicodeText),
)


vdm.sqlalchemy.make_table_stateful(package_table)
package_revision_table = vdm.sqlalchemy.make_revisioned_table(package_table)

## -------------------
## Mapped classes


class Package(vdm.sqlalchemy.RevisionedObjectMixin,
        vdm.sqlalchemy.StatefulObjectMixin,
        DomainObject):
    
    text_search_fields = ['name', 'title']

    @classmethod
    def search_by_name(self, text_query):
        text_query = text_query
        return Session.query(self).filter(self.name.contains(text_query.lower()))

    @classmethod
    def get(cls, reference):
        '''Returns a package object referenced by its id or name.'''
        query = Session.query(cls).filter(cls.id==reference)
        query = query.options(eagerload_all('package_tags.tag'))
        query = query.options(eagerload_all('package_resources_all'))
        pkg = query.first()
        if pkg == None:
            pkg = cls.by_name(reference)            
        return pkg
    # Todo: Make sure package names can't be changed to look like package IDs?

    def update_resources(self, res_dicts, autoflush=True):
        '''Change this package\'s resources.
        @param res_dicts - ordered list of dicts, each detailing a resource
        The resource dictionaries contain 'url', 'format' etc. Optionally they
        can also provide the 'id' of the PackageResource, to help matching
        res_dicts to existing PackageResources. Otherwise, it searches
        for an exactly matching PackageResource.
        The caller is responsible for creating a revision and committing.'''
        import resource
        assert isinstance(res_dicts, (list, tuple))
        # Map the incoming res_dicts (by index) to existing resources
        index_to_res = {}
        # Match up the res_dicts by id
        for i, res_dict in enumerate(res_dicts):
            assert isinstance(res_dict, dict)
            id = res_dict.get('id')
            if id:
                res = Session.query(resource.PackageResource).autoflush(autoflush).get(id)
                if res:
                    index_to_res[i] = res
        # Edit resources and create the new ones
        new_res_list = []
        for i, res_dict in enumerate(res_dicts):
            if i in index_to_res:
                res = index_to_res[i]
                for col, value in res_dict.items():
                    setattr(res, col, value)
            else:
                # ignore particular keys that disrupt creation of new resource
                for key in ('id', 'position'):
                    if res_dict.has_key(key):
                        del res_dict[key]
                res = resource.PackageResource(**res_dict)
            new_res_list.append(res)
        self.resources = new_res_list

    def add_resource(self, url, format=u'', description=u'', hash=u''):
        import resource
        self.resources.append(resource.PackageResource(
            package_id=self.id,
            url=url,
            format=format,
            description=description,
            hash=hash))

    def add_tag_by_name(self, tagname, autoflush=True):
        from tag import Tag
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

    def as_dict(self, ref_package_by='name', ref_group_by='name'):
        _dict = DomainObject.as_dict(self)
        # Set 'license' in _dict to cater for old clients.
        # Todo: Remove from Version 2?
        _dict['license'] = self.license.title if self.license else _dict.get('license_id', '')
        tags = [tag.name for tag in self.tags]
        tags.sort() # so it is determinable
        _dict['tags'] = tags
        groups = [getattr(group, ref_group_by) for group in self.groups]
        groups.sort()
        _dict['groups'] = groups
        _dict['extras'] = dict([(key, value) for key, value in self.extras.items()])
        _dict['ratings_average'] = self.get_average_rating()
        _dict['ratings_count'] = len(self.ratings)
        _dict['resources'] = [res.as_dict(core_columns_only=False) \
                              for res in self.resources]
        site_url = config.get('ckan.site_url', None)
        if site_url:
            _dict['ckan_url'] = '%s/package/%s' % (site_url, self.name)
        _dict['relationships'] = [rel.as_dict(self, ref_package_by=ref_package_by) for rel in self.get_relationships()]
        _dict['metadata_modified'] = self.metadata_modified.isoformat() \
            if self.metadata_modified else None
        _dict['metadata_created'] = self.metadata_created.isoformat() \
            if self.metadata_created else None
        return _dict

    def add_relationship(self, type_, related_package, comment=u''):
        '''Creates a new relationship between this package and a
        related_package. It leaves the caller to commit the change.'''
        import package_relationship
        from ckan import model
        if type_ in package_relationship.PackageRelationship.get_forward_types():
            subject = self
            object_ = related_package
        elif type_ in package_relationship.PackageRelationship.get_reverse_types():
            type_ = package_relationship.PackageRelationship.reverse_to_forward_type(type_)
            assert type_
            subject = related_package
            object_ = self
        else:
            raise NotImplementedError, 'Package relationship type: %r' % type_

        rels = self.get_relationships(with_package=related_package,
                                      type=type_, active=False, direction="forward")
        if rels:
            rel = rels[0]
            if comment:
                rel.comment=comment
            if rel.state == model.State.DELETED:
                rel.undelete()
        else:
            rel = package_relationship.PackageRelationship(
                subject=subject,
                object=object_,
                type=type_,
                comment=comment)
        Session.add(rel)
        return rel

    def get_relationships(self, with_package=None, type=None, active=True,
                          direction='both'):
        '''Returns relationships this package has.
        Keeps stored type/ordering (not from pov of self).'''
        assert direction in ('both', 'forward', 'reverse')
        if with_package:
            assert isinstance(with_package, Package)
        from package_relationship import PackageRelationship
        forward_filters = [PackageRelationship.subject==self]
        reverse_filters = [PackageRelationship.object==self]
        if with_package:
            forward_filters.append(PackageRelationship.object==with_package)
            reverse_filters.append(PackageRelationship.subject==with_package)
        if active:
            forward_filters.append(PackageRelationship.state==State.ACTIVE)
            reverse_filters.append(PackageRelationship.state==State.ACTIVE)
        if type:
            forward_filters.append(PackageRelationship.type==type)
            reverse_type = PackageRelationship.reverse_type(type)
            reverse_filters.append(PackageRelationship.type==reverse_type)
        q = Session.query(PackageRelationship)
        if direction == 'both':
            q = q.filter(or_(
            and_(*forward_filters),
            and_(*reverse_filters),
            ))
        elif direction == 'forward':
            q = q.filter(and_(*forward_filters))
        elif direction == 'reverse':
            q = q.filter(and_(*reverse_filters))
        return q.all()

    def get_relationships_with(self, other_package, type=None, active=True):
        return self.get_relationships(with_package=other_package,
                                      type=type,
                                      active=active)

    def get_relationships_printable(self):
        '''Returns a list of tuples describing related packages, including
        non-direct relationships (such as siblings).
        @return: e.g. [(annakarenina, u"is a parent"), ...]
        '''
        from package_relationship import PackageRelationship
        rel_list = []
        for rel in self.get_relationships():
            if rel.subject == self:
                type_printable = PackageRelationship.make_type_printable(rel.type)
                rel_list.append((rel.object, type_printable, rel.comment))
            else:
                type_printable = PackageRelationship.make_type_printable(\
                    PackageRelationship.forward_to_reverse_type(
                        rel.type)
                    )
                rel_list.append((rel.subject, type_printable, rel.comment))
        # sibling types
        # e.g. 'gary' is a child of 'mum', looking for 'bert' is a child of 'mum'
        # i.e. for each 'child_of' type relationship ...
        for rel_as_subject in self.get_relationships(direction='forward'):
            if rel_as_subject.state != State.ACTIVE:
                continue
            # ... parent is the object
            parent_pkg = rel_as_subject.object
            # Now look for the parent's other relationships as object ...
            for parent_rel_as_object in parent_pkg.get_relationships(direction='reverse'):
                if parent_rel_as_object.state != State.ACTIVE:
                    continue
                # and check children
                child_pkg = parent_rel_as_object.subject
                if child_pkg != self and \
                       parent_rel_as_object.type == rel_as_subject.type:
                    type_printable = PackageRelationship.inferred_types_printable['sibling']
                    rel_list.append((child_pkg, type_printable, None))
        return sorted(list(set(rel_list)))
    #
    ## Licenses are currently integrated into the domain model here.   
 
    @classmethod
    def get_license_register(self):
        if not hasattr(self, '_license_register'):
            self._license_register = LicenseRegister()
        return self._license_register

    @classmethod
    def get_license_options(self):
        register = self.get_license_register()
        return [(l.title, l.id) for l in register.values()]

    def get_license(self):
        license = None
        if self.license_id:
            try:
                license = self.get_license_register()[self.license_id]
            except Exception, inst:
                # Todo: Log a warning.
                pass
        return license

    def set_license(self, license):
        if type(license) == License:
            self.license_id = license.id
        elif type(license) == dict:
            self.license_id = license['id']
        else:
            msg = "Value not a license object or entity: %s" % repr(license)
            raise Exception, msg

    license = property(get_license, set_license)

    @property
    def all_related_revisions(self):
        '''Returns chronological list of all object revisions related to
        this package. Includes PackageRevisions, PackageTagRevisions,
        PackageExtraRevisions and PackageResourceRevisions.
        @return List of tuples (revision, [list of object revisions of this
                                           revision])
                Ordered by most recent first.
        '''
        results = {} # revision:[PackageRevision1, PackageTagRevision1, etc.]
        for pkg_rev in self.all_revisions:
            if not results.has_key(pkg_rev.revision):
                results[pkg_rev.revision] = []
            results[pkg_rev.revision].append(pkg_rev)
        for class_ in get_revisioned_classes_related_to_package():
            rev_class = class_.__revision_class__
            obj_revisions = Session.query(rev_class).filter_by(package_id=self.id).all()
            for obj_rev in obj_revisions:
                if not results.has_key(obj_rev.revision):
                    results[obj_rev.revision] = []
                results[obj_rev.revision].append(obj_rev)
        result_list = results.items()
        ourcmp = lambda rev_tuple1, rev_tuple2: \
                 cmp(rev_tuple2[0].timestamp, rev_tuple1[0].timestamp)
        return sorted(result_list, cmp=ourcmp)

    @property
    def latest_related_revision(self):
        '''Returns the latest revision for the package and its related
        objects.'''
        return self.all_related_revisions[0][0]
        
    def diff(self, to_revision=None, from_revision=None):
        '''Overrides the diff in vdm, so that related obj revisions are
        diffed as well as PackageRevisions'''
        import package_extra, resource
        results = {} # field_name:diffs
        results.update(super(Package, self).diff(to_revision, from_revision))
        # Iterate over PackageTag, PackageExtra, PackageResources etc.
        for obj_class in get_revisioned_classes_related_to_package():
            obj_rev_class = obj_class.__revision_class__
            # Query for object revisions related to this package            
            obj_rev_query = Session.query(obj_rev_class).\
                            filter_by(package_id=self.id).\
                            join('revision').\
                            order_by(Revision.timestamp.desc())
            # Columns to include in the diff
            cols_to_diff = obj_class.revisioned_fields()
            cols_to_diff.remove('id')
            cols_to_diff.remove('package_id')
            # Particular object types are better known by an invariant field
            if obj_class.__name__ == 'PackageTag':
                cols_to_diff.remove('tag_id')
            elif obj_class.__name__ == 'PackageExtra':
                cols_to_diff.remove('key')
            # Iterate over each object ID
            # e.g. for PackageTag, iterate over Tag objects
            related_obj_ids = set([related_obj.id for related_obj in obj_rev_query.all()])
            for related_obj_id in related_obj_ids:
                q = obj_rev_query.filter(obj_rev_class.id==related_obj_id)
                to_obj_rev, from_obj_rev = super(Package, self).\
                    get_obj_revisions_to_diff(
                    q, to_revision, from_revision)
                for col in cols_to_diff:
                    values = [getattr(obj_rev, col) if obj_rev else '' for obj_rev in (from_obj_rev, to_obj_rev)]
                    value_diff = self._differ(*values)
                    if value_diff:
                        if obj_class.__name__ == 'PackageTag':
                            display_id = to_obj_rev.tag.name
                        elif obj_class.__name__ == 'PackageExtra':
                            display_id = to_obj_rev.key
                        else:
                            display_id = related_obj_id[:4]
                        key = '%s-%s-%s' % (obj_class.__name__, display_id, col)
                        results[key] = value_diff
        return results

    @staticmethod
    def last_modified(*av):
        """
        Return most recent timestamp for a package revision, with optionally
        extra where clause.
        """
        from ckan import model
        where = []
        for arg in av:
            if isinstance(arg, expression.ClauseElement) or isinstance(arg, basestring):
                where.append(arg)
        where_clauses = [
            and_(model.package_table.c.revision_id == model.revision_table.c.id, *where),
            and_(model.package_extra_table.c.package_id == model.package_table.c.id,
                 model.package_extra_table.c.revision_id == model.revision_table.c.id, *where),
            and_(model.package_relationship_table.c.subject_package_id == model.package_table.c.id,
                 model.package_relationship_table.c.revision_id == model.revision_table.c.id, *where),
            and_(model.package_relationship_table.c.object_package_id == model.package_table.c.id,
                 model.package_relationship_table.c.revision_id == model.revision_table.c.id, *where),
            and_(model.package_resource_table.c.package_id == model.package_table.c.id,
                 model.package_resource_table.c.revision_id == model.revision_table.c.id, *where),
            and_(model.package_tag_table.c.package_id == model.package_table.c.id,
                 model.package_tag_table.c.revision_id == model.revision_table.c.id, *where)
            ]
        query = union(*[select([model.revision_table.c.timestamp], x) for x in where_clauses]
                      ).order_by("timestamp DESC").limit(1)
        conn = model.meta.engine.connect()
        result = conn.execute(query).fetchone()
        if result:
            timestamp = result[0].utctimetuple()
            usecs = float(result[0].microsecond) / 1e6
        else:
            timestamp, usecs = gmtime(), 0
        return mktime(timestamp) + usecs

    @property
    def metadata_modified(self):
        import ckan.model as model
        epochtime = self.last_modified(model.package_table.c.id==self.id)
        return datetime.datetime.fromtimestamp(epochtime)
    
    @property
    def metadata_created(self):
        import ckan.model as model
        q = model.Session.query(model.Revision).select_from(
            model.revision_table.join(
                model.package_revision_table,
                and_(model.revision_table.c.id==model.package_revision_table.c.revision_id))
            ).order_by(model.Revision.timestamp.asc())
        ts = q.first()
        if ts is not None:
            return ts.timestamp

    @staticmethod
    def get_fields(core_only=False, fields_to_ignore=None):
        '''Returns a list of the properties of a package.
        @param core_only - limit it to fields actually in the package table and
                           not those on related objects, such as tags & extras.
        @param fields_to_ignore - a list of names of fields to not return if
                           present.
        '''
        # ['id', 'name', 'title', 'version', 'url', 'author', 'author_email', 'maintainer', 'maintainer_email', 'notes', 'license_id', 'state']
        fields = Package.revisioned_fields()
        if not core_only:
            fields += ['resources', 'tags', 'groups', 'extras', 'relationships']

        if fields_to_ignore:
            for field in fields_to_ignore:
                fields.remove(field)

        return fields

def get_revisioned_classes_related_to_package():
    import resource
    import package_extra
    import tag
    return [tag.PackageTag, resource.PackageResource,
            package_extra.PackageExtra]

