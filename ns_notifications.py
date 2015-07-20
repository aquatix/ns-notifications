"""
NS trip notifier
"""
from ns_api import ns_api
from pushbullet import PushBullet
import pushbullet
#import pylibmc
from pymemcache.client import Client as MemcacheClient
import datetime
#import simplejson as json
import json
import requests
import __main__ as main
import sys

import settings

# Only plan routes that are at maximum half an hour in the past or an hour in the future
MAX_TIME_PAST = 1800
MAX_TIME_FUTURE = 3600


## Helper functions for memcache serialisation
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


## Open memcache
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

    print('should run? ' + str(should_run))

    if not should_run:
        sys.exit(0)

    errors = []
    nsapi = ns_api.NSAPI(settings.username, settings.apikey)

    ## Get the list of stations
    try:
        stations = mc.get('stations')
    except KeyError:
        stations = []
        try:
            stations = nsapi.get_stations()
        except requests.exceptions.ConnectionError:
            print('Something went wrong connecting to the API')

        stations_json = ns_api.list_to_json(stations)
        # Cache the stations
        mc.set('stations', stations_json)


    ## Get the current disruptions (globally)
    try:
        disruptions = nsapi.get_disruptions()

        #prev_disruptions = None
        prev_disruptions = mc.get('prev_disruptions')
        # TODO: check whether this went ok
        if prev_disruptions == None or prev_disruptions == []:
            prev_disruptions = {'unplanned': [], 'planned': []}

        prev_disruptions['unplanned'] = ns_api.list_from_json(prev_disruptions['unplanned'])
        #prev_disruptions['planned'] = ns_api.list_from_json(prev_disruptions['planned'])

        new_or_changed_unplanned = ns_api.list_diff(prev_disruptions['unplanned'], disruptions['unplanned'])
        print('New or changed unplanned disruptions:')
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
        mc.set('prev_disruptions', {'unplanned': ns_api.list_to_json(prev_unplanned), 'planned': []})

    except requests.exceptions.ConnectionError as e:
        print('[ERROR] connectionerror doing disruptions')
        errors.append(('Exception doing disruptions', e))


    ## Get the information on the list of trips configured by the user
    try:
        today = datetime.datetime.now().strftime('%d-%m')
        today_date = datetime.datetime.now().strftime('%d-%m-%Y')
        current_time = datetime.datetime.now()

        trips = []

        #for route in settings.routes:
        #    if current_time > route_time and delta.total_seconds() > MAX_TIME_PAST:
        #        # the route was too long ago ago, lets skip it
        #        logger.info('route %s was too long ago, skipped', route)
        #        continue
        #    if current_time < route_time and abs(delta.total_seconds()) > MAX_TIME_FUTURE:
        #        # the route is too much in the future, lets skip it
        #        logger.info('route %s was too much in the future, skipped', route)
        #        continue
        #        print route['time'] + ' ' + route['departure']
        #    trips = nsapi.get_trips(route['time'], route['departure'], route['keyword'], route['destination'])

        route = settings.routes[0]
        route_time = datetime.datetime.strptime(today_date + " " + route['time'], "%d-%m-%Y %H:%M")
        delta = current_time - route_time
        print route['time'] + ' ' + route['departure']
        if current_time > route_time and delta.total_seconds() > MAX_TIME_PAST:
            print "TOO LATE"
        if current_time < route_time and abs(delta.total_seconds()) > MAX_TIME_FUTURE:
            print "TOO EARLY"
        trips = nsapi.get_trips(route['time'], route['departure'], route['keyword'], route['destination'], True)
        optimal_trip = ns_api.Trip.get_optimal(trips, route['time'])

        print ns_api.list_to_json(trips)

        if not optimal_trip:
            print "Optimal not found. Alert?"
            # TODO: Get the trip before and the one after route['time']?

        print optimal_trip

    except requests.exceptions.ConnectionError as e:
        print('[ERROR] connectionerror doing trips')
        errors.append(('Exception doing trips', e))


    ## Wrapping up
    print "errors:"
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
