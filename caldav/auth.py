from django.contrib.auth import authenticate
from wsgidav.dc.base_dc import BaseDomainController


class DjangoDomainController(BaseDomainController):
    def __init__(self, wsgidav_app, config):
        super().__init__(wsgidav_app, config)

    def get_domain_realm(self, path_info, environ):
        return self._calc_realm_from_path_provider(path_info, environ)

    def require_authentication(self, realm, environ):
        return True

    def supports_http_digest_auth(self):
        return False

    def basic_auth_user(self, realm, user_name, password, environ):
        user = authenticate(username=user_name, password=password)
        if user is not None and user.is_active:
            environ["wsgidav.auth.user_name"] = user_name
            environ["wsgidav.auth.user_obj"] = user
            return True
        return False
