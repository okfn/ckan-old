from ckan.tests import *

import ckan.commands.revision

import ckan.model as model

class _TestRevisionPurge:
    
    @classmethod
    def setup_class(self):
        model.Session.remove()
        CreateTestData.create()

    @classmethod
    def teardown_class(self):
        CreateTestData.delete()

    def setup_method(self, name=''):
        self.pkgname = u'revision-purge-test'

        model.repo.begin()
        self.pkg = model.Package(name=self.pkgname)
        self.old_url = u'abc.com'
        self.pkg.url = self.old_url
        tag1 = model.Tag.by_name(u'russian')
        tag2 = model.Tag.by_name(u'tolstoy')
        self.pkg.tags.append(tag1)
        self.pkg.tags.append(tag2)
        model.repo.commit()

        txn2 = model.repo.begin()
        pkg = model.Package.by_name(self.pkgname)
        newurl = u'blah.com'
        pkg.url = newurl
        pkg.tags = []
        self.pkgname2 = u'revision-purge-test-2'
        self.pkg_new = model.Package(name=self.pkgname2)
        model.Session.commit()
        model.Session.remove()

    def teardown_method(self, name=''):
        model.Session.remove()
        pkg_new = model.Package.by_name(self.pkgname2)
        if pkg_new:
            pkg_new.purge()
        pkg = model.Package.by_name(self.pkgname)
        pkg.purge()
        model.Session.commit()
        model.Session.remove()

    def test_1(self):
        rev = model.repo.youngest_revision()
        cmd = ckan.commands.revision.PurgeRevision(rev, leave_record=True)
        cmd.execute()

        rev = model.repo.youngest_revision()
        pkg = model.Package.by_name(self.pkgname)

        assert rev.message == 'PURGED'
        assert pkg.url == self.old_url
        pkg2 = model.Package.by_name(self.pkgname2)
        assert pkg2 is None, 'pkgname2 should no longer exist'
        # TODO: reinstate
        # assert len(pkg.tags) == 2

    def test_2(self):
        rev = model.repo.youngest_revision()
        num = rev.id
        cmd = ckan.commands.revision.PurgeRevision(rev, leave_record=False)
        cmd.execute()

        rev = model.repo.youngest_revision()
        assert rev.id < num

    def test_purge_first_revision(self):
        rev = model.repo.youngest_revision()
        num = rev.id
        rev2 = model.Revision.query.get(rev.id - 1)
        cmd = ckan.commands.revision.PurgeRevision(rev2, leave_record=False)
        cmd.execute()

        rev = model.repo.youngest_revision()
        assert rev.id == num
        # either none or should equal num - 2 or be None (if no lower revision)
        pkg = model.Package.by_name(self.pkgname)
        assert len(pkg.all_revisions) == 1

