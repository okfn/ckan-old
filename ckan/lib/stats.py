import datetime

from pylons import config
from sqlalchemy import *

from ckan import model

ENABLE_CACHING = bool(config.get('enable_caching', ''))
if ENABLE_CACHING:
    from pylons import cache
    our_cache = cache.get_cache('stats', type='dbm')
DATE_FORMAT = '%Y-%m-%d'

def table(name):
    return Table(name, model.metadata, autoload=True)

def datetime2date(datetime_):
    return datetime.date(datetime_.year, datetime_.month, datetime_.day)


class Stats(object):
    @classmethod
    def top_rated_packages(self, limit=10):
        # NB Not using sqlalchemy as sqla 0.4 doesn't work using both group_by
        # and apply_avg
        #         SELECT package.id AS package_id, AVG(rating.rating) FROM package
        #         JOIN rating ON package.id = rating.package_id
        #         GROUP BY package.id
        #         ORDER BY AVG(rating.rating) DESC
        #         LIMIT 10
        package = table('package')
        rating = table('rating')
        sql = select([package.c.id, func.avg(rating.c.rating)], from_obj=[package.join(rating)]).\
              group_by(package.c.id).\
              order_by(func.avg(rating.c.rating).desc()).\
              limit(limit)
        res_ids = model.Session.execute(sql).fetchall()
        res_pkgs = [(model.Session.query(model.Package).get(unicode(pkg_id)), avg) for pkg_id, avg in res_ids]
        return res_pkgs
            
    @classmethod
    def most_edited_packages(self, limit=10):
        package_revision = table('package_revision')
        s = select([package_revision.c.id, func.count(package_revision.c.revision_id)]).\
            group_by(package_revision.c.id).\
            order_by(func.count(package_revision.c.revision_id).desc()).\
            limit(limit)
        res_ids = model.Session.execute(s).fetchall()        
        res_pkgs = [(model.Session.query(model.Package).get(unicode(pkg_id)), val) for pkg_id, val in res_ids]
        return res_pkgs
        
    @classmethod
    def largest_groups(self, limit=10):
        package_group = table('package_group')
        s = select([package_group.c.group_id, func.count(package_group.c.package_id)]).\
            group_by(package_group.c.group_id).\
            order_by(func.count(package_group.c.package_id).desc()).\
            limit(limit)
        res_ids = model.Session.execute(s).fetchall()        
        res_groups = [(model.Session.query(model.Group).get(unicode(group_id)), val) for group_id, val in res_ids]
        return res_groups

    @classmethod
    def top_tags(self, limit=10, returned_tag_info='object'): # by package
        assert returned_tag_info in ('name', 'id', 'object')
        tag = table('tag')
        package_tag = table('package_tag')
        #TODO filter out tags with state=deleted
        if returned_tag_info == 'name':
            from_obj = [package_tag.join(tag)]
            tag_column = tag.c.name
        else:
            from_obj = None
            tag_column = package_tag.c.tag_id
        s = select([tag_column, func.count(package_tag.c.package_id)],
                    from_obj=from_obj)
        s = s.group_by(tag_column).\
            order_by(func.count(package_tag.c.package_id).desc()).\
            limit(limit)
        res_col = model.Session.execute(s).fetchall()
        if returned_tag_info in ('id', 'name'):
            return res_col
        elif returned_tag_info == 'object':
            res_tags = [(model.Session.query(model.Tag).get(unicode(tag_id)), val) for tag_id, val in res_col]
            return res_tags
        
    @classmethod
    def top_package_owners(self, limit=10):
        package_role = table('package_role')
        user_object_role = table('user_object_role')
        s = select([user_object_role.c.user_id, func.count(user_object_role.c.role)], from_obj=[user_object_role.join(package_role)]).\
            where(user_object_role.c.role==model.authz.Role.ADMIN).\
            group_by(user_object_role.c.user_id).\
            order_by(func.count(user_object_role.c.role).desc()).\
            limit(limit)
        res_ids = model.Session.execute(s).fetchall()        
        res_users = [(model.Session.query(model.User).get(unicode(user_id)), val) for user_id, val in res_ids]
        return res_users

class RevisionStats(object):
    @classmethod
    def package_addition_rate(self, weeks_ago=0):
        week_commenced = self.get_date_weeks_ago(weeks_ago)
        return self.get_new_packages_by_time(week_commenced,
                                             type='new_package_rate')

    @classmethod
    def package_revision_rate(self, weeks_ago=0):
        dates = self.get_week_dates(weeks_ago)
        return self.get_revision_rate(dates)

    @classmethod
    def get_date_weeks_ago(self, weeks_ago):
        '''
        @param weeks_ago: specify how many weeks ago to give count for
                          (0 = this week so far)
        '''
        date_ = datetime.date.today()
        return date_ - datetime.timedelta(days=
                             datetime.date.weekday(date_) + 7 * weeks_ago)

    @classmethod
    def get_week_dates(self, weeks_ago):
        '''
        @param weeks_ago: specify how many weeks ago to give count for
                          (0 = this week so far)
        '''
        package_revision = table('package_revision')
        revision = table('revision')
        today = datetime.date.today()
        date_from = datetime.datetime(today.year, today.month, today.day) -\
                    datetime.timedelta(days=datetime.date.weekday(today) + \
                                       7 * weeks_ago)
        date_to = date_from + datetime.timedelta(days=7)
        return (date_from, date_to)

    @classmethod
    def get_date_week_started(self, date_):
        assert isinstance(date_, datetime.date)
        if isinstance(date_, datetime.datetime):
            date_ = datetime2date(date_)
        return date_ - datetime.timedelta(days=datetime.date.weekday(date_))


    @classmethod
    def get_revision_rate(self, dates):
        package_revision = table('package_revision')
        revision = table('revision')
        date_from, date_to = dates
        q = model.Session.query(model.PackageRevision).select_from(package_revision.join(revision)).filter(revision.c.timestamp < date_to).filter(revision.c.timestamp > date_from)
        return q.count()

    @classmethod
    def get_new_packages(self):
        def new_packages():
            # Can't filter by time in select because 'min' function has to
            # be 'for all time' else you get first revision in the time period.
            package_revision = table('package_revision')
            revision = table('revision')
            s = select([package_revision.c.id, func.min(revision.c.timestamp)], from_obj=[package_revision.join(revision)]).group_by(package_revision.c.id).order_by(func.min(revision.c.timestamp))
            return model.Session.execute(s).fetchall()
        # 3600=hourly, 86400=daily, 604800=weekly
        if ENABLE_CACHING:
            week_commences = get_date_week_started(datetime.date.today())
            key = 'all_new_packages_%s' + week_commences.strftime(DATE_FORMAT)
            new_packages = our_cache.get_value(key=key,
                                               createfunc=new_packages)
        else:
            new_packages = new_packages()
        return new_packages

    @classmethod
    def get_new_packages_by_week(self):
        def new_packages_by_week():
            new_packages = self.get_new_packages()
            first_date = new_packages[0][1] if new_packages else datetime.date.today()
            week_commences = self.get_date_week_started(first_date)
            week_ends = week_commences + datetime.timedelta(days=7)
            week_index = 0
            weekly_pkg_ids = [] # [(week_commences, [pkg_id1, pkg_id2, ...])]
            pkg_id_stack = []
            for pkg_id, datetime_ in new_packages:
                date_ = datetime2date(datetime_)
                if date_ >= week_ends:
                    weekly_pkg_ids.append((week_commences.strftime(DATE_FORMAT), pkg_id_stack))
                    pkg_id_stack = []
                    week_commences = week_ends
                    week_ends = week_commences + datetime.timedelta(days=7)
                pkg_id_stack.append(pkg_id)
            weekly_pkg_ids.append((week_commences.strftime(DATE_FORMAT), pkg_id_stack))
            today = datetime.date.today()
            while week_ends < today:
                week_commences = week_ends
                week_ends = week_commences + datetime.timedelta(days=7)
                weekly_pkg_ids.append((week_commences.strftime(DATE_FORMAT), []))
            return weekly_pkg_ids
        if ENABLE_CACHING:
            week_commences = get_date_week_started(datetime.date.today())
            key = 'new_packages_by_week_%s' + week_commences.strftime(DATE_FORMAT)
            new_packages_by_week_ = our_cache.get_value(key=key,
                                                       createfunc=new_packages_by_week)
        else:
            new_packages_by_week_ = new_packages_by_week()
        return new_packages_by_week_
        
    @classmethod
    def get_new_packages_by_time(self, date_week_commences,
                                 type='new-package-rate'):
        '''
        @param type: "new_package_rate" returns number of new packages during
                     the date range. "new_packages" returns a list of the
                     packages created in the date range in a tuple with the
                     date.
        @param dates: date range of interest - a tuple:
                     (start_date, end_date)
        '''
        assert isinstance(date_week_commences, datetime.date)
        new_pkgs_by_week = self.get_new_packages_by_week()
        date_wc_str = date_week_commences.strftime(DATE_FORMAT)
        pkg_ids = dict(new_pkgs_by_week)[date_wc_str]
        if type == 'new_package_rate':
            return len(pkg_ids)
        elif type == 'revisions':
            return [ model.Session.query(model.Package).get(pkg_id) \
                     for pkg_id in pkg_ids ]
        else:
            raise NotImplementedError()
