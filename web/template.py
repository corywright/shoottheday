import os,re,textwrap,tempfile
from util import settings, safeunicode

settings.DEBUG = True
settings.TEMPLATE_ROOT = ''

class Template(object):
  INDENT = u'  '
  BUFFER = u'_out'
  TOKEN_RE = re.compile(r'(?ismu)({{.*?}}|{%.*?%})')
  COMMENT_RE = re.compile(r'(?ismu){#.*?#}')
  EXPRESSION_RE = re.compile(r'(?ismu){{.*?}}')
  BLOCK_RE = re.compile(r'(?ismu){%\s*block\s+(\S+)\s*%}')
  ENDBLOCK_RE = re.compile(r'(?ismu){%\s*endblock.*?%}')
  INCLUDE_RE = re.compile(r'(?ismu){%\s*include\s+(\S+)\s*(.*)\s*%}')
  PARENT_RE = re.compile(r'(?ismu){%\s*parent\s+(\S+)\s*%}')
  CODE_RE = re.compile(r'(?iu){%.*?%}')
  MULTI_CODE_RE = re.compile(r'(?ismu){%.*?%}')

  def __init__(self, filename=None, text=None):
    self._filename = filename
    self._text = open(os.path.join(settings.TEMPLATE_ROOT,filename)).read() if filename else text
    self._code = None
    self._compiled_code = None
    self._output = None

  def render(self, context={}):
    parent = None
    skip = False
    indent = u''
    buf = Template.BUFFER
    output = []
    output.append(u"%s = []" % buf)
    text = Template.COMMENT_RE.sub(u'',self._text) # Remove Comments
    tokens = Template.TOKEN_RE.split(text)
    for token in tokens:
      if skip: # Ignore blocks defined in child
        if Template.ENDBLOCK_RE.match(token): skip = False
        continue
      if Template.EXPRESSION_RE.match(token): # Expression (filters)
        expr = token[2:-2].strip()
        val = expr.split(u'|')[0]
        filters = expr.split(u'|')[1:]
        for f in filters: val = u"%s(%s)" % (f,val)
        output.append(u"%s%s.append(unicode(%s))" % (indent,buf,val))
      elif Template.INCLUDE_RE.match(token): # Include tag
        filename,args = Template.INCLUDE_RE.match(token).groups()
        include_context = eval(args) if args else context
        include = Template(filename).render(context=include_context) # TODO: add leading whitespace
        output.append(u"%s%s.append('''%s''')" % (indent,buf,include))
      elif Template.PARENT_RE.match(token): # Parent tag
        parent = Template.PARENT_RE.match(token).group(1)
      elif Template.BLOCK_RE.match(token): # Block tag
        block = '_%s' % Template.BLOCK_RE.match(token).group(1)
        if context.has_key(block): # TODO: add leading whitespace
          output.append(u"%s%s.append(unicode(%s))" % (indent,buf,block))
          skip = True
        elif parent:
          buf = block
          output.insert(0,u"%s = []" % buf)
      elif Template.ENDBLOCK_RE.match(token): # Endblock tag
        if parent:
          output.append(u"%s%s = ''.join(%s)" % (indent,buf,buf))
          buf = Template.BUFFER
      elif Template.CODE_RE.match(token): # Code (single)
        code = token[2:-2].strip()
        if code.startswith(u':') and code.endswith(':'):
          output.append(u"%s%s" % (indent[:-len(Template.INDENT)],code[1:]))
        elif code.endswith(u':'):
          output.append(u"%s%s" % (indent,code))
          indent += Template.INDENT
        elif code.startswith(u':'): indent = indent[:-len(Template.INDENT)]
        else: output.append(u"%s%s" % (indent,code))
      elif Template.MULTI_CODE_RE.match(token): # Code (multi)
        code = token[2:-2]
        output.append(u"%s%s" % (indent,textwrap.dedent(code).strip()))
      else: # Text
        if token.strip():
          token = token.replace(u'\n',u'\\n')
          output.append(u"%s%s.append('''%s''')" % (indent,buf,token))
    self._code = u'\n'.join(output)
    if settings.DEBUG: # write template code to a file for viewing and better tracebacks
      f,fn = tempfile.mkstemp()
      os.write(f,self._code)
      os.close(f)
      execfile(fn,context)
      os.unlink(fn)
    else:
      self._compiled_code = compile(self._code,'','exec')
      exec self._compiled_code in context
    if parent: self._output = Template(parent).render(context=context)
    else: self._output = u''.join(context[Template.BUFFER])
    return self._output
