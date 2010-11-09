"""
Interfaces for plugins system
See doc/plugins.rst for more information
"""

__all__ = [
    'IGenshiStreamFilter', 'IRoutesExtension',
    'IMapperExtension', 'ISessionExtension',
    'IDomainObjectNotification', 'IGroupController', 
    'IPackageController'
]

from pyutilib.component.core import Interface

class IGenshiStreamFilter(Interface):
    '''
    Hook into template rendering.
    See ckan.lib.base.py:render
    '''

    def filter(self, stream):
        """
        Return a filtered Genshi stream.
        Called when any page is rendered.

        :param stream: Genshi stream of the current output document
        :returns: filtered Genshi stream
        """

class IRoutesExtension(Interface):
    """
    Plugin into the setup of the routes map creation.

    """
    def before_map(self, map):
        """
        Called before the routes map is generated. ``before_map`` is before any
        other mappings are created so can override all other mappings.

        :param map: Routes map object
        :returns: Modified version of the map object
        """

    def after_map(self, map):
        """
        Called after routes map is set up. ``after_map`` can be used to add fall-back handlers. 

        :param map: Routes map object
        :returns: Modified version of the map object
        """

class IMapperExtension(Interface):
    """
    A subset of the SQLAlchemy mapper extension hooks.
    See http://www.sqlalchemy.org/docs/05/reference/orm/interfaces.html#sqlalchemy.orm.interfaces.MapperExtension

    Example::

        >>> class MyPlugin(SingletonPlugin):
        ...
        ...     implements(IMapperExtension)
        ...
        ...     def after_update(self, mapper, connection, instance):
        ...         log("Updated: %r", instance)
    """

    def before_insert(self, mapper, connection, instance):
        """
        Receive an object instance before that instance is INSERTed into its table.
        """

    def before_update(self, mapper, connection, instance):
        """
        Receive an object instance before that instance is UPDATEed.
        """

    def before_delete(self, mapper, connection, instance):
        """
        Receive an object instance before that instance is DELETEed.
        """

    def after_insert(self, mapper, connection, instance):
        """
        Receive an object instance after that instance is INSERTed.
        """
                                     
    def after_update(self, mapper, connection, instance):
        """
        Receive an object instance after that instance is UPDATEed.
        """
    
    def after_delete(self, mapper, connection, instance):
        """
        Receive an object instance after that instance is DELETEed.
        """

class ISessionExtension(Interface):
    """
    A subset of the SQLAlchemy session extension hooks.
    """

    def after_begin(self, session, transaction, connection):
        """
        Execute after a transaction is begun on a connection
        """

    def before_flush(self, session, flush_context, instances):
        """
        Execute before flush process has started.
        """

    def after_flush(self, session, flush_context):
        """
        Execute after flush has completed, but before commit has been called.
        """

    def before_commit(self, session):
        """
        Execute right before commit is called.
        """

    def after_commit(self, session):
        """
        Execute after a commit has occured.
        """

    def after_rollback(self, session):
        """
        Execute after a rollback has occured.
        """

class IDomainObjectNotification(Interface):
    """
    Receives notification of new and changed domain objects
    """

    def after_insert(self, mapper, connection, instance):
        pass

    def after_update(self, mapper, connection, instance):
        pass

class IGroupController(Interface):
    """
    Extension points in the groups controller. These will 
    usually be called just before committing or returning the
    respective object, i.e. all validation, synchronization 
    and authorization setup are complete. 
    """

    def read(self, entity):
        pass

    def create(self, entity):
        pass

    def edit(self, entity):
        pass

    def authz_add_role(self, object_role):
        pass
    
    def authz_remove_role(self, object_role):
        pass

    def delete(self, entity):
        pass

class IPackageController(Interface):
    """
    Extension points in the package controller.
    (see IGroupController)
    """

    def read(self, entity):
        pass

    def create(self, entity):
        pass

    def edit(self, entity):
        pass

    def authz_add_role(self, object_role):
        pass
    
    def authz_remove_role(self, object_role):
        pass

    def delete(self, entity):
        pass
