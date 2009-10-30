import os, sys, re

project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from web.app import Application, Response
from web.template import Template
from web.orm import Model
from web.util import settings

settings.TEMPLATE_ROOT = os.path.join(project_root,'templates')
settings.DOMAIN = 'isshot.com'
# the following translates to ../isshot.com.db
settings.DB = 'sqlite://%s.db' % os.path.join(os.path.dirname(project_root), settings.DOMAIN)
settings.DEBUG = False

class Redirection(Model): pass

def page(filename, context={}, errors=[]):
  context['errors'] = errors
  context['settings'] = settings
  filename = os.path.join(project_root, filename)
  return Response(Template(filename=filename).render(context))

def cleanup_label(label):
  # this could be condensed, but then you'd have no idea what is going on
  label = re.sub(" ", "-", label)
  label = re.sub("-+" ,"-", label)
  label = re.sub("\.+" ,".", label)
  label = re.sub("[^0-9a-zA-Z.-]", "", label)
  prev_label = ""
  while prev_label != label:
    prev_label = label
    label = re.sub("^[.-]|[.-]$", "", label)
  parts = []
  for part in label.split('.'):
    parts.append(re.sub("^[-]|[-]$", "", part))
  return '.'.join(parts)

def index(request):
  dot_domain = '.%s' % settings.DOMAIN
  host = request.environ['HTTP_HOST']
  host = host.split(':')[0] if ':' in host else host
  label = cleanup_label(host.split(dot_domain)[0] if dot_domain in host else host)
  if host == settings.DOMAIN or host == 'www.%s' % settings.DOMAIN:
    redirections = Redirection.select("where counter > 0 order by counter desc limit 5")
    return page("templates/index.html", {'redirections':redirections})
  else:
    r = Redirection.select("where label = {label}", {'label':label})
    if r:
      entry = r[0]
      destination = entry.destination
      entry.counter += 1
      entry.save()
    else:
      destination = 'http://www.%s/shootit?label=%s' % (settings.DOMAIN,label)
    return Response(redirect=destination, status_code=301)

def shootit(request):
  errors = []
  if request.method == 'POST':
    orig_label = request.POST['label']
    label = cleanup_label(orig_label)
    destination = request.POST['destination']
    if label == "":
      errors.append("Your label (%s) reduced to nothing, and is invalid" % orig_label)
    elif Redirection.select("where label = {label}", {'label':label}):
      errors.append('that label already exists')
    else:
      if not destination.startswith('http://'): destination = 'http://%s' % destination
      Redirection(label=label, destination=destination, counter=0).save()
      url = "%s.%s" % (label, settings.DOMAIN)
      errors.append('<a href="http://%s">%s</a> has been created and points to %s' % (url, url, destination))
  return page("templates/shootit.html", errors=errors)

urls = (
  (r'^/$', index, 'index'),
  (r'^/shootit$', shootit, 'shootit')
)

application = Application(urls)

if __name__ == '__main__':
  from web import server
  server.run(application, autoreload=True)
