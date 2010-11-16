import meta
from domain_object import DomainObjectOperation
from core import *
from package import *
from tag import *
from package_mapping import *
from user import user_table, User
from authorization_group import * 
from group import *
from group_extra import *
from search_index import *
from authz import *
from package_extra import *
from resource import *
from rating import *
from package_relationship import *
from changeset import Changeset, Change, Changemask
from harvesting import HarvestSource, HarvestingJob, HarvestedDocument

import ckan.migration

# set up in init_model after metadata is bound
version_table = None

def init_model(engine):
    '''Call me before using any of the tables or classes in the model'''
    meta.Session.configure(bind=engine)
    meta.engine = engine
    meta.metadata.bind = engine
    # sqlalchemy migrate version table
    import sqlalchemy.exceptions
    try:
        version_table = Table('migrate_version', metadata, autoload=True)
    except sqlalchemy.exceptions.NoSuchTableError:
        pass



class Repository(vdm.sqlalchemy.Repository):
    migrate_repository = ckan.migration.__path__[0]

    def init_db(self):
        super(Repository, self).init_db()
        # assume if this exists everything else does too
        if not User.by_name(PSEUDO_USER__VISITOR):
            visitor = User(name=PSEUDO_USER__VISITOR)
            logged_in = User(name=PSEUDO_USER__LOGGED_IN)
            Session.add(visitor)
            Session.add(logged_in)
        validate_authorization_setup()
        if Session.query(Revision).count() == 0:
            rev = Revision()
            rev.author = 'system'
            rev.message = u'Initialising the Repository'
            Session.add(rev)
        self.commit_and_remove()   

    def create_db(self):
        self.metadata.create_all(bind=self.metadata.bind)    
        # creation this way worked fine for normal use but failed on test with
        # OperationalError: (OperationalError) no such table: xxx
        # 2009-09-11 interesting all the tests will work if you run them after
        # doing paster db clean && paster db upgrade !
        # self.upgrade_db()
        self.setup_migration_version_control(self.latest_migration_version())
        self.create_indexes()

    def latest_migration_version(self):
        import migrate.versioning.api as mig
        version = mig.version(self.migrate_repository)
        return version

    def setup_migration_version_control(self, version=None):
        import migrate.versioning.exceptions
        import migrate.versioning.api as mig
        # set up db version control (if not already)
        try:
            mig.version_control(self.metadata.bind.url,
                    self.migrate_repository, version)
        except migrate.versioning.exceptions.DatabaseAlreadyControlledError:
            pass
    
    def create_indexes(self):
        import os
        from migrate.versioning.script import SqlScript
        from sqlalchemy.exceptions import ProgrammingError
        try:
            path = os.path.join(self.migrate_repository, 'versions', '021_postgres_upgrade.sql')
            script = SqlScript(path) 
            script.run(meta.engine, step=None)
        except ProgrammingError, e:
            if not 'already exists' in repr(e):
                raise
    
    def upgrade_db(self, version=None):
        '''Upgrade db using sqlalchemy migrations.

        @param version: version to upgrade to (if None upgrade to latest)
        '''
        import migrate.versioning.api as mig
        self.setup_migration_version_control()
        mig.upgrade(self.metadata.bind.url, self.migrate_repository, version=version)
        validate_authorization_setup()



repo = Repository(metadata, Session,
        versioned_objects=[Package, PackageTag, PackageResource, PackageExtra, PackageGroup, Group]
        )


# Fix up Revision with project-specific attributes
def _get_packages(self):
    changes = repo.list_changes(self)
    pkgs = set()
    for pkg_rev in changes.pop(Package):
        pkgs.add(pkg_rev.continuity)
    for non_pkg_rev_list in changes.values():
        for non_pkg_rev in non_pkg_rev_list:
            if hasattr(non_pkg_rev.continuity, 'package'):
                pkgs.add(non_pkg_rev.continuity.package)
    return list(pkgs)

def _get_groups(self):
    changes = repo.list_changes(self)
    groups = set()
    for group_rev in changes.pop(Group):
        groups.add(group_rev.continuity)
    for non_group_rev_list in changes.values():
        for non_group_rev in non_group_rev_list:
            if hasattr(non_group_rev.continuity, 'group'):
                groups.add(non_group_rev.continuity.group)
    return list(groups)

# could set this up directly on the mapper?
def _get_revision_user(self):
    username = unicode(self.author)
    user = Session.query(User).filter_by(name=username).first()
    return user

Revision.packages = property(_get_packages)
Revision.groups = property(_get_groups)
Revision.user = property(_get_revision_user)

def strptimestamp(s):
    import datetime, re
    return datetime.datetime(*map(int, re.split('[^\d]', s)))

def strftimestamp(t):
    return t.isoformat()

