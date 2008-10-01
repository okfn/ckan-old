import py.test

# needed for config to be set and db access to work
import ckan.tests
import ckan.exceptions
import ckan.model as model

from datetime import datetime

class TestLicense:
    name = u'testlicense'

    @classmethod
    def teardown_class(self):
        lic = model.License.by_name(self.name)
        lic.purge()
        model.Session.commit()

    def test_license(self):
        license = model.License(name=self.name)
        assert license in model.Session
        model.Session.flush()
        model.Session.clear()
        exp = model.License.by_name(self.name)
        assert exp.name == self.name


class TestPackage:

    @classmethod
    def setup_class(self):
        self.name = u'geodata'
        self.notes = u'Written by Puccini'
        pkgs = model.Package.query.filter_by(name=self.name).all()
        for p in pkgs:
            p.purge()
        model.Session.commit()

        rev = model.new_revision()
        self.pkg1 = model.Package(name=self.name)
        self.pkg1.notes = self.notes
        self.license_name = u'OKD Compliant::Other'
        license = model.License.by_name(self.license_name)
        self.pkg1.license = license
        model.Session.commit()
        model.Session.remove()

    def teardown_class(self):
        pkg1 = model.Package.query.filter_by(name=self.name).one()
        pkg1.purge()
        model.Session.commit()
        model.Session.remove()

    def test_create_package(self):
        out = model.Package.by_name(self.name)
        assert out.name == self.name
        assert out.notes == self.notes
        assert out.license.name == self.license_name

    def test_update_package(self):
        newnotes = 'Written by Beethoven'
        author = 'jones'

        rev2 = model.new_revision()
        pkg = model.Package.by_name(self.name)
        pkg.notes = newnotes
        rev2.author = 'jones'
        model.Session.commit()
        model.Session.clear()
        outpkg = model.Package.by_name(self.name)
        assert outpkg.notes == newnotes
        assert len(outpkg.all_revisions) > 0
        assert outpkg.all_revisions[-1].revision.author == author


class TestPackageWithTags:
    """
    WARNING: with sqlite these tests may fail (depending on the order they are
    run in) as sqlite does not support ForeignKeys properly.
    """

    def setup_class(self):
        # use this when things get fouled up ...
        # model.rebuild_db()
        rev1 = model.new_revision()
        self.tagname = u'testtagm2m'
        self.tagname2 = u'testtagm2m2'
        self.tagname3 = u'testtag3'
        self.pkgname = u'testpkgm2m'
        pkg = model.Package(name=self.pkgname)
        self.tag = model.Tag(name=self.tagname)
        self.tag2 = model.Tag(name=self.tagname2)
        pkg2tag = model.PackageTag(package=pkg, tag=self.tag)
        pkg.tags.append(self.tag2)
        model.Session.commit()
        self.pkg2tag_id = pkg2tag.id
        self.rev = rev1

    def teardown_class(self):
        # should only be one but maybe things have gone wrong
        # p = model.Package.by_name(self.pkgname)
        pkgs = model.Package.query.filter_by(name=self.pkgname)
        for p in pkgs:
            for pt in p.package_tags:
                pt.purge()
            p.purge()
        t1 = model.Tag.by_name(self.tagname)
        t1.purge()
        t2 = model.Tag.by_name(self.tagname2)
        t2.purge()
        t3 = model.Tag.by_name(self.tagname3)
        t3.purge()
        model.Session.commit()

    def test_1(self):
        pkg = model.Package.by_name(self.pkgname)
        assert len(pkg.tags) == 2
        # pkg2tag = model.PackageTag.query.get(self.pkg2tag_id)
        # assert pkg2tag.package.name == self.pkgname

    def test_tags(self):
        pkg = model.Package.by_name(self.pkgname)
        # TODO: go back to this
        # 2 default packages each with 2 tags so we have 2 + 4
        all = model.Tag.query.all() 
        assert len(all) == 2

    def test_add_tag_by_name(self):
        rev = model.new_revision()
        pkg = model.Package.by_name(self.pkgname)
        pkg.add_tag_by_name(self.tagname3)
        model.Session.commit()
        model.Session.clear()
        outpkg = model.Package.by_name(self.pkgname)
        assert len(outpkg.tags) == 3
        t1 = model.Tag.by_name(self.tagname)
        assert len(t1.package_tags) == 1

    def test_add_tag_by_name_existing(self):
        model.Session.clear()
        pkg = model.Package.by_name(self.pkgname)
        assert len(pkg.tags) == 3
        pkg.add_tag_by_name(self.tagname)
        assert len(pkg.tags) == 3
    

class TestPackageWithLicense:

    def setup_class(self):
        # use this when things get fouled up ...
        # model.rebuild_db()
        self.licname1 = 'test_license1'
        self.licname2 = 'test_license2'
        self.license1 = model.License(name=self.licname1)
        self.license2 = model.License(name=self.licname2)
        rev = model.new_revision()
        self.pkgname = 'testpkgfk'
        pkg = model.Package(name=self.pkgname)
        pkg.license = self.license1
        model.Session.commit()
        self.rev1id = rev.id
        model.Session.remove()

        rev = model.new_revision()
        pkg = model.Package.by_name(self.pkgname)
        pkg.license = self.license2
        model.Session.commit()
        self.rev2id = rev.id
        model.Session.remove()

    def teardown_class(self):
        model.Session.clear()
        pkg = model.Package.by_name(self.pkgname)
        pkg.purge()
        lic1 = model.License.by_name(self.licname1)
        lic2 = model.License.by_name(self.licname2)
        lic1.purge()
        lic2.purge()
        model.Session.commit()
 
    def test_set1(self):
        rev = model.Revision.query.get(self.rev1id)
        pkg = model.Package.by_name(self.pkgname)
        pkgrev = pkg.get_as_of(rev)
        out = pkgrev.license.name 
        assert out == self.licname1

    def test_set2(self):
        pkg = model.Package.by_name(self.pkgname)
        out = pkg.license.name 
        assert out == self.licname2

class TestTag:

    def setup_class(self):
        model.Session.clear()
        model.Session.begin()
        model.Tag(name='russian')
        model.Tag(name='something')

    def teardown_class(self):
        model.Session.rollback()
        model.Session.remove()

    def test_search_1(self):
        out = list(model.Tag.search_by_name('russian'))
        assert len(out) == 1
        assert out[0].name == 'russian'

    def test_search_2(self):
        out = list(model.Tag.search_by_name('us'))
        assert len(out) == 1

    def test_search_3(self):
        out = list(model.Tag.search_by_name('s'))
        assert len(out) == 2
