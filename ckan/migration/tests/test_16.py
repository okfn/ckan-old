from ckan.migration.tests import *

def _test_anna():
    from ckan import model
    anna = model.Package.by_name(u'annakarenina')
    assert anna.title == u'A Novel By Tolstoy', anna.title
    assert isinstance(anna.id, unicode), repr(anna.id)
    assert len(anna.resources) == 2, anna.resources
    assert anna.resources[0].url == u'http://www.annakarenina.com/download/x=1&y=2', anna.resources[0].url
    assert 'russian' in str(anna.tags), anna.tags
    assert 'OKD Compliant::Other' in str(anna.license), anna.license
    assert anna.extras['genre'] == 'romantic novel', anna.extras
    assert anna in anna.tags[0].packages, anna.tags[0].packages
    pkg_rev = model.Session.query(model.PackageRevision).get((anna.id, anna.revision.id))
    assert pkg_rev
    assert pkg_rev.name == anna.name


class Test_0_Empty(TestMigrationBase):
    @classmethod
    def setup_class(cls):
        cls.paster('db clean')
        cls.paster('db upgrade')
        cls.paster('db init')
        cls.paster('create-test-data')

    @classmethod
    def teardown_class(cls):
        from ckan import model
        model.Session.close()

    def test_package_count(self):        
        from ckan import model
        pkg_query = model.Session.query(model.Package)
        num_pkgs = pkg_query.count()
        assert num_pkgs == 2, pkg_query.all()

    def test_package_details(self):
        _test_anna()


class Test_1_BasicData(TestMigrationBase):
    @classmethod
    def setup_class(cls):
        cls.setup_db(os.path.join(TEST_DUMPS_PATH, 'test_data_15.pg_dump'))
        cls.paster('db upgrade')

    @classmethod
    def teardown_class(cls):
        from ckan import model
        model.Session.close()

    def test_package_count(self):        
        from ckan import model
        pkg_query = model.Session.query(model.Package)
        num_pkgs = pkg_query.count()
        assert num_pkgs == 2, pkg_query.all()

    def test_package_details(self):
        _test_anna()
        
    def test_ids(self):
        from ckan import model
        uuid_length = 36
        obj = model.Session.query(model.Package).first()
        assert len(obj.id) == uuid_length, obj.id
        obj = model.Session.query(model.Tag).first()
        assert len(obj.id) == uuid_length, obj.id
        obj = model.Session.query(model.PackageTag).first()
        assert len(obj.id) == uuid_length, obj.id
        obj = model.Session.query(model.PackageExtra).first()
        assert len(obj.id) == uuid_length, obj.id
        obj = model.Session.query(model.PackageRevision).first()
        assert len(obj.id) == uuid_length, obj.id
        obj = model.Session.query(model.PackageTagRevision).first()
        assert len(obj.id) == uuid_length, obj.id
        obj = model.Session.query(model.PackageExtraRevision).first()
        assert len(obj.id) == uuid_length, obj.id

        
class Test_2_RealData(TestMigrationBase):
    @classmethod
    def setup_class(cls):
        cls.paster('db clean')
        cls.setup_db()
        cls.paster('db upgrade')
        # pass

    def test_ckan_net(self):
        from ckan import model
        pkg = model.Package.by_name(u'osm')
        assert pkg.title == u'Open Street Map', pkg.title
        assert isinstance(pkg.id, unicode), repr(pkg.id)
        assert len(pkg.resources) == 1, pkg.resources
        assert pkg.resources[0].url == u'http://wiki.openstreetmap.org/index.php/Planet.osm', pkg.resources[0].url
        assert 'navigation' in str(pkg.tags), pkg.tags
        assert 'OKD Compliant::Creative Commons Attribution-ShareAlike' in str(pkg.license), pkg.license
        assert pkg.extras == {}, pkg.extras
        assert pkg in pkg.tags[0].packages, pkg.tags[0].packages
        pkg_rev = model.Session.query(model.PackageRevision).get((pkg.id, pkg.revision.id))
        assert pkg_rev
        assert pkg_rev.name == pkg.name
        assert len(pkg.all_revisions) > 1
        for pkgrev in pkg.all_revisions:
            assert pkgrev.id == pkg.id

    def test_ckan_net_2(self):
        from ckan import model
        id_differences = False
        obj = model.PackageRevision
        out = model.Session.query(obj).filter(obj.id!=obj.continuity_id).all()
        assert len(out) == 0, out
        
        from sqlalchemy import sql
        out = model.Session.query(obj).filter(sql.func.length(obj.id)!=36).count()
        assert out == 0, out
        out = model.Session.query(obj).filter(sql.func.length(obj.continuity_id)!=36).count()
        assert out == 0, out

