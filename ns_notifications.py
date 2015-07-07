"""
NS trip notifier
"""
from ns_api import ns_api
from pushbullet import PushBullet
import pushbullet
import pylibmc
#import simplejson as json
import __main__ as main
import requests

import settings

mc = pylibmc.Client(['127.0.0.1'], binary=True, behaviors={'tcp_nodelay': True, 'ketama': True})


#if hasattr(main, '__file__'):
#    """
#    Running in interactive mode in the Python shell
#    """
#    print("Running interactively in Python shell")

#elif __name__ == '__main__':
if __name__ == '__main__':
    """
    Notifier is ran standalone, rock and roll
    """


    should_run = True
    if 'nsapi_run' in mc:
        should_run = mc['nsapi_run']
    else:
        #logger.info('no run tuple in memcache, creating')
        mc['nsapi_run'] = should_run

    if not should_run:
        sys.exit(0)

    nsapi = ns_api.NSAPI(settings.username, settings.apikey)

    stations = []
    try:
        stations = nsapi.get_stations()
    except requests.exceptions.ConnectionError:
        print('Something went wrong connecting to the API')

    # Cache the stations
    mc['stations_a'] = stations

    #stations = []
    #with open('stations.xml') as fd:
    #    stations = nsapi.parse_stations(fd.read())

    #departures = []
    #with open('examples.xml') as fd:
    #    departures = nsapi.parse_departures(fd.read())

    #trips = []
    #with open('reismogelijkheden.xml') as fd:
    #    trips = na_api.NSAPI.parse_trips(fd.read())

    if settings.notification_type == 'pb':
        api_key = settings.pushbullet_key
        try:
            p = PushBullet(api_key)
        except pushbullet.errors.InvalidKeyError:
            print('Invalid PushBullet key')
        logger.info('sending delays to device with id %s', (settings.device_id))
        p.pushNote(settings.device_id, 'NS Vertraging', "\n\n".join(delays_tosend))
