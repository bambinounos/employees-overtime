import os
import sys

def main():
    # Add the project directory to the python path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
    import django
    django.setup()

    from wsgidav.wsgidav_app import WsgiDAVApp
    from caldav.dav_provider import CalDAVProvider

    config = {
        "provider_mapping": {
            "/": CalDAVProvider(),
        },
        "host": "0.0.0.0",
        "port": 8080,
        "verbose": 1,
        "props_manager": "wsgidav.props.memory_props_manager.MemoryPropsManager",
        "locks_manager": "wsgidav.locks.memory_locks_manager.MemoryLocksManager",
        "http_authenticator": {
            "domain_controller": None,  # Use SimpleDomainController
        },
        "simple_dc": {
            "user_mapping": {
                "*": True,  # Allow anonymous access
            }
        },
    }

    app = WsgiDAVApp(config)

    # Use a simple WSGI server to run the app
    from wsgiref.simple_server import make_server
    httpd = make_server(config["host"], config["port"], app)
    print(f"WsgiDAV server running on http://{config['host']}:{config['port']}/")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
