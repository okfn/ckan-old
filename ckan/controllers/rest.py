import sqlalchemy.orm
import logging

from paste.util.multidict import MultiDict 
from ckan.lib.base import *
from ckan.lib.helpers import json
import ckan.model as model
import ckan.forms
from ckan.lib.search import query_for, QueryOptions, SearchError, DEFAULT_OPTIONS
import ckan.authz
import ckan.rating
from ckan.plugins import ExtensionPoint, IGroupController, IPackageController

log = logging.getLogger(__name__)

IGNORE_FIELDS = ['q']

class BaseApiController(BaseController):

    api_version = ''
    ref_package_by = ''
    ref_group_by = ''
    content_type_json = 'application/json;charset=utf-8'

    def _ref_package(self, package):
        assert self.ref_package_by in ['id', 'name']
        return getattr(package, self.ref_package_by)

    def _ref_group(self, group):
        assert self.ref_group_by in ['id', 'name']
        return getattr(group, self.ref_group_by)

    def _ref_harvest_source(self, harvest_source):
        return getattr(harvest_source, 'id')

    def _list_package_refs(self, packages):
        return [getattr(p, self.ref_package_by) for p in packages]

    def _list_group_refs(self, groups):
        return [getattr(p, self.ref_group_by) for p in groups]

    def _finish_ok(self, response_data=None):
        # response.status_int = 200 -- already will be so
        response.headers['Content-Type'] = self.content_type_json
        response_msg = ''
        if response_data is not None:
            response_msg = json.dumps(response_data)
            # Support "JSONP" callback.
            if request.params.has_key('callback') and request.method == 'GET':
                callback = request.params['callback']
                response_msg = self._wrap_jsonp(callback, response_msg)
        return response_msg

    def _wrap_jsonp(self, callback, response_msg):
        return '%s(%s);' % (callback, response_msg)


class ApiVersion1(BaseApiController):

    api_version = '1'
    ref_package_by = 'name'
    ref_group_by = 'name'


class ApiVersion2(BaseApiController):

    api_version = '2'
    ref_package_by = 'id'
    ref_group_by = 'id'



class BaseRestController(BaseApiController):

    def get_api(self):
        response_data = {}
        response_data['version'] = self.api_version
        return self._finish_ok(response_data) 

    def list(self, register, subregister=None, id=None):
        log.debug('list %s' % (request.path))
        if register == 'revision':
            revs = model.Session.query(model.Revision).all()
            return self._finish_ok([rev.id for rev in revs])
        elif register == u'package' and not subregister:
            query = ckan.authz.Authorizer().authorized_query(self._get_username(), model.Package)
            packages = query.all()
            response_data = self._list_package_refs(packages)
            return self._finish_ok(response_data)
        elif register == u'package' and subregister == 'relationships':
            #TODO authz stuff for this and related packages
            pkg = self._get_pkg(id)
            if not pkg:
                response.status_int = 404
                return 'First package named in request was not found.'
            relationships = pkg.get_relationships()
            response_data = [rel.as_dict(package=pkg, ref_package_by=self.ref_package_by) for rel in relationships]
            return self._finish_ok(response_data)
        elif register == u'group':
            groups = model.Session.query(model.Group).all() 
            response_data = self._list_group_refs(groups)
            return self._finish_ok(response_data)
        elif register == u'tag':
            tags = model.Session.query(model.Tag).all() #TODO
            response_data = [tag.name for tag in tags]
            return self._finish_ok(response_data)
        elif register == u'changeset':
            from ckan.model.changeset import ChangesetRegister
            response_data = ChangesetRegister().keys()
            return self._finish_ok(response_data)
        elif register == u'licenses':
            from ckan.model.license import LicenseRegister
            licenses = LicenseRegister().values()
            response_data = [l.as_dict() for l in licenses]
            return self._finish_ok(response_data)
        elif register == u'harvestsource':
            filter_kwds = {}
            if id == 'publisher':
                filter_kwds['publisher_ref'] = subregister
            objects = model.HarvestSource.filter(**filter_kwds)
            response_data = [o.id for o in objects]
            return self._finish_ok(response_data)
        elif register == u'harvestingjob':
            filter_kwds = {}
            if id == 'status':
                filter_kwds['status'] = subregister.lower().capitalize()
            objects = model.HarvestingJob.filter(**filter_kwds)
            response_data = [o.id for o in objects]
            return self._finish_ok(response_data)
        else:
            response.status_int = 400
            return gettext('Cannot list entity of this type: %s') % register

    def show(self, register, id, subregister=None, id2=None):
        log.debug('show %s/%s/%s/%s' % (register, id, subregister, id2))
        if register == u'revision':
            # Todo: Implement access control for revisions.
            rev = model.Session.query(model.Revision).get(id)
            if rev is None:
                response.status_int = 404
                return ''
            response_data = {
                'id': rev.id,
                'timestamp': model.strftimestamp(rev.timestamp),
                'author': rev.author,
                'message': rev.message,
                'packages': self._list_package_refs(rev.packages),
            }
            return self._finish_ok(response_data)
        elif register == u'changeset':
            from ckan.model.changeset import ChangesetRegister
            changesets = ChangesetRegister()
            changeset = changesets.get(id, None)
            #if not self._check_access(changeset, model.Action.READ):
            #    return ''
            if changeset is None:
                response.status_int = 404
                return ''            
            response_data = changeset.as_dict()
            return self._finish_ok(response_data)
        elif register == u'package' and not subregister:
            pkg = self._get_pkg(id)
            if pkg == None:
                response.status_int = 404
                return ''
            if not self._check_access(pkg, model.Action.READ):
                return ''
            for item in ExtensionPoint(IPackageController):
                item.read(pkg)
            response_data = self._represent_package(pkg)
            return self._finish_ok(response_data)
        elif register == u'package' and (subregister == 'relationships' or subregister in model.PackageRelationship.get_all_types()):
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            if subregister == 'relationships':
                relationships = pkg1.get_relationships_with(pkg2)
            else:
                relationships = pkg1.get_relationships_with(pkg2,
                                                            type=subregister)
                if not relationships:
                    response.status_int = 404
                    return 'Relationship "%s %s %s" not found.' % \
                           (id, subregister, id2)
            response_data = [rel.as_dict(pkg1, ref_package_by=self.ref_package_by) for rel in relationships]
            return self._finish_ok(response_data)

        elif register == u'group':
            group = model.Group.by_name(id)
            if group is None:
                response.status_int = 404
                return ''

            if not self._check_access(group, model.Action.READ):
                return ''
            for item in ExtensionPoint(IGroupController):
                item.read(group)
            _dict = group.as_dict(ref_package_by=self.ref_package_by)
            #TODO check it's not none
            return self._finish_ok(_dict)
        elif register == u'tag':
            obj = model.Tag.by_name(id) #TODO tags
            if obj is None:
                response.status_int = 404
                return ''            
            response_data = [pkgtag.package.name for pkgtag in obj.package_tags]
            return self._finish_ok(response_data)
        elif register == u'harvestsource':
            obj = model.HarvestSource.get(id, default=None)
            if obj is None:
                response.status_int = 404
                return ''            
            response_data = obj.as_dict()
            return self._finish_ok(response_data)
        elif register == u'harvestingjob':
            obj = model.HarvestingJob.get(id, default=None)
            if obj is None:
                response.status_int = 404
                return ''            
            response_data = obj.as_dict()
            return self._finish_ok(response_data)
        else:
            response.status_int = 400
            return gettext('Cannot read entity of this type: %s') % register

    def _represent_package(self, package):
        return package.as_dict(ref_package_by=self.ref_package_by, ref_group_by=self.ref_group_by)

    def create(self, register, id=None, subregister=None, id2=None):
        log.debug('create %s/%s/%s/%s params: %r' % (register, id, subregister, id2, request.params))
        # Check an API key given, otherwise deny access.
        if not self._check_access(None, None):
            return json.dumps(_('Access denied'))
        # Read the request data.
        try:
            request_data = self._get_request_data()
        except ValueError, inst:
            response.status_int = 400
            return gettext('JSON Error: %s') % str(inst)
        try:
            if register == 'package' and not subregister:
                # Create a Package.
                fs = self._get_standard_package_fieldset()
                try:
                    request_fa_dict = ckan.forms.edit_package_dict(ckan.forms.get_package_dict(fs=fs), request_data)
                except ckan.forms.PackageDictFormatError, inst:
                    log.error('Package format incorrect: %s' % str(inst))
                    response.status_int = 400
                    return gettext('Package format incorrect: %s') % str(inst)
                fs = fs.bind(model.Package, data=request_fa_dict, session=model.Session)
                # ...continues below.
            elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
                # Create a Package Relationship.
                pkg1 = self._get_pkg(id)
                pkg2 = self._get_pkg(id2)
                if not pkg1:
                    response.status_int = 404
                    return 'First package named in address was not found.'
                if not pkg2:
                    response.status_int = 404
                    return 'Second package named in address was not found.'
                comment = request_data.get('comment', u'')
                existing_rels = pkg1.get_relationships_with(pkg2, subregister)
                if existing_rels:
                    return self._update_package_relationship(existing_rels[0],
                                                             comment)
                rev = model.repo.new_revision()
                rev.author = self.rest_api_user
                rev.message = _(u'REST API: Create package relationship: %s %s %s') % (pkg1, subregister, pkg2)
                rel = pkg1.add_relationship(subregister, pkg2, comment=comment)
                model.repo.commit_and_remove()
                response_data = rel.as_dict(ref_package_by=self.ref_package_by)
                return self._finish_ok(response_data)
            elif register == 'group' and not subregister:
                # Create a Group.
                is_admin = ckan.authz.Authorizer().is_sysadmin(c.user)
                request_fa_dict = ckan.forms.edit_group_dict(ckan.forms.get_group_dict(), request_data)
                fs = ckan.forms.get_group_fieldset(combined=True, is_admin=is_admin)
                fs = fs.bind(model.Group, data=request_fa_dict, session=model.Session)
                # ...continues below.
            elif register == 'rating' and not subregister:
                # Create a Rating.
                return self._create_rating(request_data)
            elif register == 'harvestingjob' and not subregister:
                # Create a HarvestingJob.
                return self._create_harvesting_job(request_data)
            else:
                # Complain about unsupported entity type.
                log.error('Cannot create new entity of this type: %s %s' % (register, subregister))
                response.status_int = 400
                return gettext('Cannot create new entity of this type: %s %s') % (register, subregister)
            # Validate the fieldset.
            validation = fs.validate()
            if not validation:
                # Complain about validation errors.
                log.error('Validation error: %r' % repr(fs.errors))
                response.status_int = 409
                return json.dumps(repr(fs.errors))
            # Construct new revision.
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Create object %s') % str(fs.name.value)
            # Construct catalogue entity.
            fs.sync()
            # Construct access control entities.
            if self.rest_api_user:
                admins = [model.User.by_name(self.rest_api_user.decode('utf8'))]
            else:
                admins = []
            model.setup_default_user_roles(fs.model, admins)
            # Commit
            if register == 'package' and not subregister:
                for item in ExtensionPoint(IPackageController):
                    item.create(fs.model)
            elif register == 'group' and not subregister:
                for item in ExtensionPoint(IGroupController):
                    item.create(fs.model)
            model.repo.commit()        
        except Exception, inst:
            log.exception(inst)
            model.Session.rollback()
            if 'fs' in dir():
                log.error('Exception creating object %s: %r' % (str(fs.name.value), inst))
            else:
                log.error('Exception creating object fieldset for register %r: %r' % (register, inst))                
            raise
        log.debug('Created object %s' % str(fs.name.value))
        obj = fs.model
        # Set location header with new ID.
        location = str('%s/%s' % (request.path, obj.id))
        response.headers['Location'] = location
        log.debug('Response headers: %r' % (response.headers))
        # Todo: Return 201, not 200.
        return self._finish_ok(obj.as_dict())
            
    def update(self, register, id, subregister=None, id2=None):
        log.debug('update %s/%s/%s/%s' % (register, id, subregister, id2))
        # must be logged in to start with
        if not self._check_access(None, None):
            return json.dumps(_('Access denied'))

        if register == 'package' and not subregister:
            entity = self._get_pkg(id)
            if entity == None:
                response.status_int = 404
                return 'Package was not found.'
        elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            existing_rels = pkg1.get_relationships_with(pkg2, subregister)
            if not existing_rels:
                response.status_int = 404
                return 'This relationship between the packages was not found.'
            entity = existing_rels[0]
        elif register == 'group' and not subregister:
            entity = model.Group.by_name(id)
            if entity == None:
                response.status_int = 404
                return 'Group was not found.'
        else:
            response.status_int = 400
            return gettext('Cannot update entity of this type: %s') % register
        if not entity:
            response.status_int = 404
            return ''

        if (not subregister and \
            not self._check_access(entity, model.Action.EDIT)) \
            or not self._check_access(None, None):
            return json.dumps(_('Access denied'))

        try:
            request_data = self._get_request_data()
        except ValueError, inst:
            response.status_int = 400
            return gettext('JSON Error: %s') % str(inst)

        if not subregister:
            if register == 'package':
                fs = self._get_standard_package_fieldset()
                try:
                    request_fa_dict = ckan.forms.GetEditFieldsetPackageData(
                        fieldset=fs, package=entity, data=request_data).data
                except ckan.forms.PackageDictFormatError, inst:
                    response.status_int = 400
                    return gettext('Package format incorrect: %s') % str(inst)
            elif register == 'group':
                auth_for_change_state = ckan.authz.Authorizer().am_authorized(c, 
                    model.Action.CHANGE_STATE, entity)
                orig_entity_dict = ckan.forms.get_group_dict(entity)
                request_fa_dict = ckan.forms.edit_group_dict(orig_entity_dict, request_data, id=entity.id)
                fs = ckan.forms.get_group_fieldset(combined=True, is_admin=auth_for_change_state)
            fs = fs.bind(entity, data=request_fa_dict)
            
            validation = fs.validate()
            if not validation:
                response.status_int = 409
                return json.dumps(repr(fs.errors))
            try:
                rev = model.repo.new_revision()
                rev.author = self.rest_api_user
                rev.message = _(u'REST API: Update object %s') % str(fs.name.value)
                fs.sync()
                
                if register == 'package' and not subregister:
                    for item in ExtensionPoint(IPackageController):
                        item.edit(fs.model)
                elif register == 'group' and not subregister:
                    for item in ExtensionPoint(IGroupController):
                        item.edit(fs.model)

                model.repo.commit()        
            except Exception, inst:
                log.exception(inst)
                model.Session.rollback()
                if inst.__class__.__name__ == 'IntegrityError':
                    response.status_int = 409
                    return ''
                else:
                    raise
            obj = fs.model
            return self._finish_ok(obj.as_dict())
        else:
            if register == 'package':
                comment = request_data.get('comment', u'')
                return self._update_package_relationship(entity, comment)

    def delete(self, register, id, subregister=None, id2=None):
        log.debug('delete %s/%s/%s/%s' % (register, id, subregister, id2))
        # must be logged in to start with
        if not self._check_access(None, None):
            return json.dumps(_('Access denied'))

        if register == 'package' and not subregister:
            entity = self._get_pkg(id)
            if not entity:
                response.status_int = 404
                return 'Package was not found.'
            revisioned_details = 'Package: %s' % entity.name
        elif register == 'package' and subregister in model.PackageRelationship.get_all_types():
            pkg1 = self._get_pkg(id)
            pkg2 = self._get_pkg(id2)
            if not pkg1:
                response.status_int = 404
                return 'First package named in address was not found.'
            if not pkg2:
                response.status_int = 404
                return 'Second package named in address was not found.'
            existing_rels = pkg1.get_relationships_with(pkg2, subregister)
            if not existing_rels:
                response.status_int = 404
                return ''
            entity = existing_rels[0]
            revisioned_details = 'Package Relationship: %s %s %s' % (id, subregister, id2)
        elif register == 'group' and not subregister:
            entity = model.Group.by_name(id)
            if not entity:
                response.status_int = 404
                return 'Group was not found.'
            revisioned_details = 'Group: %s' % entity.name
        elif register == 'harvestingjob' and not subregister:
            entity = model.HarvestingJob.get(id, default=None)
            revisioned_details = None
        else:
            response.status_int = 400
            return gettext('Cannot delete entity of this type: %s %s') % (register, subregister or '')
        if not entity:
            response.status_int = 404
            return ''

        if not self._check_access(entity, model.Action.PURGE):
            return json.dumps(_('Access denied'))

        if revisioned_details:
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Delete %s') % revisioned_details
            
        try:
            if register == 'package' and not subregister:
                for item in ExtensionPoint(IPackageController):
                    item.delete(entity)
            elif register == 'group' and not subregister:
                for item in ExtensionPoint(IGroupController):
                    item.delete(entity)

            entity.delete()
            model.repo.commit()        
        except Exception, inst:
            log.exception(inst)
            raise

        return self._finish_ok()

    def search(self, register=None):
        log.debug('search %s params: %r' % (register, request.params))
        if register == 'revision':
            since_time = None
            if request.params.has_key('since_id'):
                id = request.params['since_id']
                rev = model.Session.query(model.Revision).get(id)
                if rev is None:
                    response.status_int = 400
                    return gettext(u'There is no revision with id: %s') % id
                since_time = rev.timestamp
            elif request.params.has_key('since_time'):
                since_time_str = request.params['since_time']
                try:
                    since_time = model.strptimestamp(since_time_str)
                except ValueError, inst:
                    response.status_int = 400
                    return 'ValueError: %s' % inst
            else:
                response.status_int = 400
                return gettext("Missing search term ('since_id=UUID' or 'since_time=TIMESTAMP')")
            revs = model.Session.query(model.Revision).filter(model.Revision.timestamp>since_time)
            return self._finish_ok([rev.id for rev in revs])
        elif register == 'package' or register == 'resource':
            if request.params.has_key('qjson'):
                if not request.params['qjson']:
                    response.status_int = 400
                    return gettext('Blank qjson parameter')
                params = json.loads(request.params['qjson'])
            elif request.params.values() and request.params.values() != [u''] and request.params.values() != [u'1']:
                params = request.params
            else:
                try:
                    params = self._get_request_data()
                except ValueError, inst:
                    response.status_int = 400
                    return gettext(u'Search params: %s') % unicode(inst)
            
            options = QueryOptions()
            for k, v in params.items():
                if (k in DEFAULT_OPTIONS.keys()):
                    options[k] = v
            options.update(params)
            options.username = self._get_username()
            options.search_tags = False
            options.return_objects = False
            
            query_fields = MultiDict()
            for field, value in params.items():
                field = field.strip()
                if field in DEFAULT_OPTIONS.keys() or \
                   field in IGNORE_FIELDS:
                    continue
                values = [value]
                if isinstance(value, list):
                    values = value
                for v in values:
                    query_fields.add(field, v)
            
            if register == 'package':
                options.ref_entity_with_attr = self.ref_package_by
            try:
                backend = None
                if register == 'resource': 
                    query = query_for(model.PackageResource, backend='sql')
                else:
                    query = query_for(model.Package)
                results = query.run(query=params.get('q'), 
                                    fields=query_fields, 
                                    options=options)
                return self._finish_ok(results)
            except SearchError, e:
                log.exception(e)
                response.status_int = 400
                return gettext('Bad search option: %s') % e
        else:
            response.status_int = 404
            return gettext('Unknown register: %s') % register

    def tag_counts(self):
        log.debug('tag counts')
        tags = model.Session.query(model.Tag).all()
        results = []
        for tag in tags:
            tag_count = len(tag.package_tags)
            results.append((tag.name, tag_count))
        return self._finish_ok(results)

    def throughput(self):
        qos = self._calc_throughput()
        qos = str(qos)
        return self._finish_ok(qos)

    def _calc_throughput(self):
        period = 10  # Seconds.
        timing_cache_path = self._get_timing_cache_path()
        call_count = 0
        import datetime, glob
        for t in range(0, period):
            expr = '%s/%s*' % (
                timing_cache_path,
                (datetime.datetime.now() - datetime.timedelta(0,t)).isoformat()[0:19],
            )
            call_count += len(glob.glob(expr))
        # Todo: Clear old records.
        return float(call_count) / period

    def _create_rating(self, params):
        """ Example data:
               rating_opts = {'package':u'warandpeace',
                              'rating':5}
        """
        # check options
        package_ref = params.get('package')
        rating = params.get('rating')
        user = self.rest_api_user
        opts_err = None
        if not package_ref:
            opts_err = gettext('You must supply a package id or name (parameter "package").')
        elif not rating:
            opts_err = gettext('You must supply a rating (parameter "rating").')
        else:
            try:
                rating_int = int(rating)
            except ValueError:
                opts_err = gettext('Rating must be an integer value.')
            else:
                package = self._get_pkg(package_ref)
                if rating < ckan.rating.MIN_RATING or rating > ckan.rating.MAX_RATING:
                    opts_err = gettext('Rating must be between %i and %i.') % (ckan.rating.MIN_RATING, ckan.rating.MAX_RATING)
                elif not package:
                    opts_err = gettext('Package with name %r does not exist.') % package_ref
        if opts_err:
            self.log.debug(opts_err)
            response.status_int = 400
            response.headers['Content-Type'] = self.content_type_json
            return opts_err

        user = model.User.by_name(self.rest_api_user)
        ckan.rating.set_rating(user, package, rating_int)

        package = self._get_pkg(package_ref)
        ret_dict = {'rating average':package.get_average_rating(),
                    'rating count': len(package.ratings)}
        return self._finish_ok(ret_dict)

    def _create_harvesting_job(self, params):
        """ Example data: {'user_ref':u'0005', 'source_id':5}
        """
        # Pick out attribute values from request.
        user_ref = params.get('user_ref')
        source_id = params.get('source_id')
        # Validate values.
        opts_err = ''
        if not user_ref:
            opts_err = gettext('You must supply a user_ref.')
        elif not source_id:
            opts_err = gettext('You must supply a source_id.')
        else:
            source = model.HarvestSource.get(source_id, default=None)
            if not source:
                opts_err = gettext('Harvest source %s does not exist.') % source_id
        if opts_err:
            self.log.debug(opts_err)
            response.status_int = 400
            response.headers['Content-Type'] = self.content_type_json
            return json.dumps(opts_err)
        # Create job.
        job = model.HarvestingJob(source_id=source_id, user_ref=user_ref)
        model.Session.add(job)
        model.Session.commit()
        ret_dict = job.as_dict()
        return self._finish_ok(ret_dict)

    def _get_username(self):
        user = self._get_user_for_apikey()
        return user and user.name or u''

    def _check_access(self, entity, action):
        # Checks apikey is okay and user is authorized to do the specified
        # action on the specified package (or other entity).
        # If both args are None then just check the apikey corresponds
        # to a user.
        api_key = None
        # Todo: Remove unused 'isOk' variable.
        isOk = False

        self.rest_api_user = self._get_username()
        log.debug('check access - user %r' % self.rest_api_user)
        
        if action and entity and not isinstance(entity, model.PackageRelationship) \
                and not isinstance(entity, model.HarvestingJob):
            if action != model.Action.READ and self.rest_api_user in (model.PSEUDO_USER__VISITOR, ''):
                self.log.debug("Valid API key needed to make changes")
                response.status_int = 403
                response.headers['Content-Type'] = self.content_type_json
                return False                
            
            am_authz = ckan.authz.Authorizer().is_authorized(self.rest_api_user, action, entity)
            if not am_authz:
                self.log.debug("User is not authorized to %s %s" % (action, entity))
                response.status_int = 403
                response.headers['Content-Type'] = self.content_type_json
                return False
        elif not self.rest_api_user:
            self.log.debug("No valid API key provided.")
            response.status_int = 403
            response.headers['Content-Type'] = self.content_type_json
            return False
        self.log.debug("Access OK.")
        response.status_int = 200
        return True                

    def _update_package_relationship(self, relationship, comment):
        is_changed = relationship.comment != comment
        if is_changed:
            rev = model.repo.new_revision()
            rev.author = self.rest_api_user
            rev.message = _(u'REST API: Update package relationship: %s %s %s') % (relationship.subject, relationship.type, relationship.object)
            relationship.comment = comment
            model.repo.commit_and_remove()
        return self._finish_ok(relationship.as_dict())


class RestController(ApiVersion1, BaseRestController):
    # Implements CKAN API Version 1.

    def _represent_package(self, package):
        msg_data = super(RestController, self)._represent_package(package)
        msg_data['download_url'] = package.resources[0].url if package.resources else ''
        return msg_data

