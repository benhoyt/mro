""" MRO: Map Rows to Objects with web.py.

See docstrings, README.md, and/or https://github.com/benhoyt/mro for
documentation.

MRO is released under the 3-clause "New BSD license", and is copyright (c) 2009
Brush Technology. See the full text of the license at:
    http://opensource.org/licenses/BSD-3-Clause

"""

import datetime
import web

class Column(object):
    """ Defines a column in a Table object. """

    def __init__(self, sql_type=None, indexed=False, primary_key=False, secondary_key=False, **kwargs):
        """ Define a column inside a Table object with an SQL type of sql_type
            (if not given, the column's _sql_type attribute is used).

            If "indexed" is True, an index for this column will be created. If
            "indexed" is a string, it will be used as an SQL indexing function,
            for example indexed='LOWER(username)'.

            "primary_key" is True if this column is an (integer) primary key,
            or "secondary_key" can be True if this column is a unique, string
            secondary key (like username, email address, or slug).

            Other keyword args are converted to SQL constraints as follows:
            underscores in key name are replaced with spaces and it's converted
            to uppercase. If value is a bool and True, key name is added to the
            constraints, otherwise value is converted to a string and appended
            to the constraint. For example:

            >>> column = Column('TEXT', not_null=True, default="'NZD'")
            >>> print column._sql_type, column._constraints
            TEXT DEFAULT 'NZD' NOT NULL
        """
        if sql_type is not None:
            self._sql_type = sql_type
        self._indexed = indexed
        constraints = []
        self._primary_key = primary_key
        if primary_key:
            constraints.append('PRIMARY KEY')
        self._secondary_key = secondary_key
        if secondary_key:
            constraints.append('NOT NULL UNIQUE')
            self._indexed = True
        for name, value in sorted(kwargs.iteritems()):
            name = name.replace('_', ' ').upper()
            if isinstance(value, bool) and value:
                constraints.append(name)
            else:
                constraints.append('%s %s' % (name, value))
        self._constraints = ' '.join(constraints)

class Serial(Column):
    _sql_type = 'SERIAL'

class Integer(Column):
    _sql_type = 'INTEGER'

class String(Column):
    _sql_type = 'TEXT'

class Date(Column):
    _sql_type = 'DATE'

class Timestamp(Column):
    _sql_type = 'TIMESTAMP WITHOUT TIME ZONE'

class Inet(Column):
    _sql_type = 'INET'

class Table(object):
    """ Defines a database table with its columns. See the UserTest class for
        an example, and see __init__'s docstring for examples of how to use the
        constructor.
    """

    def __init__(self, _init=None, _fromdb=False, _test=False, **kwargs):
        """ Initialise a row object of this table from the given _init data.
            If _init is None, fields are taken from kwargs. If _init is a dict,
            fields are taken from it. Otherwise _init is assumed to be a
            primary key if it's an int or a secondary key if it's a non-int,
            and fields are loaded from the database (raising a KeyError if no
            rows match the given key).

            _fromdb is used internally to signal that these values have been
            loaded from the database.

            >>> UserTest()
            UserTest()
            >>> UserTest({'username': 'bill', 'hash': '4321'})
            UserTest(hash='4321', username='bill')
            >>> u = UserTest(username='bob', hash='1234')
            >>> u
            UserTest(hash='1234', username='bob')
            >>> print u.save(_test=True)
            INSERT INTO users (username, hash) VALUES ('bob', '1234')

            >>> u = UserTest(5, _test=True)
            SELECT * FROM users WHERE id = 5
            >>> u = UserTest('bob', _test=True)
            SELECT * FROM users WHERE username = 'bob'

            >>> u = UserTest('baduser', _test=[{}, {}])
            Traceback (most recent call last):
              ...
            KeyError: "no users (or more than one) with username of 'baduser'"
        """
        self._changed = set()
        self._init_columns()
        if _init is None:
            _init = kwargs
        elif not isinstance(_init, dict):
            key_name = self._primary_key if isinstance(_init, int) else self._secondary_key
            select = web.select(self._table, where='%s = $key' % key_name, vars={'key': _init}, _test=_test)
            if _test:
                print select
                select = _test if not isinstance(_test, bool) else [{}]
            rows = list(select)
            if len(rows) != 1:
                raise KeyError('no %s (or more than one) with %s of %r' % (self._table, key_name, _init))
            _init = rows[0]
        self.setattrs(_init)
        if _fromdb:
            self._changed.clear()

    @classmethod
    def get(cls, key, _test=False):
        """ Get and return a single row from the database given a primary or
            secondary key, returning None if no rows match the given key
            (unlike __init__, which raises a KeyError).

            >>> u = UserTest.get(5, _test=True)
            SELECT * FROM users WHERE id = 5
            >>> u = UserTest.get('bob', _test=True)
            SELECT * FROM users WHERE username = 'bob'
            >>> print UserTest.get('baduser', _test=[{}, {}])
            SELECT * FROM users WHERE username = 'baduser'
            None
        """
        try:
            return cls(key, _fromdb=True, _test=_test)
        except KeyError:
            return None

    @classmethod
    def select(cls, _test=False, **kwargs):
        """ Select and return multiple rows from the database via the web.py
            SQL-like query given via kwargs. For example:

            >>> print UserTest.select(where='username LIKE $u', vars={'u': 'jo%'}, order='username', limit=5, _test=True)
            SELECT * FROM users WHERE username LIKE 'jo%' ORDER BY username LIMIT 5
        """
        select = web.select(cls._table, _test=_test, **kwargs)
        return select if _test else [cls(row, _fromdb=True) for row in select]

    @classmethod
    def _column_sql(cls, name, column):
        """ Return the SQL (column_sql, index_sql) required to create the given
            column and its index, if any. """
        sql = '%s %s%s' % (name, column._sql_type, ' ' + column._constraints if column._constraints else '')
        index = ''
        if column._indexed:
            func = name if isinstance(column._indexed, bool) else column._indexed
            index = 'CREATE INDEX %s_%s_idx ON %s (%s);' % (cls._table, name, cls._table, func)
        else:
            index = ''
        return sql, index

    @classmethod
    def create(cls, _test=False):
        """ Create the table and its indexes based on the column description.
        
            >>> print UserTest.create(_test=True)
            CREATE TABLE users (
                hash TEXT,
                id SERIAL PRIMARY KEY,
                time TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
                username TEXT NOT NULL UNIQUE);
            CREATE INDEX users_username_idx ON users (username);
        """
        columns = []
        indexes = []
        for name, value in sorted(cls.__dict__.iteritems()):
            if isinstance(value, Column):
                column, index = cls._column_sql(name, value)
                columns.append('    ' + column)
                if index:
                    indexes.append(index)
        sql = 'CREATE TABLE %s (\n' % cls._table + ',\n'.join(columns) + ');\n' + '\n'.join(indexes)
        return web.query(sql, _test=_test)

    @classmethod
    def add_column(cls, name, _test=False):
        """ Add a column to the table (after table has been created).

            >>> print UserTest.add_column('username', _test=True)
            ALTER TABLE users ADD COLUMN username TEXT NOT NULL UNIQUE;
            CREATE INDEX users_username_idx ON users (username);
            >>> print UserTest.add_column('hash', _test=True)
            ALTER TABLE users ADD COLUMN hash TEXT;
        """
        column = getattr(cls, name)
        column, index = cls._column_sql(name, column)
        sql = 'ALTER TABLE %s ADD COLUMN %s;' % (cls._table, column)
        if index:
            sql += '\n' + index
        return web.query(sql, _test=_test)

    def save(self, _test=False):
        """ Save this row to the database: update row (only changed fields) if
            primary key attribute has been set, otherwise insert a new row.

            >>> u = UserTest(username='bob', hash='asdf')
            >>> print u.save(_test=True)
            INSERT INTO users (username, hash) VALUES ('bob', 'asdf')
            >>> u = UserTest(id=5)
            >>> u.username = 'bill'
            >>> print u.save(_test=True)
            UPDATE users SET username = 'bill' WHERE id = 5
        """
        if not isinstance(getattr(self, self._primary_key), (Column, type(None))):
            return self.update(key_name=self._primary_key, _test=_test)
        else:
            return self.insert(_test=_test)

    def insert(self, _test=False):
        """ Insert current row as a new row into the database.
        
            >>> u = UserTest(username='bob', hash='asdf')
            >>> print u.insert(_test=True)
            INSERT INTO users (username, hash) VALUES ('bob', 'asdf')
        """
        changed = self._changed_values()
        if self._primary_key in changed:
            del changed[self._primary_key]
        return web.insert(self._table, _test=_test, **changed)

    def update(self, key_name=None, _test=False):
        """ Update row (only changed fields). Primary key is used unless
            another key_name is specified.

            >>> u = UserTest(id=5)
            >>> u.username = 'bill'
            >>> print u.update(_test=True)
            UPDATE users SET username = 'bill' WHERE id = 5
        """
        changed = self._changed_values()
        if key_name is None:
            key_name = self._primary_key
        if key_name in changed:
            del changed[key_name]
        return web.update(self._table, where='%s = $key' % key_name, vars={'key': getattr(self, key_name)}, _test=_test, **changed)

    def delete(self, _test=False):
        """ Delete this row based on its primary key.
        
            >>> u = UserTest(id=5)
            >>> print u.delete(_test=True)
            DELETE FROM users WHERE id = 5
        """
        key_name = self._primary_key
        return web.delete(self._table, where='%s = $key' % key_name, vars={'key': getattr(self, key_name)}, _test=_test)

    def setattrs(self, d):
        """ Set fields of self from key/value pairs in given dict.
        
            >>> u = UserTest()
            >>> u
            UserTest()
            >>> u.setattrs({'username': 'bob', 'hash': '1234'})
            >>> u
            UserTest(hash='1234', username='bob')
        """
        for name, value in d.iteritems():
            setattr(self, name, value)

    def _init_columns(self):
        """ Initialise self's columns list and primary/secondary key fields. """
        cls = self.__class__
        self._columns = []
        for name, value in sorted(cls.__dict__.iteritems()):
            if isinstance(value, Column):
                self._columns.append((name, value))
                if value._primary_key:
                    self._primary_key = name
                elif value._secondary_key:
                    self._secondary_key = name

    def __setattr__(self, name, value):
        """ Override __setattr__ so we can tell which values have been changed
            for insert or update.
        """
        object.__setattr__(self, name, value)
        if isinstance(getattr(self.__class__, name, None), Column):
            self._changed.add(name)

    def _changed_values(self):
        """ Return a list of changed values as (name, value) pairs. """
        return dict((name, getattr(self, name)) for name in self._changed)

    def __str__(self):
        """ Return a more or less human-readable string representation of
            given row, showing all fields that have been set.
            
            >>> u = UserTest(id=5)
            >>> u.username = 'bob'
            >>> u.hash = 'asdf'
            >>> print str(u)
            UserTest(hash='asdf', id=5, username='bob')
        """
        args = []
        for name, column in self._columns:
            value = getattr(self, name)
            if not isinstance(value, Column):
                args.append('%s=%r' % (name, value))
        return '%s(%s)' % (self.__class__.__name__, ', '.join(args))

    __repr__ = __str__

class UserTest(Table):
    """ Example "users" table, used by doctests. """
    _table = 'users'
    id = Serial(primary_key=True)
    username = String(secondary_key=True)
    hash = String()
    time = Timestamp(not_null=True, default='now()')

if __name__ == '__main__':
    import doctest
    doctest.testmod()
