# Activate virtualenv
import sys
import settings
activate_this = getattr(settings, 'VENV', None)

if (sys.version_info > (3, 0)):
    # Python 3
    with open(activate_this) as file_:
        exec(file_.read(), dict(__file__=activate_this))
else:
    # Python 2
    if activate_this:
        execfile(activate_this, dict(__file__=activate_this))

from server import app as application

if __name__ == "__main__":
    # application is ran standalone
    application.run(debug=settings.DEBUG)
