from ckan.controllers.base import *
import simplejson
from ckan.modes import RegisterGet, RegisterPost, RegisterSearch
from ckan.modes import EntityGet, EntityPut, EntityDelete
import ckan.model as model

class RestController(CkanBaseController):

    def index(self):
        return render('rest/index')

    def list(self, register):
        if not self.check_access(): return simplejson.dumps("Access denied")
        registry_path = '/%s' % register
        self.log.debug("Listing: %s" % registry_path)
        self.mode = RegisterGet(registry_path).execute()
        return self.finish()

    def create(self, register):
        if not self.check_access(): return simplejson.dumps("Access denied")
        registry_path = '/%s' % register
        try:
            request_data = request.params.keys()[0]
        except Exception, inst:
            msg = "Can't find entity data in request params %s: %s" % (
                request.params.items(), str(inst)
            )
            raise Exception, msg
        self.log.debug("Loading JSON string: %s" % (request_data))
        request_data = simplejson.loads(request_data)
        self.log.debug("Creating: %s with %s" % (registry_path, request_data))
        self.mode = RegisterPost(registry_path, request_data).execute()
        return self.finish()

    def show(self, register, id):
        if not self.check_access(): return simplejson.dumps("Access denied")
        id = self.fix_id(id)
        registry_path = '/%s/%s' % (register, id)
        self.log.debug("Reading: %s" % registry_path)
        self.mode = EntityGet(registry_path).execute()
        return self.finish()

    def update(self, register, id):
        if not self.check_access(): return simplejson.dumps("Access denied")
        id = self.fix_id(id)
        registry_path = '/%s/%s' % (register, id)
        try:
            request_data = request.params.keys()[0]
        except Exception, inst:
            msg = "Can't find entity data in request params %s: %s" % (
                request.params.items(), str(inst)
            )
            raise Exception, msg
        request_data = simplejson.loads(request_data)
        if 'id' in request_data:
            request_data.pop('id')
        self.log.debug("Updating: %s with %s" % (registry_path, request_data))
        self.mode = EntityPut(registry_path, request_data).execute()
        return self.finish()

    def delete(self, register, id):
        if not self.check_access(): return simplejson.dumps("Access denied")
        id = self.fix_id(id)
        registry_path = '/%s/%s' % (register, id)
        self.log.debug("Deleting: %s" % registry_path)
        self.mode = EntityDelete(registry_path).execute()
        return self.finish()

    def search(self, register):
        if not self.check_access(): return simplejson.dumps("Access denied")
        registry_path = '/%s' % register
        request_data = self._get_request_data()
        self.log.debug("Searching: %s" % registry_path)
        self.mode = RegisterSearch(registry_path, request_data).execute()
        return self.finish()

    def finish(self):
        response.status_code = self.mode.response_code
        return simplejson.dumps(self.mode.response_data)

    def fix_id(self, id):
        return id

    def check_access(self):
        isOk = False
        # Follow this way for API authentication, reuses existing passwords?
        # http://developer.yahoo.com/python/python-rest.html#auth
        isOk = True  # Todo: Instead, call access control logic.
        if isOk:
            response.status_code = 200
            return True
        else:
            response.status_code = 401
            return False

    def _get_request_data(self):
        try:
            request_data = request.params.keys()[0]
        except Exception, inst:
            msg = "Can't find entity data in request params %s: %s" % (
                request.params.items(), str(inst)
            )
            raise Exception, msg
        request_data = simplejson.loads(request_data)
        return request_data
