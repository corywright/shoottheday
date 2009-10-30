import exceptions, re
from db import db
from util import settings

model_cache = {}

class HasOne(object):
  def __init__(self, child=None, parent=None, parent_column=None, child_column=None):
    self._parent = parent
    self._child = child
    self._parent_column = parent_column
    self._child_column = child_column
  @property
  def parent(self): return model_cache[self._parent]
  @property
  def child(self): return model_cache[self._child]
  @property
  def parent_column(self): return self._parent_column or '%s_%s' % (self.child._table,self.child._pk)
  @property
  def child_column(self): return self._child_column or self.child._pk
  
class HasMany(object):
  def __init__(self, child=None, parent=None, parent_column=None, child_column=None, through=None):
    self._parent = parent
    self._child = child
    self._parent_column = parent_column
    self._child_column = child_column
    self._through = through
  @property
  def parent(self): return model_cache[self._parent]
  @property
  def child(self): return model_cache[self._child]
  @property
  def parent_column(self):
    if self._parent_column: return self._parent_column
    elif self._through: return '%s_%s' % (self.parent._table,self.parent._pk)
    else: return self.parent._pk
  @property
  def child_column(self):
    if self._child_column: return self._child_column
    elif self._through: return '%s_%s' % (self.child._table,self.child._pk)
    else: return '%s_%s' % (self.parent._table,self.parent._pk)
  @property
  def through(self): return model_cache[self._through]._table if self._through in model_cache else self._through

class Collection(list):
  def __init__(self,model,reference,*args,**kwargs):
    self.model = model
    self.reference = reference
    super(self.__class__,self).__init__(*args,**kwargs)
  def create(self,*args,**kwargs):
    ref = self.reference
    obj = ref.child(*args,**kwargs)
    if ref.through:
      obj.save()
      sql = 'insert into "%s" ("%s","%s") values (?,?)' % (ref.through,ref.parent_column,ref.child_column)
      values = [getattr(self.model,self.model._pk),getattr(obj,obj._pk)]
      db.execute(sql,values)
    else:
      setattr(obj,ref.child_column,getattr(self.model,self.model._pk))
      obj.save()
    self.append(obj)
  def add(self,obj):
    ref = self.reference
    if not isinstance(obj,ref.child): raise Exception
    if ref.through:
      if not getattr(self.model,self.model._pk):
        self.model.save()
      sql = 'insert into "%s" ("%s","%s") values (?,?)' % (ref.through,ref.parent_column,ref.child_column)
      values = [getattr(self.model,self.model._pk),getattr(obj,obj._pk)]
      db.execute(sql,values)
    else:
      setattr(obj,ref.child_column,self.model.id)
      obj.save()
    self.append(obj)
  def remove(self,obj):
    ref = self.reference
    if not isinstance(obj,ref.child): raise Exception
    if ref.through:
      sql = 'delete from "%s" where "%s" = ? and "%s" = ?' % (ref.through,ref.parent_column,ref.child_column)
      values = [getattr(self.model,self.model._pk),getattr(obj,obj._pk)]
      db.execute(sql,values)
    else:
      setattr(obj,ref.child_column,None)
      obj.save()
    super(self.__class__,self).remove(obj)

class ModelMeta(type):
  def __new__(cls, name, bases, attrs):
    if name == 'Model': return type.__new__(cls, name, bases, attrs)
    references = {}
    for key,val in attrs.items():
      if isinstance(val,HasOne) or isinstance(val,HasMany):
        val._parent = name
        references[key] = val
        del attrs[key]
    new_class = type.__new__(cls, name, bases, attrs)
    new_class._table = attrs.get('_table',re.sub(r'([A-Z])',r'_\1',name).lower().lstrip('_'))
    new_class._pk = attrs.get('_pk','id')
    if not attrs.get('_columns',None):
      sql = 'select * from "%s" limit 1' % new_class._table
      db.execute(sql)
      new_class._columns = [col[0] for col in db.cursor.description]
    new_class._references = references
    model_cache[new_class.__name__] = new_class
    return new_class

class Model(object):
  __metaclass__ = ModelMeta
  
  def __init__(self, **kwargs):
    for key in self._columns:
      self.__dict__[key] = None
    for key,value in kwargs.items():
      self.__dict__[key] = value
  
  def __eq__(self, obj): return isinstance(obj,self.__class__) and getattr(obj,obj._pk) == getattr(self,self._pk)
  def __ne__(self, obj): return not self == obj
  
  def __getattr__(self,attr):
    if attr in self._references:
      ref = self._references[attr]
      if isinstance(ref,HasOne):
        result = ref.child.select("""where "%s" = ?""" % ref.child_column,values=[getattr(self,ref.parent_column)])
        result = result[0] if result else None
      elif isinstance(ref,HasMany):
        if ref.through:
          sql = 'join "%s" on ("%s"."%s" = "%s"."%s") where "%s"."%s" = ?' % \
                (ref.through,ref.through,ref.child_column,ref._child,ref.child._pk,ref.through,ref.parent_column)
          result = Collection(self,ref,ref.child.select(sql,values=[getattr(self,self._pk)]))
        else:
          result = Collection(self,ref,ref.child.select('where "%s" = ?' % ref.child_column,values=[getattr(self,ref.parent_column)]))
      self.__dict__[attr] = result
      return result
    raise exceptions.AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__,attr))
  
  def __setattr__(self,attr,val):
    if attr in self._references:
      ref = self._references[attr]
      if isinstance(ref,HasOne):
        self.__dict__[ref.parent_column] = getattr(val,ref.child_column)
    self.__dict__[attr] = val
    return val
      
  def save(self):
    fields = []
    values = []
    for k in self._columns:
      fields.append(k)
      values.append(self.__dict__[k])
    if getattr(self,self._pk):
      sql = 'update "%s" set %s where "%s" = ?' % (self._table, ','.join(['"%s"=?' % f for f in fields]),self._pk)
      db.execute(sql,values + [getattr(self,self._pk)])
    else:
      sql = 'insert into "%s" ("%s") values (%s)' % (self._table, '","'.join(fields), ','.join(['?']*len(fields)))
      db.execute(sql,values)
      setattr(self,self._pk,db.lastrowid)
    return self
  
  def delete(self):
    if getattr(self,self._pk):
      sql = 'delete from "%s" where "%s" = ?' % (self._table,self._pk)
      db.execute(sql,[getattr(self,self._pk)])
  
  @classmethod
  def get(cls, id):
    sql = u'select "%s" from "%s" where "%s" = ?' % ('","'.join(cls._columns),cls._table,cls._pk)
    data = {}
    for row in db.execute(sql,[id]):
      for num in xrange(len(cls._columns)):
        data[cls._columns[num]] = row[num]
    return cls(**data) if data else None  # raise an exception ?
  
  @classmethod
  def count(cls, *args, **kwargs):
    kwargs['count'] = True
    return cls.select(*args,**kwargs)

  @classmethod
  def all(cls):
    return cls.select()

  @classmethod
  def select(cls, query="", context=None, count=False, left_join=False, values=[]):
    join = 'left join' if left_join else 'join' 
    collections = re.findall(r'([\w\.]+)\.\w+',query) # find collections
    collections = normalize(collections)
    query = re.sub(r'([\w\.]+)\.(\w+)','"\\1"."\\2"',query) # quote collection aliases
    references = {} # find reference for each collection
    for collection in collections:
      if '.' in collection:
        prefix,attr = collection.rsplit('.',1)
        references[collection] = model_cache[references[prefix].model]._references[attr]
      else:
        references[collection] = cls._references[collection]
    query = parse(query,context)
    if count: sql = 'select count(distinct "%s"."%s")' % (cls.__name__,cls._pk)
    else:
      columns = []
      for column in cls._columns:
        columns.append('"%s"."%s"' % (cls.__name__,column))
      sql = 'select distinct ' + ','.join(columns)
    sql += ' from "%s" as "%s"' % (cls._table,cls.__name__)
    for collection in sorted(references.keys()): # add joins for each collection
      prefix = collection.rsplit('.',1)[0] if '.' in collection else cls.__name__
      ref = references[collection]
      if isinstance(ref,HasOne):
        sql += ' %s "%s" as "%s" on ("%s"."%s" = "%s"."%s")' % \
               (join,ref.child._table,collection,collection,ref.child_column,prefix,ref.parent_column)
      elif isinstance(ref,HasMany):
        if ref.through:
          prefix_pk = model_cache[references[prefix].model]._pk if prefix in references else cls._pk
          sql += ' %s "%s" as "%s.map" on ("%s"."%s" = "%s.map"."%s")' % \
                 (join,ref.through,collection,prefix,prefix_pk,collection,ref.parent_column)
          sql += ' %s "%s" as "%s" on ("%s"."%s" = "%s.map"."%s")' % \
                 (join,ref.child._table,collection,collection,ref.child._pk,collection,ref.child_column)
        else:
          sql += ' %s "%s" as "%s" on ("%s"."%s" = "%s"."%s")' % \
                 (join,ref.child._table,collection,collection,ref.child_column,prefix,ref.parent_column)
    sql += " %s" % query
    if count: return db.execute(sql,values)[0][0]
    else:
      objects = [] # TODO: use dictionary, instead of distinct, to provide uniqueness ???
      for row in db.execute(sql,values):
        data = {}
        for num in xrange(len(cls._columns)):
          data[cls._columns[num]] = row[num]
        objects.append(cls(**data))
      return objects

def normalize(collections):
  d = {}
  for collection in collections:
    parts = collection.split('.')
    for i in xrange(len(parts)):
      d['.'.join(parts[:i+1])] = True
  return sorted(d.keys())

def escape(obj):
  if obj is None: val = 'NULL'
  elif isinstance(obj,(int,long,float)): val = unicode(obj)
  elif isinstance(obj,Model): val = unicode(getattr(obj,obj._pk))
  else: val = "'%s'" % unicode(obj).replace("'","''")
  return val

def parse(query,context=None):
  tokens = re.split(r'({.*?})',query)
  sql = ''
  for token in tokens:
    if token.startswith('{') and token.endswith('}'):
      code = token[1:-1]
      obj = eval(code,context) if context else eval(code)
      if hasattr(obj,'__iter__'): sql = '%s(%s)' % (sql,','.join((escape(o) for o in obj)))
      else: sql = '%s%s' % (sql,escape(obj))
    else: sql = "%s%s" % (sql,token)
  return sql
