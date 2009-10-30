CREATE TABLE redirection (
  id INTEGER PRIMARY KEY,
  label TEXT,
  destination TEXT,
  counter INTEGER DEFAULT 0
);

-- INSERT INTO redirection (label,destination) VALUES ('theday','http://www.thedayisshot.com/');
