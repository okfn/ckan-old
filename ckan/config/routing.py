"""Routes configuration

The more specific and detailed routes should be defined first so they
may take precedent over the more generic routes. For more information
refer to the routes manual at http://routes.groovie.org/docs/
"""
from pylons import config
from routes import Mapper
from formalchemy.ext.pylons import maps # routes generator

def make_map():
    """Create, configure and return the routes Mapper"""
    map = Mapper(directory=config['pylons.paths']['controllers'],
                 always_scan=config['debug'])

    # The ErrorController route (handles 404/500 error pages); it should
    # likely stay at the top, ensuring it can always be resolved
    map.connect('error/:action/:id', controller='error')

    # CUSTOM ROUTES HERE

    map.connect('home', '', controller='home', action='index')
    map.connect('guide', 'guide', controller='home', action='guide')
    map.connect('license', 'license', controller='home', action='license')
    map.connect('about', 'about', controller='home', action='about')
    maps.admin_map(map, controller='admin', url='/admin')
    map.connect('api/search/:register', controller='rest', action='search')
    map.connect('api/rest', controller='rest', action='index')
    map.connect('api/rest/:register', controller='rest', action='list',
        conditions=dict(method=['GET']))
    map.connect('api/rest/:register', controller='rest', action='create',
        conditions=dict(method=['POST']))
    map.connect('api/rest/:register/:id', controller='rest', action='show',
        conditions=dict(method=['GET']))
    map.connect('api/rest/:register/:id', controller='rest', action='update',
        conditions=dict(method=['PUT']))
    map.connect('api/rest/:register/:id', controller='rest', action='update',
        conditions=dict(method=['POST']))
    map.connect('api/rest/:register/:id', controller='rest', action='delete',
        conditions=dict(method=['DELETE']))

    map.connect('package', controller='package', action='index')
    map.connect('package/search', controller='package', action='search')
    map.connect('package/list', controller='package', action='list')
    map.connect('package/new', controller='package', action='new')
    map.connect('package/:id', controller='package', action='read')
    map.connect('group', controller='group', action='list')
    map.connect('group/:id', controller='group', action='read')
    map.connect(':controller/:action/:id')
    map.connect('*url', controller='template', action='view')

    return map
