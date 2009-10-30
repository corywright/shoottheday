import base64,uuid,pickle,os
from db import db

# settings.SESSION = 'file:///sessions'

class Session(dict):
  def __init__(self,key=None,**kwargs):
    super(self.__class__,self).__init__(**kwargs)
    self.key = key if key else base64.encodestring(uuid.uuid4().bytes)[:-3]
    self.modified = False
  def __setitem__(self,key,value):
    super(self.__class__,self).__setitem__(key,value)
    self.modified = True
  def __delitem__(self,key):
    super(self.__class__,self).__delitem__(key)
    self.modified = True

class FileStore(object):
  def exists(self,key):
    return os.path.exists(os.path.join(self.path,key))
  def load(self,key):
    if self.exists(key):
      return pickle.loads(base64.decodestring(open(os.path.join(self.path,key)).read()))
    else:
      return Session(key=key)
  def store(self,session):
    open(os.path.join(self.path,session.key),'w').write(base64.encodestring(pickle.dumps(session)))
  def __init__(self,path='sessions'):
    self.path = path

class DBStore(object):
  def exists(self,key):
    return db.execute("""select key from "%s" where key = ? limit 1""" % self.table,[key])
  def load(self,key):
    if self.exists(key):
      return pickle.loads(base64.decodestring(db.execute("""select data from "%s" where key = ?""" % self.table,[key])[0][0]))
    else:
      return Session(key=key)
  def store(self,session):
    data = base64.encodestring(pickle.dumps(session))
    if self.exists(session.key):
      db.execute("""update "%s" set data = ? where key = ?""" % self.table,[data,session.key])
    else:
      db.execute("""insert into "%s" (key,data) values (?,?)""" % self.table,[session.key,data])
  def __init__(self,table='session'):
    self.table = table
