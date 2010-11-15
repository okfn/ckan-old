"""
Provides plugin services to the CKAN
"""

import logging
from inspect import isclass
from itertools import chain
from pkg_resources import iter_entry_points
from pyutilib.component.core import PluginGlobals, ExtensionPoint, implements
from pyutilib.component.core import SingletonPlugin as _pca_SingletonPlugin
from pyutilib.component.core import Plugin as _pca_Plugin
from pyutilib.component.core import PluginEnvironment
from sqlalchemy.orm.interfaces import MapperExtension

from ckan.plugins.interfaces import IPluginObserver

__all__ = [
    'ExtensionPoint', 'implements',
    'PluginNotFoundException', 'Plugin', 'SingletonPlugin',
    'load', 'load_all', 'unload', 'unload_all',
    'reset'
]

log = logging.getLogger(__name__)

# Entry point group. 
PLUGINS_ENTRY_POINT_GROUP = "ckan.plugins"

# Entry point group for system plugins (those that are part of core ckan and do
# not need to be explicitly enabled by the user)
SYSTEM_PLUGINS_ENTRY_POINT_GROUP = "ckan.system_plugins"

class PluginNotFoundException(Exception):
    """
    Raised when a requested plugin cannot be found.
    """

class Plugin(_pca_Plugin):
    """
    Base class for plugins which require multiple instances.

    Unless you need multiple instances of your plugin object you should
    probably use SingletonPlugin.
    """

class SingletonPlugin(_pca_SingletonPlugin):
    """
    Base class for plugins which are singletons (ie most of them)

    One singleton instance of this class will be created when the plugin is
    loaded. Subsequent calls to the class constructor will always return the
    same singleton instance.
    """

def _get_service(plugin):
    """
    Return a service (ie an instance of a plugin class).

    :param plugin: any of: the name of a plugin entry point; a plugin class; an
        instantiated plugin object.
    :return: the service object
    """

    if isinstance(plugin, basestring):
        try:
            (plugin,) = iter_entry_points(
                group=PLUGINS_ENTRY_POINT_GROUP,
                name=plugin
            )
        except ValueError:
            raise PluginNotFoundException(plugin)

        return plugin.load()()

    elif isinstance(plugin, _pca_Plugin):
        return plugin

    elif isclass(plugin) and issubclass(plugin, _pca_Plugin):
        return plugin()

    else:
        raise TypeError("Expected a plugin name, class or instance", plugin)


def load_all(config):
    """
    Load all plugins listed in the 'ckan.plugins' config directive.
    """
    plugins = chain(
        find_system_plugins(),
        find_user_plugins(config)
    )

    # PCA default behaviour is to activate SingletonPlugins at import time. We
    # only want to activate those listed in the config, so clear
    # everything then activate only those we want.
    unload_all()

    for plugin in plugins:
        load(plugin)

def reset():
    """
    Clear and reload all configured plugins
    """
    from pylons import config
    load_all(config)

def load(plugin):
    """
    Load a single plugin, given a plugin name, class or instance
    """
    observers = ExtensionPoint(IPluginObserver)
    for observer_plugin in observers:
        observer_plugin.before_load(plugin)
    service = _get_service(plugin)
    service.activate()
    for observer_plugin in observers:
        observer_plugin.after_load(service)
    return service

def unload_all():
    """
    Unload (deactivate) all loaded plugins
    """
    for env in PluginGlobals.env_registry.values():
        for service in env.services.copy():
            unload(service)

def unload(plugin):
    """
    Unload a single plugin, given a plugin name, class or instance
    """
    observers = ExtensionPoint(IPluginObserver)
    service = _get_service(plugin)
    for observer_plugin in observers:
        observer_plugin.before_unload(service)

    service.deactivate()

    for observer_plugin in observers:
        observer_plugin.after_unload(service)

    return service

def find_user_plugins(config):
    """
    Return all plugins specified by the user in the 'ckan.plugins' config
    directive.
    """
    plugins = []
    for name in config.get('ckan.plugins', '').split():
        entry_points = list(
            iter_entry_points(group=PLUGINS_ENTRY_POINT_GROUP, name=name)
        )
        if not entry_points:
            raise PluginNotFoundException(name)
        plugins.extend(ep.load() for ep in entry_points)
    return plugins

def find_system_plugins():
    """
    Return all plugins in the ckan.system_plugins entry point group.
    
    These are essential for operation and therefore cannot be enabled/disabled
    through the configuration file.
    """
    return (
        ep.load()
        for ep in iter_entry_points(group=SYSTEM_PLUGINS_ENTRY_POINT_GROUP)
    )

######  Pylons monkey-patch
# Required by the deliverance plugin and iATI

from pylons.wsgiapp import PylonsApp
import pkg_resources

log.info("Monkey-patching Pylons to allow loading of controllers via entry point mechanism")

find_controller_generic = PylonsApp.find_controller

# This is from pylons 1.0 source, will monkey-patch into 0.9.7
def find_controller(self, controller):
    if controller in self.controller_classes:
        return self.controller_classes[controller]

    # Check to see if its a dotted name
    if '.' in controller or ':' in controller:
        mycontroller = pkg_resources.EntryPoint.parse('x=%s' % controller).load(False)
        self.controller_classes[controller] = mycontroller
        return mycontroller

    return find_controller_generic(self, controller)

PylonsApp.find_controller = find_controller
