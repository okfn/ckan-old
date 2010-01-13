from sqlalchemy import *
import sqlalchemy.sql as sql

from migrate import *
import migrate.changeset

metadata = MetaData(migrate_engine)

def upgrade():
    stateful_tables = [
            'license',
            'package', 'package_revision',
            'package_tag', 'package_tag_revision',
            'package_extra', 'package_extra_revision',
            'package_resource', 'package_resource_revision',
            'revision'
            ]
    for table_name in stateful_tables:
        # print '***** Processing table: %s' % table_name
        table = Table(table_name, metadata, autoload=True)
        column = Column('state', UnicodeText)
        column.create(table)
        for (name,id) in [ ('active',1), ('deleted',2), ('pending',3) ]:
            sqlcmd = '''UPDATE %s SET state = 'active' WHERE state_id =
            1''' % table.name
            migrate_engine.execute(sqlcmd)
        stateid = table.c['state_id']
        stateid.drop()
    table = Table('state', metadata, autoload=True)
    table.drop()

def downgrade():
    raise NotImplementedError()
