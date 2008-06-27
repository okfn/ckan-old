from ckan.lib.base import *
import simplejson
import logging
import ckan.model as model

class CkanBaseController(BaseController):

    repo = model.repo
    log = logging.getLogger(__name__)

    def __before__(self, action, **params):
        # what is different between session['user'] and environ['REMOTE_USER']
        c.user = request.environ.get('REMOTE_USER', None)
        c.remote_addr = request.environ.get('REMOTE_ADDR', 'Unknown IP Address')
        if c.remote_addr == 'localhost' or c.remote_addr == '127.0.0.1':
            # see if it was proxied
            c.remote_addr = request.environ.get('HTTP_X_FORWARDED_FOR',
                    '127.0.0.1')
        if c.user:
            c.author = c.user
        else:
            c.author = c.remote_addr
        c.has_paginate = False
        c.has_autocomplete = False

    def _paginate_list(self, register_name, id, template_path):
        c.has_paginate = True
        try:
            current_page = int(id)
        except:
            current_page = 0
        if register_name == 'revisions':
            select_results = self.repo.history()
            collection = list(select_results)
        else:
            rev = self.repo.youngest_revision()
            register = getattr(rev.model, register_name)
            collection = register.list()
        item_count = len(collection)
        if c.format == 'json':
            response.headers['Content-Type'] = 'text/plain'
            list_name = '%s-list' % register_name
            list_value = [{'id': i.name} for i in collection]
            return simplejson.dumps({list_name: list_value})
        else:
            import paginate
            c.page = paginate.Page(
                collection=collection,
                current_page=current_page,
                items_per_page=50,
                item_count=item_count,
            )
            c.register_name = register_name
            #if 'paginatedlist' in request.params:
            #    template_path = 'paginated_list_contents'
            return render(template_path)


