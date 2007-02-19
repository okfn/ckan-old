from ckan.tests import *

class TestPackageController(TestControllerTwill):

    def _go_index(self):
        offset = url_for(controller='tag')
        url = self.siteurl + offset
        web.go(url)

    def test_index(self):
        self._go_index()
        web.code(200)
        web.title('Tags - Index')

    def test_read(self):
        name = 'tolstoy'
        pkgname = 'warandpeace'
        offset = url_for(controller='tag', action='read', id=name)
        url = self.siteurl + offset
        web.go(url)
        web.title('Tags - %s' % name)
        web.find(name)
        web.follow(pkgname)
        web.title('Packages - %s' % pkgname)

    def test_list(self):
        tagname = 'tolstoy'
        offset = url_for(controller='tag', action='list')
        url = self.siteurl + offset
        web.go(url)
        web.code(200)
        web.title('Tags - List')
        web.find(tagname)
        print web.show()
        web.find('\(2 packages\)')
        web.follow(tagname)
        web.code(200)
        web.title('Tags - %s' % tagname)

