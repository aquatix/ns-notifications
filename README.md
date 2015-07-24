# ns-notifications
Get notified when your NS (Dutch Railways) train is delayed, or makes a quick transfer which normally you wouldn't catch possible

## Installation

Clone this project to your local drive.

As ns-api is not in [PyPI](https://pypi.python.org/pypi) yet, you'll have to clone it too and symlink it to this project:

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

Run the same `pip` command in the ns-api directory so it install the ns-api dependencies in the same virtualenv.

Also, memcached itself has to be running (e.g., `apt-get install memcached`; ns-notifications assumes port 11211).

Then copy `settings_example.py` to `settings.py` and modify the configuration to your needs. You might want to check which index your desired device is on in the Pushbullet list (you can also go to your account on [Pushbullet.com](https://www.pushbullet.com/) and count in your device list, starting with 0 for the first).

N.B.: if you encounter issues after updating from the repo, try checking [settings_example.py](settings_example.py) against your settings.py. Some new configuration items might be added.

### NS API key

To actually be able to query the [Nederlandse Spoorwegen API](http://www.ns.nl/api/api), you [need to request a key](https://www.ns.nl/ews-aanvraagformulier/). Provide a good reason and you will likely get it mailed to you (it might take some days).

After receiving the key, put it together with the email address you used in settings.py


## Running

`ns_notifications.py` is best called through a crontab entry, for example:

```
# Call every five minutes from 7 to 10 and then from 16 to 18 hours:
*/5  7-9  * * 1-5 cd /home/username/bin/crontab/ns-notifications; /usr/bin/python ns-notifications.py
*/5 16-17 * * 1-5 cd /home/username/bin/crontab/ns-notifications; /usr/bin/python ns-notifications.py
```

It can be disabled by setting the `nsapi_run` tuple in memcache to `False`.

`notifications_server.py` has been included to provide a web interface.

```
pip install Flask
```
