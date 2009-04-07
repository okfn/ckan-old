from ckan.lib.base import *
from ckan.controllers.base import CkanBaseController

class HomeController(CkanBaseController):
    repo = model.repo

    def index(self):
        c.package_count = model.Package.query.count()
        return render('home')

    def license(self):
        return render('license')
    
    def guide(self):
        ckan_pkg = model.Package.by_name('ckan')
        if ckan_pkg:
            c.info = ckan_pkg.notes
        else:
            c.info = ''
        return render('guide')

