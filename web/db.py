import threading
from util import settings, URI

class Database(object):
  def __init__(self, uri=None):
    self.local = threading.local()
    self.local.uri = URI(uri) if uri else None
  @property
  def uri(self):
    if not hasattr(self.local,'uri') or not self.local.uri:
      self.local.uri = URI(settings.DB)
    return self.local.uri
  @property
  def connection(self):
    if not hasattr(self.local,'connection'):
      driver_map = {'sqlite':'sqlite3','postgres':'psycopg2','mysql':'MySQLdb'}
      uri = self.uri
      module = __import__(driver_map[uri.scheme])
      if uri.scheme == 'sqlite':
        kw = dict(database=uri.path or ':memory:',detect_types=module.PARSE_DECLTYPES|module.PARSE_COLNAMES)
      elif uri.scheme == 'postgres':
        kw = dict(database=uri.path,user=uri.user,password=uri.password,host=uri.host,port=uri.port)
      elif uri.scheme == 'mysql':
        kw = dict(db=uri.path,user=uri.user,passwd=uri.password,host=uri.host,port=uri.port,sql_mode='ANSI')
      kw = dict([(k,v) for k,v in kw.items() if v]) # remove blank options
      kw.update(uri.kwargs) # add in users kwargs
      self.local.connection = module.connect(**kw)
    return self.local.connection
  @property
  def cursor(self):
    if not hasattr(self.local,'cursor'): self.local.cursor = self.connection.cursor()
    return self.local.cursor
  @property
  def lastrowid(self):
    if not hasattr(self.local,'lastrowid'): return None
    return self.local.lastrowid
  def commit(self):
    self.connection.commit()
  def rollback(self):
    self.connection.rollback()
  def execute(self,sql,values=None):
    if self.uri.scheme != 'sqlite': sql = sql.replace('?','%s')
    if settings.DEBUG: print sql,values
    if values: self.cursor.execute(sql,values)
    else: self.cursor.execute(sql)
    self.local.lastrowid = self.cursor.lastrowid
    return self.cursor.fetchall() #or self.cursor.rowcount
  def execute_script(self, sql):
    self.connection.isolation_level = None # sqlite only ?
    for stmt in sql.split(';\n'):
      if stmt.strip(): self.execute(stmt)

db = Database()

