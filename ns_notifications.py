"""
NS trip notifier
"""
from ns_api import ns_api
from pushbullet import PushBullet
import pushbullet
#import pylibmc
from pymemcache.client import Client as MemcacheClient
#import simplejson as json
import json
import __main__ as main
import requests
import sys

import settings

#mc = pylibmc.Client(['127.0.0.1'], binary=True, behaviors={'tcp_nodelay': True, 'ketama': True})


def json_serializer(key, value):
    if type(value) == str:
        return value, 1
    #if issubclass(value, ns_api.BaseObject):
    #    print ("instance of NS-API object")
    #    return value.to_json(), 3
    return json.dumps(value), 2

def json_deserializer(key, value, flags):
    if flags == 1:
        return value
    if flags == 2:
        return json.loads(value)
    raise Exception("Unknown serialization format")


mc = MemcacheClient(('127.0.0.1', 11211), serializer=json_serializer,
        deserializer=json_deserializer)


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

    should_run = mc.get('nsapi_run')
    if should_run == None:
        should_run = True
        #logger.info('no run tuple in memcache, creating')
        mc.set('nsapi_run', should_run)

    print(should_run)

    if not should_run:
        sys.exit(0)

    errors = []
    nsapi = ns_api.NSAPI(settings.username, settings.apikey)

    #with open('storingen.xml') as fd:
    #    disruptions = nsapi.parse_disruptions(fd.read())
    try:
        disruptions = nsapi.get_disruptions()

        prev_disruptions = mc.get('prev_disruptions')
        if prev_disruptions == None:
            prev_disruptions = {'unplanned': [], 'planned': []}

        prev_disruptions['unplanned'] = ns_api.list_from_json(prev_disruptions['unplanned'])
        prev_disruptions['planned'] = ns_api.list_from_json(prev_disruptions['planned'])

        new_or_changed_unplanned = ns_api.list_diff(prev_disruptions['unplanned'], disruptions['unplanned'])
        print(new_or_changed_unplanned)

        unchanged_unplanned = ns_api.list_same(prev_disruptions['unplanned'], disruptions['unplanned'])

        prev_unplanned = new_or_changed_unplanned + unchanged_unplanned



        #new_or_changed_planned = ns_api.list_diff(prev_disruptions['planned'], disruptions['planned'])
        #print(new_or_changed_planned)
        #for plan in new_or_changed_planned: 
        #    print plan.key
        #    print plan.message
        #    print "------"

        #unchanged_planned = ns_api.list_same(prev_disruptions['planned'], disruptions['planned'])

        #prev_planned = new_or_changed_planned + unchanged_planned

        # Update the cached list with the current information
        #prev_unplanned_json = ns_api.list_to_json(prev_unplanned)
        #mc.set('prev_disruptions', ns_api.list_to_json(prev_unplanned))

    except requests.exceptions.ConnectionError as e:
        print('[ERROR] connectionerror doing disruptions')
        errors.append(('Exception doing disruptions', e))

    try:
        #stations = mc['stations']
        stations = mc.get('stations')
    except KeyError:
        stations = []
        try:
            stations = nsapi.get_stations()
        except requests.exceptions.ConnectionError:
            print('Something went wrong connecting to the API')

        stations_json = ns_api.list_to_json(stations)
        # Cache the stations
        #mc['stations'] = stations_json
        mc.set('stations', stations_json)

    try:
        trips = []

        #for route in settings.routes:
        #    print route['time'] + ' ' + route['departure']
        #    trips = nsapi.get_trips(route['time'], route['departure'], route['keyword'], route['destination'])

        route = settings.routes[0]
        print route['time'] + ' ' + route['departure']
        trips = nsapi.get_trips(route['time'], route['departure'], route['keyword'], route['destination'], True)
        optimal_found = False
        for trip in trips:
            if trip.is_optimal:
                print "Optimal found:"
                print trip
                optimal_found = True
                print 'Delay on this trip: ' + str(trip.delay)

        if not optimal_found:
            print "Optimal not found. Alert?"
            # TODO: Get the trip before and the one after route['time']?

    except requests.exceptions.ConnectionError as e:
        print('[ERROR] connectionerror doing trips')
        errors.append(('Exception doing trips', e))

    print errors

    sys.exit(0)

    try:
        departures = []
        departures = nsapi.get_departures('Heemskerk')
        print departures

    except requests.exceptions.ConnectionError as e:
        print('[ERROR] connectionerror doing departures')
        errors.append(('Exception doing departures', e))



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
