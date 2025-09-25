from django.contrib.auth import authenticate
from wsgidav.domain_controller import BaseDomainController

class DjangoDomainController(BaseDomainController):
    def __init__(self, environ):
        super().__init__(environ)

    def get_domain_realm(self, path_info, environ):
        return "Django Authentication"

    def require_authentication(self, realm, environ):
        return True

    def basic_auth_user(self, realm, user_name, password, environ):
        user = authenticate(username=user_name, password=password)
        if user is not None and user.is_active:
            environ["wsgidav.auth.user_name"] = user_name
            environ["wsgidav.auth.user_obj"] = user
            return True
        return False