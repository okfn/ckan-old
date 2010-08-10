from ckan.lib.base import *
from ckan.lib.helpers import json
import ckan.forms
import ckan.controllers.package
from ckan.lib.package_saver import PackageSaver
from ckan.lib.package_saver import ValidationException

class ApiError(Exception): pass

# Todo: Create controller for testing package edit form (but try to disable for production usage).
# Todo: Refactor forms handling logic (to share common line between forms and edit).
# Todo: Remove superfluous commit_pkg() method parameter.
# Todo: Support setting choices (populates form input options and constrains validation)? Actually, perhaps groups shouldn't be editable on packages?

class FormController(BaseController):
    """Implements the CKAN Forms API."""

    def _abort_bad_request(self):
        response.status_int = 400
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

    def _assert_is_authorized(self, entity):
        user = self._get_user_for_apikey()
        if not user:
           self._abort_not_authorized()

    def package_edit(self, id):
        try:
            # Find the entity.
            pkg = self._get_pkg(id)
            self._assert_is_found(pkg)
            # Get the fieldset.
            fieldset = ckan.forms.registry.get_fieldset()
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
                self._assert_is_authorized(pkg)
                # Read request.
                request_data = self._get_request_data()
                try:
                    form_data = request_data['form_data']
                except KeyError, error:
                    self._abort_bad_request()
                # Bind form data to fieldset.
                # Todo: Replace 'Exception' with bind error.
                try:
                    bound_fieldset = fieldset.bind(pkg, data=form_data)
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
                    self._save_package(id, bound_fieldset, log_message, author)
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
                    # Set the Location header.
                    location = '/forms'
                    response.headers['Location'] = location
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
            # Set response body.
            response_body = "Internal server error"
            # Set status code.
            response.status_int = 500
            # Return response body.
            return response_body

    def _save_package(self, id, bound_fieldset, log_message, author):
        # Superfluous commit_pkg() method parameter.
        superfluous = None # Value is never consumed.
        PackageSaver().commit_pkg(bound_fieldset, superfluous, id, log_message, author) 

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

