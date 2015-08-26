# ns-notifications
Get notified when your NS (Dutch Railways) train is delayed, or makes a quick transfer which normally you wouldn't catch possible. Makes use of the [ns-api](https://github.com/aquatix/ns-api) library.

## Installation

Clone this project to your local drive:

```
git clone https://github.com/aquatix/ns-notifications.git
```

As ns-api is not in [PyPI](https://pypi.python.org/pypi) yet, you'll have to clone it too and symlink it to this project:

```
git clone https://github.com/aquatix/ns-api.git
cd ns-notifications
ln -s ../ns-api/ns_api
```

First check if you use a version of Python that's at least 2.7.9: `python --version`. If not, *go to* the "Python <2.7.9" section first!

Create a new virtualenv (`mkvirtualenv` is a command when you have [virtualenvwrapper](https://virtualenvwrapper.readthedocs.org/en/latest/) installed - you can do so with `sudo apt-get install virtualenvwrapper`) and install the dependencies:

```
mkvirtualenv ns-notifications   # only if you didn't do so already
pip install -r requirements.txt
```

Run the same `pip` command in the ns-api directory so it installs the ns-api dependencies in the same virtualenv.

Also, memcached itself has to be running (e.g., `apt-get install memcached`; ns-notifications assumes port 11211).

Then copy `settings_example.py` to `settings.py` and modify the configuration to your needs. You might want to check what id your desired device has in the Pushbullet list. If an invalid id is provided, ns_notifications.py will provide you with a list of your devices with their corresponding id's.

N.B.: if you encounter issues after updating from the repo, try checking [settings_example.py](settings_example.py) against your settings.py. Some new configuration items might be added.


### Upgrading

If you got a notification that ns-notifier needs upgrading, you can run `./run_notifier upgrade`. This will do a `git pull` and other necessary updates. Updating ns-api can't be done (yet) through this method though. To upgrade, just do a `git pull` in its directory.


### Python <2.7.9

If you run an older version of Python (for example Ubuntu 14.04 LTS ships with 2.7.6), the `requests` library needs a more secure version of the ssl sub system.

On Ubuntu, first install some SSL and Python header files and then install the `requests` extension:

```
mkvirtualenv ns-notifications   # if you didn't do so already
sudo apt-get install python-dev libffi-dev libssl-dev
pip install 'requests[security]'
```

Now continue with the steps above, starting from the line with `requirements.txt`.


### NS API key

To actually be able to query the [Nederlandse Spoorwegen API](http://www.ns.nl/api/api), you [need to request a key](https://www.ns.nl/ews-aanvraagformulier/). Provide a good reason and you will likely get it mailed to you (it might take some days).

After receiving the key, put it together with the email address you used in `settings.py`.


## Running

`ns_notifications.py` is best called through a crontab entry. The `run_notifier` script is provided for convenience, as it enables the virtualenv for you (assuming the name 'ns-notifications' and virtualenvwrapper installed for the `workon` command). For example:

```
# Call every five minutes from 7 to 10 and then from 16 to 18 hours:
*/5  7-9  * * 1-5 cd /home/username/bin/crontab/ns-notifications; ./run_notifier
*/5 16-17 * * 1-5 cd /home/username/bin/crontab/ns-notifications; ./run_notifier
```

It can be disabled by setting the `nsapi_run` tuple in memcache to `False`.


## Screenshot

![PushBullet notifications](http://aquariusoft.org/files/projects/20150729_ns-notifications.png)


## Web frontend

`server.py` has been included to provide a web interface. You can just run that file and it will enable a simple website to be available on your server at port 8086.

After creating the `ns-notifications` virtualenv, you will have to install the requirements for the server (type `workon ns-notifications` if you don't have the environment enabled):

```
pip install -r requirements_server.txt
```

Now you can run the server by starting the `run_server` script. It will open a small web server on port 8086 of your machine, which you can make GET requests on to check for the status (just the root document, so for example http://example.com:8086/), to disable notifications for a bit (/disable/<keyword>) or enable them (/enable/<keyword>). The `keyword` variable here is intended to be replaced by a location for example, which really is just for your convenience (for example when you use Tasker, you can have it do a request on http://example.com:8086/disable/work when you arrive at work, but you can put whatever text you like in there).
