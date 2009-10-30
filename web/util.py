import os, sys

class Settings(object):
  def __new__(cls):
    if '_instance' not in cls.__dict__: cls._instance = object.__new__(cls)
    return cls._instance
  def __getattr__(self, attr):
    if attr in self.__dict__: return self.attr
    return None
settings = Settings()

class MultiDict(dict):
  def __init__(self,*args,**kwargs):
    dict.__init__(self,*args,**kwargs)
    self._dups = {}
    if args:
      for key,val in (x for x in args[0] if x not in self.items()): self._dups.setdefault(key,[]).append(val)
  def __setitem__(self, key, val):
    if dict.has_key(self,key): self._dups.setdefault(key,[]).append(dict.get(self,key))
    dict.__setitem__(self,key,val)
  def __delitem__(self, key):
    dict.__delitem__(self,key)
    self._dups.__delitem__(key)
  def getall(self, key, default=[]):
    return self._dups.get(key,[]) + [self.get(key)] if self.has_key(key) else default
  def items(self):
    items = dict.items(self)
    for key,val in self._dups.items(): items.extend([(key,v) for v in val])
    return items
  def values(self):
    return [v for k,v in self.items()]

class URI(object):
  def __init__(self, uri):
    self.uri = uri
    self.scheme = None
    self.user = None
    self.password = None
    self.host = None
    self.port = None
    self.path = None
    self.kwargs = {}
    self.scheme,uri = uri.split('://',1)
    if '@' in uri: self.user,uri = uri.rsplit('@',1)
    if self.user and ':' in self.user: self.user,self.password = self.user.split(':',1)
    if '/' in uri: self.host,self.path = uri.split('/',1)
    if self.host and ':' in self.host: self.host,self.port = self.host.split(':',1)
    if self.port: self.port = int(self.port)
    if self.path and '?' in self.path:
      self.path,query = self.path.split('?',1)
      for arg in query.split(','):
        k,v = arg.split('=')
        self.kwargs[k] = v

def safeunicode(obj, encoding='utf-8'):
  if isinstance(obj, unicode): return obj
  elif isinstance(obj, str): return obj.decode(encoding)
  elif hasattr(obj, '__unicode__'): return unicode(obj)
  else: return str(obj).decode(encoding)

def safestr(obj, encoding='utf-8'):
  if isinstance(obj, unicode): return obj.encode(encoding)
  elif isinstance(obj, str): return obj
  else: return str(obj)

def import_path(fullpath):
  path, filename = os.path.split(fullpath)
  filename, ext = os.path.splitext(filename)
  sys.path.append(path)
  module = __import__(filename)
  del sys.path[-1]
  return module
