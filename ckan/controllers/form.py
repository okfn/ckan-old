import logging
import sys, traceback
from ckan.lib.base import *
from ckan.lib.helpers import json
import ckan.forms
import ckan.controllers.package
from ckan.lib.package_saver import WritePackageFromBoundFieldset
from ckan.lib.package_saver import ValidationException
from ckan.controllers.rest import BaseApiController, ApiVersion1, ApiVersion2

log = logging.getLogger(__name__)

class ApiError(Exception): pass

# Todo: Create controller for testing package edit form (but try to disable for production usage).
# Todo: Refactor forms handling logic (to share common line between forms and edit).
# Todo: Remove superfluous commit_pkg() method parameter.
# Todo: Support setting choices (populates form input options and constrains validation)? Actually, perhaps groups shouldn't be editable on packages?

class BaseFormController(BaseApiController):
    """Implements the CKAN Forms API."""

    def _abort_bad_request(self, msg=None):
        response.status_int = 400
        error_msg = 'Bad request'
        if msg:
            error_msg += ': %s' % msg
        raise ApiError, "Bad request"
        
    def _abort_not_authorized(self):
        response.status_int = 403
        raise ApiError, "Not authorized"
        
    def _abort_not_found(self):
        response.status_int = 404
        raise ApiError, "Not found"
                    
    def _assert_is_found(self, entity):
        if entity is None:
            self._abort_not_found()

    def _assert_authorization_credentials(self, entity=None):
        user = self._get_user_for_apikey()
        if not user:
            log.info('User did not supply authorization credentials when required.')
            self._abort_not_authorized()

    def package_create(self):
        try:
            api_url = config.get('ckan.api_url', '/').rstrip('/')
            c.package_create_slug_api_url = api_url+h.url_for(controller='apiv2/package', action='create_slug')
            # Get the fieldset.
            fieldset = self._get_package_fieldset()
            if request.method == 'GET':
                # Bind entity to fieldset.
                #bound_fieldset = fieldset.bind()
                # Render the fields.
                fieldset_html = fieldset.render()
                # Set response body.
                response_body = fieldset_html
                # Set status code.
                response.status_int = 200
                # Return the response body.
                return response_body
            if request.method == 'POST':
                # Check user authorization.
                self._assert_authorization_credentials()
                # Read request.
                try:
                    request_data = self._get_request_data()
                except ValueError, error:
                    self._abort_bad_request('Extracting request data: %r' % error.args)                
                try:
                    form_data = request_data['form_data']
                except KeyError, error:
                    self._abort_bad_request('Missing \'form_data\' in request data.')
                # Bind form data to fieldset.
                try:
                    bound_fieldset = fieldset.bind(model.Package, data=form_data, session=model.Session)
                except Exception, error:
                    log.error('Package create - problem binding data. data=%r fieldset=%r', form_data, fields)
                    self._abort_bad_request('Form data incomplete')
                # Validate and save form data.
                log_message = request_data.get('log_message', 'Form API')
                user = self._get_user_for_apikey()
                author = user.name
                try:
                    WritePackageFromBoundFieldset(
                        fieldset=bound_fieldset,
                        log_message=log_message, 
                        author=author,
                        client=c, 
                    )
                except ValidationException, exception:
                    # Get the errorful fieldset.
                    errorful_fieldset = exception.args[0]
                    # Render the fields.
                    fieldset_html = errorful_fieldset.render()
                    # Set response body.
                    response_body = fieldset_html
                    # Set status code.
                    response.status_int = 400
                    log.info('Package create - data did not validate. user=%r data=%r error=%r', user.name, form_data, errorful_fieldset.errors)
                    # Return response body.
                    return response_body
                else:
                    # Retrieve created pacakge.
                    package = bound_fieldset.model
                    # Construct access control entities.
                    self._create_permissions(package, user)
                    # Log message
                    log.info('Package create successful. user=%r data=%r', author, form_data)
                    # Set the Location header.
                    location = self._make_package_201_location(package)
                    self._set_response_header('Location', location)
                    # Set response body.
                    response_body = json.dumps('')
                    # Set status code.
                    response.status_int = 201
                    # Return response body.
                    return response_body
        except ApiError, api_error:
            log.info('Package create - ApiError. user=%r data=%r error=%r',
                     author if 'author' in dir() else None,
                     form_data if 'form_data' in dir() else None,
                     api_error)
            # Set response body.
            response_body = str(api_error) 
            # Assume status code is set.
            # Return response body.
            return response_body
        except Exception:
            # Log error.
            log.error('Package create - unhandled exception: exception=%r', traceback.format_exc())
            raise

    def _make_package_201_location(self, package):
        location = '/api'
        location += self._make_version_part()
        package_ref = self._ref_package(package)
        location += '/rest/package/%s' % package_ref
        return location

    def _make_harvest_source_201_location(self, harvest_source):
        location = '/api'
        location += self._make_version_part()
        source_ref = self._ref_harvest_source(harvest_source)
        location += '/rest/harvestsource/%s' % source_ref
        return location

    def _make_version_part(self):
        part = ''
        is_version_in_path = False
        path_parts = request.path.split('/')
        if path_parts[2] == self.api_version:
            is_version_in_path = True
        if is_version_in_path:
            part = '/%s' % self.api_version
        return part

    def _set_response_header(self, name, value):
        try:
            value = str(value)
        except Exception, inst:
            msg = "Couldn't convert '%s' header value '%s' to string: %s" % (name, value, inst)
            raise Exception, msg
        response.headers[name] = value

    def _set_response_header(self, name, value):
        try:
            value = str(value)
        except Exception, inst:
            msg = "Couldn't convert '%s' header value '%s' to string: %s" % (name, value, inst)
            raise Exception, msg
        response.headers[name] = value

    def package_edit(self, id):
        try:
            # Find the entity.
            pkg = self._get_pkg(id)
            self._assert_is_found(pkg)
            # Get the fieldset.
            fieldset = self._get_package_fieldset()
            if request.method == 'GET':
                # Bind entity to fieldset.
                bound_fieldset = fieldset.bind(pkg)
                # Render the fields.
                fieldset_html = bound_fieldset.render()
                # Set response body.
                response_body = fieldset_html
                # Set status code.
                response.status_int = 200
                # Return the response body.
                return response_body
            if request.method == 'POST':
                # Check user authorization.
                self._assert_authorization_credentials()
                # Read request.
                try:
                    request_data = self._get_request_data()
                except ValueError, error:
                    self._abort_bad_request('Extracting request data: %r' % error.args)
                try:
                    form_data = request_data['form_data']
                except KeyError, error:
                    self._abort_bad_request('Missing \'form_data\' in request data.')
                # Bind form data to fieldset.
                try:
                    bound_fieldset = fieldset.bind(pkg, data=form_data)
                    # Todo: Replace 'Exception' with bind error.
                except Exception, error:
                    log.error('Package edit - problem binding data. data=%r fieldset=%r', form_data, fields)
                    self._abort_bad_request('Form data incomplete')
                # Validate and save form data.
                log_message = request_data.get('log_message', 'Form API')
                author = request_data.get('author', '')
                if not author:
                    user = self._get_user_for_apikey()
                    if user:
                        author = user.name
                try:
                    WritePackageFromBoundFieldset(
                        fieldset=bound_fieldset,
                        log_message=log_message, 
                        author=author,
                        client=c,
                    )
                except ValidationException, exception:
                    # Get the errorful fieldset.
                    errorful_fieldset = exception.args[0]
                    # Render the fields.
                    fieldset_html = errorful_fieldset.render()
                    # Set response body.
                    response_body = fieldset_html
                    # Set status code.
                    response.status_int = 400
                    log.info('Package edit - data did not validate. user=%r data=%r error=%r', author, form_data, errorful_fieldset.errors)
                    # Return response body.
                    return response_body
                else:
                    log.info('Package edit successful. user=%r data=%r', author, form_data)
                    # Set response body.
                    response_body = json.dumps('')
                    # Set status code.
                    response.status_int = 200
                    # Return response body.
                    return response_body
        except ApiError, api_error:
            log.info('Package edit - ApiError. user=%r data=%r error=%r',
                     author if 'author' in dir() else None,
                     form_data if 'form_data' in dir() else None,
                     api_error)
            # Set response body.
            response_body = str(api_error) 
            # Assume status code is set.
            # Return response body.
            return response_body
        except Exception:
            # Log error.
            log.error('Package edit - unhandled exception: exception=%r', traceback.format_exc())
            raise

    def _create_harvest_source_entity(self, bound_fieldset, user_ref=None, publisher_ref=None):
        bound_fieldset.validate()
        if bound_fieldset.errors:
            raise ValidationException(bound_fieldset)
        bound_fieldset.sync()
        model.Session.commit()

    def _create_permissions(self, package, user):
        model.setup_default_user_roles(package, [user])
        model.repo.commit_and_remove()

    def _update_harvest_source_entity(self, id, bound_fieldset, user_ref, publisher_ref):
        bound_fieldset.validate()
        if bound_fieldset.errors:
            raise ValidationException(bound_fieldset)
        bound_fieldset.sync()
        model.Session.commit()

    def package_create_example(self):
        client_user = self._get_user(u'tester')
        api_key = client_user.apikey
        self.ckan_client = self._start_ckan_client(api_key=api_key)
        if request.method == 'GET':
            fieldset_html = self.ckan_client.package_create_form_get()
            if fieldset_html == None:
                raise Exception, "Can't read package create form??"
            form_html = '<form action="" method="post">' + fieldset_html + '<input type="submit"></form>'
        else:
            form_data = request.params.items()
            request_data = {
                'form_data': form_data,
                'log_message': 'Package create example...',
                'author': 'automated test suite',
            }
            form_html = self.ckan_client.package_create_form_post(request_data)
            if form_html == '""':
                form_html = "Submitted OK"
        page_html = '<html><head><title>My Package Create Page</title></head><body><h1>My Package Create Form</h1>%s</html>' % form_html
        return page_html

    def package_edit_example(self, id):
        client_user = self._get_user(u'tester')
        api_key = client_user.apikey
        self.ckan_client = self._start_ckan_client(api_key=api_key)
        if request.method == 'GET':
            fieldset_html = self.ckan_client.package_edit_form_get(id)
            if fieldset_html == None:
                raise Exception, "Can't read package edit form??"
            form_html = '<form action="" method="post">' + fieldset_html + '<input type="submit"></form>'
        else:
            form_data = request.params.items()
            request_data = {
                'form_data': form_data,
                'log_message': 'Package edit example...',
                'author': 'automated test suite',
            }
            form_html = self.ckan_client.package_edit_form_post(id, request_data)
            if form_html == '""':
                form_html = "Submitted OK"
        page_html = '<html><head><title>My Package Edit Page</title></head><body><h1>My Package Edit Form</h1>%s</html>' % form_html
        return page_html

    def _start_ckan_client(self, api_key, base_location='http://127.0.0.1:5000/api'):
        import ckanclient
        return ckanclient.CkanClient(base_location=base_location, api_key=api_key)

    def harvest_source_create(self):
        try:
            # Get the fieldset.
            fieldset = ckan.forms.get_harvest_source_fieldset()
            if request.method == 'GET':
                # Render the fields.
                fieldset_html = fieldset.render()
                # Set response body.
                response_body = fieldset_html
                # Set status code.
                response.status_int = 200
                # Return the response body.
                return response_body
            if request.method == 'POST':
                # Check user authorization.
                self._assert_authorization_credentials()
                # Read request.
                try:
                    request_data = self._get_request_data()
                except ValueError, error:
                    self._abort_bad_request('Extracting request data: %r' % error.args)                                    
                try:
                    form_data = request_data['form_data']
                    user_ref = request_data['user_ref']
                    publisher_ref = request_data['publisher_ref']
                except KeyError, error:
                    self._abort_bad_request()
                # Bind form data to fieldset.
                try:
                    bound_fieldset = fieldset.bind(model.HarvestSource, data=form_data, session=model.Session)
                except Exception, error:
                    # Todo: Replace 'Exception' with bind error.
                    self._abort_bad_request()
                # Validate and save form data.
                try:
                    self._create_harvest_source_entity(bound_fieldset, user_ref=user_ref, publisher_ref=publisher_ref)
                except ValidationException, exception:
                    # Get the errorful fieldset.
                    errorful_fieldset = exception.args[0]
                    # Render the fields.
                    fieldset_html = errorful_fieldset.render()
                    # Set response body.
                    response_body = fieldset_html
                    # Set status code.
                    response.status_int = 400
                    # Return response body.
                    return response_body
                else:
                    # Retrieve created harvest source entity.
                    source = bound_fieldset.model
                    # Set and store the non-form object attributes.
                    source.user_ref = user_ref
                    source.publisher_ref = publisher_ref
                    model.Session.add(source)
                    model.Session.commit()
                    # Set the response's Location header.
                    location = self._make_harvest_source_201_location(source)
                    self._set_response_header('Location', location)
                    # Set response body.
                    response_body = json.dumps('')
                    # Set status code.
                    response.status_int = 201
                    # Return response body.
                    return response_body
        except ApiError, api_error:
            # Set response body.
            response_body = str(api_error) 
            # Assume status code is set.
            # Return response body.
            return response_body
        except Exception:
            # Log error.
            log.error("Couldn't run create harvest source form method: %s" % traceback.format_exc())
            raise
        
    def harvest_source_edit(self, id):
        try:
            # Find the entity.
            entity = self._get_harvest_source(id)
            self._assert_is_found(entity)
            # Get the fieldset.
            fieldset = ckan.forms.get_harvest_source_fieldset()
            if request.method == 'GET':
                # Bind entity to fieldset.
                bound_fieldset = fieldset.bind(entity)
                # Render the fields.
                fieldset_html = bound_fieldset.render()
                # Set response body.
                response_body = fieldset_html
                # Set status code.
                response.status_int = 200
                # Return the response body.
                return response_body
            if request.method == 'POST':
                # Check user authorization.
                self._assert_authorization_credentials()
                # Read request.
                try:
                    request_data = self._get_request_data()
                except ValueError, error:
                    self._abort_bad_request('Extracting request data: %r' % error.args)                                    
                try:
                    form_data = request_data['form_data']
                    user_ref = request_data['user_ref']
                    publisher_ref = request_data['publisher_ref']
                except KeyError, error:
                    self._abort_bad_request()
                # Bind form data to fieldset.
                try:
                    bound_fieldset = fieldset.bind(entity, data=form_data)
                    # Todo: Replace 'Exception' with bind error.
                except Exception, error:
                    self._abort_bad_request()
                # Validate and save form data.
                log_message = request_data.get('log_message', 'Form API')
                author = request_data.get('author', '')
                if not author:
                    user = self._get_user_for_apikey()
                    if user:
                        author = user.name
                try:
                    self._update_harvest_source_entity(id, bound_fieldset, user_ref=user_ref, publisher_ref=publisher_ref)
                except ValidationException, exception:
                    # Get the errorful fieldset.
                    errorful_fieldset = exception.args[0]
                    # Render the fields.
                    fieldset_html = errorful_fieldset.render()
                    # Set response body.
                    response_body = fieldset_html
                    # Set status code.
                    response.status_int = 400
                    # Return response body.
                    return response_body
                else:
                    # Retrieve created harvest source entity.
                    source = bound_fieldset.model
                    # Set and store the non-form object attributes.
                    source.user_ref = user_ref
                    source.publisher_ref = publisher_ref
                    model.Session.add(source)
                    model.Session.commit()
                    # Set response body.
                    response_body = json.dumps('')
                    # Set status code.
                    response.status_int = 200
                    # Return response body.
                    return response_body
        except ApiError, api_error:
            # Set response body.
            response_body = str(api_error) 
            # Assume status code is set.
            # Return response body.
            return response_body
        except Exception:
            # Log error.
            log.error("Couldn't update harvest source: %s" % traceback.format_exc())
            raise

class FormController(ApiVersion1, BaseFormController): pass
 
