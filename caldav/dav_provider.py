from wsgidav.dav_provider import DAVProvider
from caldav.resources import RootCollection

class CalDAVProvider(DAVProvider):
    def __init__(self):
        super().__init__()

    def get_resource_inst(self, path, environ):
        if path == "/":
            return RootCollection(path, environ)
        return None
