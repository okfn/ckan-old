import random
import sys

from pylons import cache, config
from genshi.template import NewTextTemplate

from ckan.authz import Authorizer
from ckan.lib.search import query_for, QueryOptions, SearchError
from ckan.lib.cache import proxy_cache, get_cache_expires
from ckan.lib.base import *
import ckan.lib.stats

cache_expires = get_cache_expires(sys.modules[__name__])

class HomeController(BaseController):
    repo = model.repo   

    authorizer = Authorizer()

    @proxy_cache(expires=cache_expires)
    def index(self):
        query = query_for(model.Package)
        query.run(query='*:*', facet_by=g.facets,
                  limit=0, offset=0, username=c.user)
        c.facets = query.facets
        c.fields = []
        c.package_count = query.count
        c.latest_packages = self.authorizer.authorized_query(c.user, model.Package)\
            .join('revision').order_by(model.Revision.timestamp.desc())\
            .limit(5).all()

        if len(c.latest_packages):
            cache_key = str(hash((c.latest_packages[0].id, c.user)))
        else:
            cache_key = "fresh-install"
        
        etag_cache(cache_key)
        return render('home/index.html', cache_key=cache_key,
                cache_expire=cache_expires)

    def license(self):
        return render('home/license.html', cache_expire=cache_expires)

    def about(self):
        return render('home/about.html', cache_expire=cache_expires)
        
    def language(self):
        response.content_type = 'text/json'
        return render('home/language.js', cache_expire=cache_expires,
                      method='text', loader_class=NewTextTemplate)

    def cache(self, id):
        '''Manual way to clear the caches'''
        if id == 'clear':
            wui_caches = ['tag_counts', 'search_results', 'stats']
            for cache_name in wui_caches:
                cache_ = cache.get_cache(cache_name, type='dbm')
                cache_.clear()
            return 'Cleared caches: %s' % ', '.join(wui_caches)

