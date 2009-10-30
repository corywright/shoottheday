import re,cgi,Cookie,os,sys,traceback,mimetypes,urllib2
from db import db
from session import DBStore,FileStore,Session
from util import MultiDict,safeunicode,safestr,settings,URI

settings.DEBUG = True
settings.STATIC = 'static'

class Request(object):
  def __init__(self,environ):
    self.environ = environ
    self.path = environ.get('PATH_INFO','').decode('utf8')
    self.method = environ.get('REQUEST_METHOD','')
    self.cookies = Cookie.SimpleCookie(str(environ.get('HTTP_COOKIE','')))
    self.GET = MultiDict(cgi.parse_qsl(urllib2.unquote(environ.get('QUERY_STRING','')).decode('utf8'),keep_blank_values=1))
    self.POST = {}
    self.FILES = {}
    if self.method == 'POST':
      post = cgi.FieldStorage(fp=environ.get('wsgi.input',''),environ=environ,keep_blank_values=1)
      self.POST = MultiDict([(item.name,item.value) for item in post.list if not item.filename])
      self.FILES = MultiDict([(item.name,item) for item in post.list if item.filename])
    self.REQUEST = MultiDict(self.GET.items() + self.POST.items()) # + self.FILES.items())

class Response(object):
  def __init__(self,body='',content_type='text/html',charset='utf8',redirect=None,status_code=None,status_msg=None):
    self.headers = MultiDict()
    self.content_type = content_type
    self.charset = charset
    self.body = body
    self.redirect = redirect
    self.status_code = status_code
    self.status_msg = status_msg
    self.cookies = Cookie.SimpleCookie()
  @property
  def status(self):
    status_map = {200:'OK',301:'Moved Permanently',302:'Found',404:'Not Found',500:'Internal Server Error'}
    if not self.status_msg: self.status_msg = status_map.get(self.status_code,'')
    return "%s %s" % (self.status_code,self.status_msg)
  def finalize(self):
    self.headers['Content-Type'] = '%s; charset=%s' % (self.content_type, self.charset)
    self.headers['Content-Length'] = len(self.body)
    if self.redirect:
      self.headers['Location'] = self.redirect
      self.status_code = self.status_code or 302
    for key in self.cookies:
      self.cookies[key]['path'] = self.cookies[key]['path'] or '/'
      self.headers['Set-Cookie'] = self.cookies[key].OutputString()
    self.status_code = self.status_code or 200
    self.headers = MultiDict([(safestr(k,self.charset),safestr(v,self.charset)) for (k,v) in self.headers.items()])

def resolve(request, urls):
  for pattern,view,name in urls:
    match = pattern.match(request.path)
    if match:
      kwargs = match.groupdict()
      args = list(match.groups())
      for index in match.re.groupindex.values():
        args.pop(index-1)
      return view,args,kwargs
  return (None,None,None)

def find_url(_urls, _url_name, *args, **kwargs):
  for regex in (re.compile(p) for p,v,n in _urls if n==_url_name):
    pattern = regex.pattern.lstrip('^').rstrip('$*')
    for key in regex.groupindex:
      if key in kwargs:
        pattern = re.sub(r'(?u)\(\?P<%s>.*?\)' % key,kwargs[key],pattern)
    for arg in args:
      pattern = re.sub(r'(?u)\(.*?\)',arg,pattern,1)
    if regex.match(pattern):
      return pattern
  return ''

class Application(object):
  
  def __init__(self,urls):
    self.urls = tuple(((re.compile(pattern,re.UNICODE),view,name) for pattern,view,name in urls))

  def __call__(self, environ, start_response):
    try:
      request = Request(environ)
      if settings.DEBUG and request.method == 'GET' and request.path.startswith('/%s/' % settings.STATIC):
        response = self.serve_static(request)
      else:
        if settings.SESSION:
          session_uri = URI(settings.SESSION)
          if session_uri.scheme == 'db': store = DBStore(table=session_uri.path)
          elif session_uri.scheme == 'file': store = FileStore(path=session_uri.path)
          if request.cookies.get('session_key'): request.session = store.load(request.cookies['session_key'].value)
          else: request.session = Session()
        response = self.serve_dynamic(request)
        if settings.SESSION and request.session.modified:
          store.store(request.session)
          if not request.cookies.get('session_key'): response.cookies['session_key'] = request.session.key
      response.finalize()
      if settings.DB: db.commit()
    except Exception, e:
      if settings.DB: db.rollback()
      if settings.DEBUG: response = self.serve_debug(request)
      elif settings._500: response = settings._500(request)
      else: response = Response(body='500 Internal Server Error',content_type='text/plain',status_code=500)
      response.finalize()
    start_response(response.status,response.headers.items())
    return [safestr(response.body)]

  def serve_static(self, request):
    path = request.path[1:]
    if os.path.exists(path) and os.path.isfile(path):
      return Response(body=open(path,'rb').read(),content_type=mimetypes.guess_type(path)[0])
    elif os.path.exists(path + 'index.html'):
      return Response(body=open(path+'index.html','rb').read(),content_type='text/html')
    elif os.path.exists(path) and os.path.isdir(path):
      return Response(body='\n'.join(os.listdir(path)),content_type='text/plain')
    elif settings._404: return settings._404(request)
    else:
      return Response(body='404 Not Found',content_type='text/plain',status_code=404)

  def serve_dynamic(self, request):
    view,args,kwargs = resolve(request,self.urls)
    if view: response = view(request,*args,**kwargs)
    elif settings._404: response = settings._404(request)
    else: response = Response(body='404 Not Found',content_type='text/plain',status_code=404)
    return response

  def serve_debug(self, request):
    t,v,tb = sys.exc_info()
    s = [u'Traceback:\n']
    s.append(u''.join(traceback.format_tb(tb)))
    s.append(u'  %s: %s' % (t.__name__,v))
    s.append(u'\n\nMethod: %s' % request.method)
    s.append(u'\nPath: %s' % request.path)
    s.append(u'\nGET:\n' % request.GET)
    for key in sorted(request.GET): s.append(u'  %s: %s' % (key,request.GET[key]))
    s.append(u'\nPOST:\n' % request.POST)
    for key in sorted(request.POST): s.append(u'  %s: %s' % (key,request.POST[key]))
    s.append(u'\nCookies:\n')
    for key in sorted(request.cookies): s.append(u'  %s' % request.cookies[key])
    s.append(u'\nEnvironment:\n')
    for key in sorted(request.environ): s.append(u'  %s: %s' % (key,safeunicode(request.environ[key])))
    s.append(u'\nSettings:\n')
    for key in sorted(settings.__dict__.keys()): s.append(u'  %s: %s' % (key,getattr(settings,key)))
    return Response(body=u'\n'.join(s),content_type='text/plain',status_code=500)

