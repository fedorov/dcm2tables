# take name of the file produced by https://app.quickdatabasediagrams.com
# return dictionary with the mapping of the tables to the attributes
# ignore comments, settings, and connections


class QDBDParser:
  def __init__(self,fileName):
    self.tables = {}

    with open(fileName,'r') as f:
      content = f.readlines()

    # ignore comments and everything after the space
    content = [c for c in content if not c.startswith("#")]
    content = [c.split('#')[0].split(' ')[0].strip() for c in content]

    tableName = None
    for c in content:
      if not len(c):
        tableName = None
        continue
      if c == '-':
        continue

      if tableName is None:
        tableName = c
        self.tables[tableName] = []
      else:
        self.tables[tableName].append(c)

  def getTablesSchema(self):
    return self.tables
