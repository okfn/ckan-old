import sqlalchemy

from pylons import config

import ckan.model as model

from ckan import authz

ENABLE_CACHING = bool(config.get('enable_caching', ''))
LIMIT_DEFAULT = 20

if ENABLE_CACHING:
    from pylons import cache
    our_cache = cache.get_cache('search_results', type='dbm')

class SearchOptions:
    options = {
        # about the search
        'q':None,
        'entity':'package',
        'limit':LIMIT_DEFAULT,
        'offset':0,
        'filter_by_openness':False,
        'filter_by_downloadable':False,
        # about presenting the results
        'order_by':'rank',
        'return_objects':False,
        'ref_entity_with_attr':'name',
        'all_fields':False,
        'search_tags':False}
    # Any attributes set on this object, other than those in the 'options',
    # will be treated as field_specific_terms - terms searched for in the
    # specified field.
    # e.g. 'version' or 'url'

    @classmethod
    def get_option_name_set(self):
        if not hasattr(self, 'option_name_set'):
            self._option_name_set = set(self.options.keys())
        return self._option_name_set
    
    def __init__(self, kw_dict):
        # Note that the kw_dict may well be a UnicodeMultiDict so you may
        # have keys repeated.
        if not kw_dict.keys():
            raise Exception('no options supplied')

        # set values according to the defaults
        for option_name, default_value in self.options.items():
            setattr(self, option_name, default_value)

        # overwrite defaults with options passed in
        for k, v in kw_dict.items():
            if k in self.get_option_name_set():
                # Ensure boolean fields are boolean
                if k in ['filter_by_downloadable', 'filter_by_openness', 'all_fields']:
                    v = v == 1 or v
                # Ensure integer fields are integer
                if k in ['offset', 'limit']:
                    v = int(v)
            # Multiple tags params are added in list
            if hasattr(self, k) and k in ['tags', 'groups']:
                existing_val = getattr(self, k)
                if type(existing_val) == type([]):
                    v = existing_val + [v]
                else:
                    v = [existing_val, v]
            setattr(self, k, v)

    def __str__(self):
        return repr(self.__dict__)

class SQLSearch:
    # Note: all tokens must be in the search vector (see model/search_index.py)
    _open_licenses = None

    def search(self, query_string):
        '''For the given basic query string, returns query results.'''
        options = SearchOptions({'q':query_string})
        return self.run(options)

    def query(self, options, username=None):
        '''For the given search options, returns a query object.'''
        self._options = options
        general_terms, field_specific_terms = self._parse_query_string()

        # for case of no search terms, return nothing
        if not (general_terms or field_specific_terms):
            return None

        if self._options.entity == 'package':
            query = authz.Authorizer().authorized_query(username, model.Package)
            query = self._build_package_query(query, general_terms, field_specific_terms)
        elif self._options.entity == 'resource':
            query = self._build_resource_query(query, general_terms, field_specific_terms)
        elif self._options.entity == 'tag':
            if not general_terms:
                return None
            query = self._build_tags_query(general_terms)
        elif self._options.entity == 'group':
            if not general_terms:
                return None
            query = authz.Authorizer().authorized_query(username, model.Group)
            query = self._build_groups_query(query, general_terms)
        else:
            # error
            pass
        return query

    def run(self, options, username=None):
        '''For the given search options, returns query results.'''
        query = self.query(options, username)

        self._results = {}
        if not query:
            self._results['results'] = []
            self._results['count'] = 0
            return self._results

        self._run_query(query)
        self._format_results()
        return self._results

    def _parse_query_string(self):
        query_str = self._options.q
        
        # split query into terms
        # format: * double quotes enclose a single term. e.g. "War and Peace"
        #         * field:term or field:"longer term" means search only in that
        #           particular field for that term.
        terms = []
        if query_str:
            inside_quote = False
            buf = ''
            for ch in query_str:
                if ch == ' ' and not inside_quote:
                    if buf:
                        terms.append(buf.strip())
                    buf = ''
                elif ch == '"':
                    inside_quote = not inside_quote
                else:
                    buf += ch
            if buf:
                terms.append(buf)

        # split off field-specific terms
        field_specific_terms = {}
        general_terms = []
        for term in terms:
            
            # Look for 'token:' - is put into field_specific_terms dict
            token = None
            colon_pos = term.find(':')
            if colon_pos != -1:
                token = term[:colon_pos]
                term = term[colon_pos+1:]
                if term:
                    if not field_specific_terms.has_key(token):
                        field_specific_terms[token] = []
                    field_specific_terms[token].append(term)
            else:
                general_terms.append(term)

        # add other field-specific terms that have come in via the options
        for token, value in self._options.__dict__.items():
            if token not in SearchOptions.get_option_name_set():
                field_specific_terms[token] = value

        # special case - 'tags:' becomes a general term when searching
        # tag entities.
        if self._options.entity == 'tag' and field_specific_terms.has_key(u'tags'):
            general_terms.extend(field_specific_terms[u'tags'])
        
        
        return general_terms, field_specific_terms

    def _build_package_query(self, authorized_package_query,
                             general_terms, field_specific_terms):
        make_like = lambda x,y: x.ilike('%' + y + '%')
        query = authorized_package_query
        query = query.filter(model.package_search_table.c.package_id==model.Package.id)

        # Full search by general_terms (and field specific terms but not by field)
        terms_set = set()
        for term_list in field_specific_terms.values():
            if isinstance(term_list, (list, tuple)):
                for term in term_list:
                    terms_set.add(term)
            else:
                print term_list
                terms_set.add(term_list)
        for term in general_terms:
            terms_set.add(term)
        all_terms = ' '.join(terms_set)
        query = query.filter('package_search.search_vector '\
                                       '@@ plainto_tsquery(:terms)')
        query = query.params(terms=all_terms)
            
        # Filter by field_specific_terms
        for field, terms in field_specific_terms.items():
            if isinstance(terms, (str, unicode)):
                terms = terms.split()
            if field in ('tags', 'groups'):
                query = self._filter_by_tags_or_groups(field, query, terms)
            elif hasattr(model.Package, field):
                for term in terms:
                    model_attr = getattr(model.Package, field)
                    query = query.filter(make_like(model_attr, term))
            else:
                query = self._filter_by_extra(field, query, terms)

        # Filter for options
        if self._options.filter_by_downloadable:
            query = query.join('package_resources_all', aliased=True).\
                    filter(sqlalchemy.and_(
                model.PackageResource.state==model.State.ACTIVE,
                model.PackageResource.package_id==model.Package.id))
        if self._options.filter_by_openness:
            if self._open_licenses is None:
                self._update_open_licenses()
            query = query.filter(model.Package.license_id.in_(self._open_licenses))
        if self._options.order_by:
            if self._options.order_by == 'rank':
                query = query.add_column(sqlalchemy.func.ts_rank_cd(sqlalchemy.text('package_search.search_vector'), sqlalchemy.func.plainto_tsquery(all_terms)))
                query = query.order_by(sqlalchemy.text('ts_rank_cd_1 DESC'))
            elif hasattr(model.Package, self._options.order_by):
                model_attr = getattr(model.Package, self._options.order_by)
                query = query.order_by(model_attr)
            else:
                # TODO extras
                raise NotImplemented

        query = query.distinct()
        return query

    def _build_tags_query(self, general_terms):
        query = model.Session.query(model.Tag)
        for term in general_terms:
            query = query.filter(model.Tag.name.contains(term.lower()))
        return query

    def _build_groups_query(self, authorized_package_query, general_terms):
        query = authorized_package_query
        for term in general_terms:
            query = query.filter(model.Group.name.contains(term.lower()))
        return query

    def _run_query(self, query):
        # Run the query
        self._results['count'] = query.count()
        query = query.offset(self._options.offset)
        query = query.limit(self._options.limit)

        results = []
        for result in query:
            if isinstance(result, tuple) and isinstance(result[0], model.DomainObject):
                # This is the case for order_by rank due to the add_column.
                results.append(result[0])
            else:
                results.append(result)
        self._results['results'] = results

    def _filter_by_tags_or_groups(self, field, query, value_list):
        for name in value_list:
            if field == 'tags':
                tag = model.Tag.by_name(name.strip(), autoflush=False)
                if tag:
                    tag_id = tag.id
                    # need to keep joining for each filter
                    # tag should be active hence state_id requirement
                    query = query.join('package_tags', aliased=True).filter(sqlalchemy.and_(
                        model.PackageTag.state==model.State.ACTIVE,
                        model.PackageTag.tag_id==tag_id))
                else:
                    # unknown tag, so torpedo search
                    query = query.filter(model.PackageTag.tag_id==u'\x130')
            elif field == 'groups':
                group = model.Group.by_name(name.strip(), autoflush=False)
                if group:
                    group_id = group.id
                    # need to keep joining for each filter
                    query = query.join('groups', aliased=True).filter(
                        model.Group.id==group_id)
                else:
                    # unknown group, so torpedo search
                    query = query.filter(model.Group.id==u'-1')
                    
        return query
    
    def _filter_by_extra(self, field, query, terms):
        make_like = lambda x,y: x.ilike('%' + y + '%')
        value = '%'.join(terms)
        query = query.join('_extras', aliased=True).filter(
            sqlalchemy.and_(
              model.PackageExtra.state==model.State.ACTIVE,
              model.PackageExtra.key==unicode(field),
            )).filter(make_like(model.PackageExtra.value, value))
        return query
        
    def _update_open_licenses(self):  # Update, or init?
        self._open_licenses = []
        for license in model.Package.get_license_register().values():
            if license and license.isopen():
                self._open_licenses.append(license.id)

    def _format_results(self):
        if not self._options.return_objects:
            if self._options.all_fields:
                results = []
                for entity in self._results['results']:
                    if ENABLE_CACHING:
                        cachekey = u'%s-%s' % (unicode(str(type(entity))), entity.id)
                        result = our_cache.get_value(key=cachekey,
                                createfunc=lambda: entity.as_dict(), expiretime=3600)
                    else:
                        result = entity.as_dict()
                    results.append(result)
                self._results['results'] = results
            else:
                attr_name = self._options.ref_entity_with_attr
                self._results['results'] = [getattr(entity, attr_name) for entity in self._results['results']]
    
    def index_package(self, package):
        pass
        
    def index_group(self, group):
        pass
        
    def index_tag(self, tag):
        pass


class SolrSearch(SQLSearch):
    _solr_fields = ["entity_type", "tags", "groups", "res_description", "res_format", 
                    "res_url", "text", "urls", "indexed_ts"]

    def __init__(self, solr_url=None):
        if solr_url is None:
            solr_url = config.get('solr_url', 'http://localhost:8983/solr')
        # import inline to avoid external dependency 
        from solr import SolrConnection # == solrpy 
        self._conn = SolrConnection(solr_url)

    def _open_license_query_part():
        if self._open_licenses is None:
            self._update_open_licenses()
        licenses = ["+%d" % id for id in self.open_licenses]
        licenses = " OR ".join(licenses)
        return "license_id:(%s) " % licenses

    def _build_package_query(self, authorized_package_query,
                             general_terms, field_specific_terms):
        orm_query = authorized_package_query
        orm_query = orm_query.filter(model.package_search_table.c.package_id==model.Package.id)

        # Full search by general_terms (and field specific terms but not by field)
        query = u""
        for field, term in field_specific_terms.items():
            query += field + u":" + term + u" "
        for term in general_terms:
            query += term + u" "

        # Filter for options
        if self._options.filter_by_downloadable:
            query += u"res_url:[* TO *] " # not null resource URL 
        if self._options.filter_by_openness:
            query += self._open_license_query_part()
        
        self._solr_results = self._conn.query(query, #sort=sorting, 
                                        rows=self._options.limit,
                                        start=self._options.offset)
        entity_ids = [r.get('id') for r in self._solr_results.results]
        orm_query = orm_query.filter(model.Package.id.in_(entity_ids))
        orm_query = orm_query.add_column(sqlalchemy.func.now())
        
        if self._options.order_by and self._options.order_by != 'rank':
            if hasattr(model.Package, self._options.order_by):
                model_attr = getattr(model.Package, self._options.order_by)
                orm_query = orm_query.order_by(model_attr)
        
        return orm_query
        
    def _run_query(self, query):
        if self._options.entity == 'package':
            self._results['count'] = query.count()
            results = [(r, self._solr_results.get('score', 0)) for r in query]
            self._results['results'] = results
        else:
            SQLSearch._run_query(self, query)
    
    def index_package(self, package):
        return self.index_package_dict(package.as_dict())
    
    def index_package_dict(self, package):
        index_fields = self._solr_fields + package.keys()
            
        # include the extras in the main namespace
        extras = package.get('extras', {})
        if 'extras' in package:
            del package['extras']
        for (key, value) in extras.items():
            if key not in index_fields:
                package[key] = value

        # flatten the structure for indexing: 
        for resource in package.get('resources', []):
            for (okey, nkey) in [('description', 'res_description'),
                                 ('format', 'res_format'),
                                 ('url', 'res_url')]:
                package[nkey] = package.get(nkey, []) + [resource.get(okey, u'')]
        if 'resources' in package:
            del package['resources']

        package['entity_type'] = u"package"
        package = dict([(str(k), v) for (k, v) in package.items()])

        # send to solr:    
        self._conn.add(**package)


ENGINES = {
    'sql': SQLSearch, 
    'solr': SolrSearch
    }


def make_search(engine=None, **kwargs):
    if engine is None:
        engine = config.get('search_engine', 'sql')
    klass = ENGINES.get(engine.strip().lower())
    return klass(**kwargs)
