# ns-notifications
Get notified when your NS (Dutch Railways) train is delayed, or makes a quick transfer which normally you wouldn't catch possible

## Installation

Clone this project to your local drive.

As ns-api is not in PyPy yet, you'll have to clone it too and symlink it to this project:

```
git clone https://github.com/aquatix/ns-api.git
cd ns-notifications
ln -s ../ns-api/ns_api
```

Create a new virtualenv and install the dependencies:

```
mkvirtualenv ns-notifications
pip install -r requirements.txt
```

Run the same `pip` command in the ns-api directory.

Also, memcached itself has to be running (e.g., `apt-get install memcached`; ns-notifications assumes port 11211).
