# ns-notifications
Get notified when your NS (Dutch Railways) train is delayed, or makes a quick transfer which normally you wouldn't catch possible

## Installation

Create a new virtualenv and install the dependencies:

```
mkvirtualenv ns-notifications
pip install -r requirements.txt
```

You might have to install the memcached-dev system package first. On .deb-based systems, this is done with:

```
apt-get install libmemcached-dev
```

Also, memcached itself has to be running (e.g., `apt-get install memcached`).
