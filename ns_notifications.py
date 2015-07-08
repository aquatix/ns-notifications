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
import sys

import settings

mc = pylibmc.Client(['127.0.0.1'], binary=True, behaviors={'tcp_nodelay': True, 'ketama': True})


def list_to_json(source_list):
    result = []
    for item in source_list:
        result.append(item.to_json())
    return result


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

    with open('storingen.xml') as fd:
        disruptions = nsapi.parse_disruptions(fd.read())

    stations = []
    try:
        stations = nsapi.get_stations()
    except requests.exceptions.ConnectionError:
        print('Something went wrong connecting to the API')

    stations_json = list_to_json(stations)

    # Cache the stations
    mc['stations_a'] = stations_json
    mc['station_1'] = stations_json[0]

    print(mc['station_1'])

    station1 = ns_api.Station()
    station1.from_json(mc['station_1'])
    print(station1 == stations[0])
    print(station1 == stations[1])

    #stations = []
    #with open('stations.xml') as fd:
    #    stations = nsapi.parse_stations(fd.read())

    sys.exit(0)

    print('-- departures --')
    departures = []
    with open('examples.xml') as fd:
        departures = nsapi.parse_departures(fd.read())

    print('-- trips --')
    trips = []
    with open('reismogelijkheden.xml') as fd:
        trips = nsapi.parse_trips(fd.read())

    if settings.notification_type == 'pb':
        api_key = settings.pushbullet_key
        try:
            p = PushBullet(api_key)
        except pushbullet.errors.InvalidKeyError:
            print('Invalid PushBullet key')
        #logger.info('sending delays to device with id %s', (settings.device_id))
        p.pushNote(settings.device_id, 'NS Vertraging', "\n\n".join(delays_tosend))
