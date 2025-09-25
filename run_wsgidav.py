import os
import sys
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgiref.simple_server import make_server
from wsgidav.fs_dav_provider import FilesystemProvider
from caldav.dav_provider import CalDAVProvider

def main():
    # Add the project directory to the python path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
    import django
    django.setup()

    # Load configuration from a file
    config_file = os.path.join(os.path.dirname(__file__), "wsgidav.conf")
    from wsgidav.xml_tools import use_lxml
    from wsgidav.wsgidav_app import WsgiDAVApp

    # Check if lxml is available
    if not use_lxml:
        print("LXML is not available. Please install it using 'pip install lxml'.")
        sys.exit(1)

    # Create the WsgiDAVApp instance from the configuration file
    app = WsgiDAVApp.new_from_config(config_file)

    # Get host and port from the app's configuration
    host = app.config["host"]
    port = app.config["port"]

    # Use a simple WSGI server to run the app
    httpd = make_server(host, port, app)
    print(f"WsgiDAV server running on http://{host}:{port}/")
    httpd.serve_forever()

if __name__ == "__main__":
    main()