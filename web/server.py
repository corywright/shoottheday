import os,sys
from wsgiref.handlers import CGIHandler
from wsgiref.simple_server import make_server

class Reloader:
  def __init__(self):
    self.mtimes = {}
  def __call__(self):
    for mod in sys.modules.values():
      try:
        mtime = os.stat(mod.__file__).st_mtime
        if mod.__file__.endswith('.pyc') and os.path.exists(mod.__file__[:-1]):
          mtime = max(os.stat(mod.__file__[:-1]).st_mtime, mtime)
        if mod not in self.mtimes:
          self.mtimes[mod] = mtime
        elif self.mtimes[mod] < mtime:
          return True
      except:
        pass

def run(application, host='',port=8000, autoreload=False):
  reloader = Reloader()
  httpd = make_server(host, port, application)
  print "Serving HTTP on port %s..." % port
  while True:
    httpd.handle_request()
    if autoreload and reloader():
      httpd.server_close()
      os.execvp(sys.executable,[sys.executable] + sys.argv) # reload the current process

def cgi(app):
  CGIHandler().run(app)

