import email,smtplib,mimetypes
from util import settings,parse_uri

# settings.EMAIL = 'smtp://user:pass@host:port/?tls=false'
settings.EMAIL = 'smtp://localhost:25/'

class Email(object):
  def __init__(self,sender='',to=[],subject='',body='',attachments=[],cc=[],bcc=[],headers={},return_path=None):
    self.sender = sender
    self.return_path = return_path or self.sender
    self.to = [to] if isinstance(to,basestring) else to
    self.cc = [cc] if isinstance(cc,basestring) else cc
    self.bcc = [bcc] if isinstance(bcc,basestring) else bcc
    self.subject = subject
    self.body = body
    self.attachments = attachments
    self.headers = headers
  def attach(self,content,filename=None,mimetype=None):
    self.attachments.append((content,filename,mimetype))
  @property
  def message(self):
    if self.attachments:
      msg = email.MIMEMultipart.MIMEMultipart()
      msg.attach(email.MIMEText.MIMEText(self.body))
      for content,filename,mimetype in self.attachments:
        guess = mimetypes.guess_type(filename)[0] if filename else 'application/octet-stream'
        maintype,subtype = mimetype.split('/') if mimetype else guess.split('/')
        part = email.MIMEBase.MIMEBase(maintype,subtype)
        part.set_payload(content)
        email.Encoders.encode_base64(part)
        if filename: part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(filename))
        msg.attach(part)
    else: msg = email.MIMEText.MIMEText(self.body)
    msg['Subject'] = self.subject
    msg['From'] = self.sender
    msg['To'] = ', '.join(self.to)
    if self.cc: msg['CC'] = ', '.join(self.cc)
    msg['Date'] = email.Utils.formatdate()
    for key,value in self.headers: msg[key] = value
    return msg
  def send(self):
    uri = URI(settings.EMAIL)
    smtp = smtplib.SMTP(uri.host,uri.port)
    if uri.kwargs.get('tls','').lower() == 'true':
      smtp.ehlo()
      smtp.starttls()
      smtp.ehlo()
    if uri.user and uri.passwd: smtp.login(uri.user,uri.passwd)
    smtp.sendmail(self.return_path, self.to + self.cc + self.bcc, self.message.as_string())
    smtp.close()

if __name__ == '__main__':
  settings.EMAIL = 'smtp://<user>:<pass>@smtp.gmail.com:587/?tls=true'
  # e = Email(sender='',to='',subject='Test Subject',body='Test Body')
  # e = Email(sender='',to=['',''],subject='Test Subject',body='Test Body')
  # e.attach('This is a test attachment.',filename='test.zip')
  # print e.message
  # e.send()
