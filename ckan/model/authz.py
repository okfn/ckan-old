'''For an overview of CKAN authorization system and model see
doc/authorization.rst.

'''
from meta import *
from core import *
from package import *
from group import Group
from types import make_uuid
from user import User
from core import System
from authorization_group import AuthorizationGroup, authorization_group_table

PSEUDO_USER__LOGGED_IN = u'logged_in'
PSEUDO_USER__VISITOR = u'visitor'

class NotRealUserException(Exception):
    pass

## ======================================
## Action and Role Enums

class Enum(object):
    @classmethod
    def is_valid(self, val):
        return val in self.get_all()

    @classmethod
    def get_all(self):
        if not hasattr(self, '_all_items'):
            vals = []
            for key, val in self.__dict__.items():
                if not key.startswith('_'):
                    vals.append(val)
            self._all_items = vals
        return self._all_items

class Action(Enum):
    EDIT = u'edit'
    CHANGE_STATE = u'change-state'
    READ = u'read'
    PURGE = u'purge'
    EDIT_PERMISSIONS = u'edit-permissions'
    PACKAGE_CREATE = u'create-package'
    GROUP_CREATE = u'create-group'
    AUTHZ_GROUP_CREATE = u'create-authorization-group'

class Role(Enum):
    ADMIN = u'admin'
    EDITOR = u'editor'
    READER = u'reader'

default_role_actions = [
    (Role.EDITOR, Action.EDIT),
    (Role.EDITOR, Action.PACKAGE_CREATE),
    (Role.EDITOR, Action.GROUP_CREATE),
    (Role.EDITOR, Action.AUTHZ_GROUP_CREATE),
    (Role.EDITOR, Action.READ),        
    (Role.READER, Action.PACKAGE_CREATE),
    #(Role.READER, Action.GROUP_CREATE),
    (Role.READER, Action.READ),
    ]


## ======================================
## Table Definitions

role_action_table = Table('role_action', metadata,
           Column('id', UnicodeText, primary_key=True, default=make_uuid),
           Column('role', UnicodeText),
           Column('context', UnicodeText, nullable=False),
           Column('action', UnicodeText),
           )

user_object_role_table = Table('user_object_role', metadata,
           Column('id', UnicodeText, primary_key=True, default=make_uuid),
           Column('user_id', UnicodeText, ForeignKey('user.id'), nullable=True),
           Column('authorized_group_id', UnicodeText, ForeignKey('authorization_group.id'), nullable=True),
           Column('context', UnicodeText, nullable=False),
           Column('role', UnicodeText)
           )

package_role_table = Table('package_role', metadata,
           Column('user_object_role_id', UnicodeText, ForeignKey('user_object_role.id'), primary_key=True),
           Column('package_id', UnicodeText, ForeignKey('package.id')),
           )

group_role_table = Table('group_role', metadata,
           Column('user_object_role_id', UnicodeText, ForeignKey('user_object_role.id'), primary_key=True),
           Column('group_id', UnicodeText, ForeignKey('group.id')),
           )
           
authorization_group_role_table = Table('authorization_group_role', metadata,
           Column('user_object_role_id', UnicodeText, ForeignKey('user_object_role.id'), primary_key=True),
           Column('authorization_group_id', UnicodeText, ForeignKey('authorization_group.id')),
           )

system_role_table = Table('system_role', metadata,
           Column('user_object_role_id', UnicodeText, ForeignKey('user_object_role.id'), primary_key=True),
           )


class RoleAction(DomainObject):
    def __repr__(self):
        return '<%s role="%s" action="%s" context="%s">' % \
               (self.__class__.__name__, self.role, self.action, self.context)
    

# dictionary mapping protected objects (e.g. Package) to related ObjectRole
protected_objects = {}

class UserObjectRole(DomainObject):
    name = None
    protected_object = None

    def __repr__(self):
        return '<%s user="%s" role="%s" context="%s">' % \
               (self.__class__.__name__, self.user.name, self.role, self.context)

    @classmethod
    def get_object_role_class(self, domain_obj):
        protected_object = protected_objects.get(domain_obj.__class__, None)
        if protected_object is None:
            # TODO: make into an authz exception
            msg = '%s is not a protected object, i.e. a subject of authorization' % domain_obj
            raise Exception(msg)
        else:
            return protected_object

    @classmethod
    def user_has_role(cls, user, role, domain_obj):
        assert isinstance(user, User), user
        assert Role.is_valid(role), role
        q = cls._user_query(user, role, domain_obj)
        return q.count() == 1
        
    @classmethod
    def authorization_group_has_role(cls, authorized_group, role, domain_obj):
        assert isinstance(authorized_group, AuthorizationGroup), authorized_group
        assert Role.is_valid(role), role
        q = cls._authorized_group_query(authorized_group, role, domain_obj)
        return q.count() == 1
        
    @classmethod
    def _user_query(cls, user, role, domain_obj):
        q = Session.query(cls).filter_by(role=role)
        # some protected objects are not "contextual"
        if cls.name is not None:
            # e.g. filter_by(package=domain_obj)
            q = q.filter_by(**dict({cls.name: domain_obj}))
        q = q.filter_by(user=user)
        return q
    
    @classmethod
    def _authorized_group_query(cls, authorized_group, role, domain_obj):
        q = Session.query(cls).filter_by(role=role)
        # some protected objects are not "contextual"
        if cls.name is not None:
            # e.g. filter_by(package=domain_obj)
            q = q.filter_by(**dict({cls.name: domain_obj}))
        q = q.filter_by(authorized_group=authorized_group)
        return q

    @classmethod
    def add_user_to_role(cls, user, role, domain_obj):
        '''role assignment already exists
        NB: leaves caller to commit change'''
        if cls.user_has_role(user, role, domain_obj):
            return
        objectrole = cls(role=role, user=user)
        if cls.name is not None:
            setattr(objectrole, cls.name, domain_obj)
        Session.add(objectrole)
        
    @classmethod
    def add_authorization_group_to_role(cls, authorization_group, role, domain_obj):
        # role assignment already exists
        if cls.authorization_group_has_role(authorization_group, role, domain_obj):
            return
        objectrole = cls(role=role, authorized_group=authorization_group)
        if cls.name is not None:
            setattr(objectrole, cls.name, domain_obj)
        Session.add(objectrole)

    @classmethod
    def remove_user_from_role(cls, user, role, domain_obj):
        q = cls._user_query(user, role, domain_obj)
        uo_role = q.one()
        Session.delete(uo_role)
        Session.commit()
        Session.remove()

    @classmethod
    def remove_authorization_group_from_role(cls, authorization_group, role, domain_obj):
        q = self._authorized_group_query(authorization_group, role, domain_obj)
        ago_role = q.one()
        Session.delete(agu_role)
        Session.commit()
        Session.remove()

class PackageRole(UserObjectRole):
    protected_object = Package
    name = 'package'
protected_objects[PackageRole.protected_object] = PackageRole

class GroupRole(UserObjectRole):
    protected_object = Group
    name = 'group'
protected_objects[GroupRole.protected_object] = GroupRole

class AuthorizationGroupRole(UserObjectRole):
    protected_object = AuthorizationGroup
    name = 'authorization_group'
protected_objects[AuthorizationGroupRole.protected_object] = AuthorizationGroupRole

class SystemRole(UserObjectRole):
    protected_object = System
    name = None
protected_objects[SystemRole.protected_object] = SystemRole



## ======================================
## Helpers


def user_has_role(user, role, domain_obj):
    objectrole = UserObjectRole.get_object_role_class(domain_obj)
    return objectrole.user_has_role(user, role, domain_obj)

def add_user_to_role(user, role, domain_obj):
    objectrole = UserObjectRole.get_object_role_class(domain_obj)
    objectrole.add_user_to_role(user, role, domain_obj)

def remove_user_from_role(user, role, domain_obj):
    objectrole = UserObjectRole.get_object_role_class(domain_obj)
    objectrole.remove_user_from_role(user, role, domain_obj)

    
def authorization_group_has_role(authorization_group, role, domain_obj):
    objectrole = UserObjectRole.get_object_role_class(domain_obj)
    return objectrole.authorization_group_has_role(authorization_group, role, domain_obj)
        
def add_authorization_group_to_role(authorization_group, role, domain_obj):
    objectrole = UserObjectRole.get_object_role_class(domain_obj)
    objectrole.add_authorization_group_to_role(authorization_group, role, domain_obj)

def remove_authorization_group_from_role(authorization_group, role, domain_obj):
    objectrole = UserObjectRole.get_object_role_class(domain_obj)
    objectrole.remove_authorization_group_from_role(authorization_group, role, domain_obj)
    
def init_authz_configuration_data():
    setup_default_user_roles(System())
    Session.commit()
    Session.remove()
    
def init_authz_const_data():
    # since some of the authz config mgmt is taking place in DB, this should 
    # be validated on launch. it is a bit like a lazy migration, but seems 
    # sensible to make sure authz is always correct.
    # setup all role-actions
    # context is blank as not currently used
    # Note that Role.ADMIN can already do anything - hardcoded in.
    for role, action in default_role_actions:
        ra = Session.query(RoleAction).filter_by(role=role, action=action).first()
        if ra is not None: continue
        ra = RoleAction(role=role, context=u'', action=action)
        Session.add(ra)
    Session.commit()
    Session.remove()

## TODO: this should be in ckan/authz.py
def setup_user_roles(domain_object, visitor_roles, logged_in_roles, admins=[]):
    '''NB: leaves caller to commit change'''
    assert type(admins) == type([])
    admin_roles = [Role.ADMIN]
    visitor = User.by_name(PSEUDO_USER__VISITOR)
    assert visitor
    for role in visitor_roles:
        add_user_to_role(visitor, role, domain_object)
    logged_in = User.by_name(PSEUDO_USER__LOGGED_IN)
    assert logged_in
    for role in logged_in_roles:
        add_user_to_role(logged_in, role, domain_object)
    for admin in admins:
        # not sure if admin would reasonably by None
        if admin is not None:
            assert isinstance(admin, User), admin
            if admin.name in (PSEUDO_USER__LOGGED_IN, PSEUDO_USER__VISITOR):
                raise NotRealUserException('Invalid user for domain object admin %r' % admin.name)
            for role in admin_roles:
                add_user_to_role(admin, role, domain_object)

def give_all_packages_default_user_roles():
    # if this command gives an exception, you probably
    # forgot to do 'paster db init'
    pkgs = Session.query(Package).all()

    for pkg in pkgs:
        print pkg
        # weird - should already be in session but complains w/o this
        Session.add(pkg)
        if len(pkg.roles) > 0:
            print 'Skipping (already has roles): %s' % pkg.name
            continue
        # work out the authors and make them admins
        admins = []
        revs = pkg.all_revisions
        for rev in revs:
            if rev.revision.author:
                # rev author is not Unicode!!
                user = User.by_name(unicode(rev.revision.author))
                if user:
                    admins.append(user)
        # remove duplicates
        admins = list(set(admins))
        # gives default permissions
        print 'Creating default user for for %s with admins %s' % (pkg.name, admins)
        setup_default_user_roles(pkg, admins)

def setup_default_user_roles(domain_object, admins=[]):
    ''' sets up roles for visitor, logged-in user and any admins provided
    @param admins - a list of User objects
    NB: leaves caller to commit change.
    '''
    assert isinstance(domain_object, (Package, Group, System, AuthorizationGroup)), domain_object
    assert isinstance(admins, list)
    if type(domain_object) == Package:
        visitor_roles = [Role.EDITOR]
        logged_in_roles = [Role.EDITOR]
    elif type(domain_object) == Group:
        visitor_roles = [Role.READER]
        logged_in_roles = [Role.READER]
    elif type(domain_object) == System:
        visitor_roles = [Role.READER]
        logged_in_roles = [Role.EDITOR]
    elif type(domain_object) == AuthorizationGroup:
        visitor_roles = [Role.READER]
        logged_in_roles = [Role.READER]
    setup_user_roles(domain_object, visitor_roles, logged_in_roles, admins)

def clear_user_roles(domain_object):
    assert isinstance(domain_object, DomainObject)
    if isinstance(domain_object, Package):
        q = Session.query(PackageRole).filter_by(package=domain_object)
    elif isinstance(domain_object, Group):
        q = Session.query(GroupRole).filter_by(group=domain_object)
    else:
        raise NotImplementedError()
    user_roles = q.all()
    for user_role in user_roles:
        Session.delete(user_role)


## ======================================
## Mappers

mapper(RoleAction, role_action_table)
       
mapper(UserObjectRole, user_object_role_table,
    polymorphic_on=user_object_role_table.c.context,
    polymorphic_identity=u'user_object',
    properties={
        'user': orm.relation(User,
            backref=orm.backref('roles',
                cascade='all, delete, delete-orphan'
            )
        ),
        'authorized_group': orm.relation(AuthorizationGroup,
            backref=orm.backref('authorized_roles',
                cascade='all, delete, delete-orphan'
            )
        )
    },
    order_by=[user_object_role_table.c.id],
)

mapper(PackageRole, package_role_table, inherits=UserObjectRole,
    polymorphic_identity=unicode(Package.__name__),
    properties={
        'package': orm.relation(Package,
             backref=orm.backref('roles',
             cascade='all, delete, delete-orphan'
             )
        ),
    },
    order_by=[package_role_table.c.user_object_role_id],
)

mapper(GroupRole, group_role_table, inherits=UserObjectRole,
       polymorphic_identity=unicode(Group.__name__),
       properties={
            'group': orm.relation(Group,
                 backref=orm.backref('roles',
                 cascade='all, delete, delete-orphan'
                 ),
            )
    },
    order_by=[group_role_table.c.user_object_role_id],
)

mapper(AuthorizationGroupRole, authorization_group_role_table, inherits=UserObjectRole,
       polymorphic_identity=unicode(AuthorizationGroup.__name__),
       properties={
            'authorization_group': orm.relation(AuthorizationGroup,
                 backref=orm.backref('roles',
                    primaryjoin=authorization_group_table.c.id==authorization_group_role_table.c.authorization_group_id,
                    cascade='all, delete, delete-orphan'
                 ),
            )
    },
    order_by=[authorization_group_role_table.c.user_object_role_id],
)

mapper(SystemRole, system_role_table, inherits=UserObjectRole,
       polymorphic_identity=unicode(System.__name__),
       order_by=[system_role_table.c.user_object_role_id],
)
