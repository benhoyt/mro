MRO: Map Rows to Objects with web.py
====================================

*Note: MRO was developed for an old version of web.py (0.2). I'm not maintaining it any more at this stage, but you're welcome to fork and improve it!*

MRO is not an [ORM](http://en.wikipedia.org/wiki/Object-relational_mapping).
It’s not even the reverse of an ORM. Very simply, MRO maps rows to objects.
It’s a thin layer on top of [web.py](http://webpy.org/)’s equally thin
database wrapper.

Why? Well, for a minimalist framework, I do like web.py’s close-to-the-SQL
approach. But as soon as you have more than a couple of database operations,
you find you’ve got code that repeats itself repeats itself. In the case of
Gifty, I was repeating column names.

But I didn’t want a [fancy ORM](http://www.sqlalchemy.org/) that gave me a new
domain-specific language to worry about, or that supported every left, right,
inner and outer join under the sun. I’ve found that for simple web apps, all I
want is a bit of object with my row: a class that has attributes for columns,
and lets you select and save rows.

I ended up with something that looks quite similar to [Django’s database
layer](http://docs.djangoproject.com/en/dev/topics/db/queries/), albeit much
simplified. (In hindsight, I may well have used Django for this project if I
was doing it again.)

So here’s what MRO looks like:

```python
# define a User object and its columns (SQL table name is "users")
class User(Table):
    _table = 'users'
    id = Serial(primary_key=True)
    username = String(secondary_key=True)
    hash = String()
    time = Timestamp(not_null=True, default='now()')

# create the users table with its columns and indexes
User.create()

# insert a new user into the database (defaults used for id and time)
bob = User(username='bob', hash='1234')
bob.save()

# fetch an existing user and update its hash column
bob = User('bob')
bob.hash = '4321'
bob.save()

# fetch an existing user (this time by primary key) and delete it
bob = User(42)
bob.delete()

# fetch an existing user (or None if no user called 'bill')
bill = User.get('bill')
if not bill:
    print 'Old Bill seems not to exist'

# get list of Users whose usernames start with 'ab' (also shows interpolation)
abusers = User.select(where='username LIKE $u', vars={'u': 'ab%'})
```

So, if you use web.py for a small web app, but you want a touch of class
(ahem) with your database operations, go ahead and use MRO. Be aware that it’s
an in-house tool (for instance, it only supports PostgreSQL at the moment).

See also my [original blog entry](http://blog.brush.co.nz/2010/01/mro/) about
MRO.
