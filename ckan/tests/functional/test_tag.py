from ckan.tests import *
import ckan.model as model

HTTP_MOVED_PERMANENTLY = 301

class TestTagController(TestController):

    @classmethod
    def setup_class(self):
        model.Session.remove()
        CreateTestData.create()

    @classmethod
    def teardown_class(self):
        CreateTestData.delete()

    def test_index(self):
        offset = url_for(controller='tag')
        res = self.app.get(offset)
        assert 'Tags' in res
        assert 'There are' in res

    def test_read_moved(self):
        name = 'tolstoy'
        offset = '/tag/read/%s' % name
        res = self.app.get(offset, status=HTTP_MOVED_PERMANENTLY)
        res = res.follow()
        assert '%s - Tags' % name in res
        assert name in res
        # res = res.click(pkgname)
        # assert '%s - Data Packages' % pkgname in res

    def test_read(self):
        name = 'tolstoy'
        pkgname = 'warandpeace'
        offset = url_for(controller='tag', action='read', id=name)
        assert offset == '/tag/tolstoy', offset
        res = self.app.get(offset)
        assert '%s - Tags' % name in res
        assert name in res
        # res = res.click(pkgname)
        # assert '%s - Data Packages' % pkgname in res

    def test_list_short(self):
        offset = url_for(controller='tag', action='index')
        res = self.app.get(offset)
        tagname = 'tolstoy'
        assert tagname in res
        #assert '(2 packages)' in res
        res = res.click(tagname)
        assert tagname in res
        offset = url_for(controller='tag', action='index')
        res = self.app.get(offset)
        assert tagname in res
        #assert '(2 packages)' in res
        tag_count = model.Session.query(model.Tag).count()
        assert 'There are <strong>%s</strong> results for tags.' % tag_count in res
        offset = url_for(controller='tag', action='index')
        res = self.app.get(offset)
        assert tagname in res
        tag_count = model.Session.query(model.Tag).count()
        assert 'There are <strong>%s</strong> results for tags.' % tag_count in res
        # Avoid interactions.
        offset = url_for(controller='tag', action='index')
    
    def test_search(self):
        offset = url_for(controller='tag', action='index', id=None)
        res = self.app.get(offset)
        search_term = 's'
        fv = res.forms['tag-search']
        fv['q'] =  str(search_term)
        res = fv.submit()
        assert 'There are <strong>2</strong> results' in res, res
        assert 'russian' in res, res
        assert 'tolstoy' in res, res

    def test_autocomplete(self):
        controller = 'apiv2/package'
        action = 'autocomplete'
        offset = url_for(controller=controller, action=action)
        res = self.app.get(offset)
        assert '[]' in res
        offset = url_for(controller=controller, action=action, incomplete='russian')
        res = self.app.get(offset)
        assert 'russian' in res
        assert 'tolstoy' not in res
        offset = url_for(controller=controller, action=action, incomplete='tolstoy')
        res = self.app.get(offset)
        assert 'russian' not in res
        assert 'tolstoy' in res

