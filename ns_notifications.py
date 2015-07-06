"""
NS trip notifier
"""
from ns_api import ns_api
from pushbullet import PushBullet
import pylibmc
#import simplejson as json
import __main__ as main

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

    nsapi = ns_api.NSAPI(settings.username, settings.apikey)

    nsapi.get_stations()

    #stations = []
    #with open('stations.xml') as fd:
    #    stations = nsapi.parse_stations(fd.read())

    #departures = []
    #with open('examples.xml') as fd:
    #    departures = nsapi.parse_departures(fd.read())

    #trips = []
    #with open('reismogelijkheden.xml') as fd:
    #    trips = na_api.NSAPI.parse_trips(fd.read())
