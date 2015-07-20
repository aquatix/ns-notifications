"""
NS trip notifier
"""
from ns_api import ns_api
from pushbullet import PushBullet
import pushbullet
from pymemcache.client import Client as MemcacheClient
import datetime
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


def format_disruption(disruption):
    return {'header': 'Traject: ' + disruption.line, 'message': disruption.reason + "\n" + disruption.message}


def get_stations(mc):
    """
    Get the list of all stations, put in cache if not already there
    """
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
    return stations


def get_changed_disruptions(mc, disruptions):
    """
    Get the new or changed disruptions
    """
    try:
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

        # Planned disruptions don't have machine-readable date/time and route information, so
        # we skip planned disruptions for this moment
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
        new_or_changed_unplanned = []

    return new_or_changed_unplanned


def get_changed_trips(mc, routes, userkey):
    try:
        today = datetime.datetime.now().strftime('%d-%m')
        today_date = datetime.datetime.now().strftime('%d-%m-%Y')
        current_time = datetime.datetime.now()

        prev_trips = mc.get(str(userkey) + '_trips')
        if prev_trips == None:
            prev_trips = []
        prev_trips = ns_api.list_from_json(prev_trips)
        #print prev_trips
        trips = []

        for route in routes:
            route_time = datetime.datetime.strptime(today_date + " " + route['time'], "%d-%m-%Y %H:%M")
            delta = current_time - route_time
            #if current_time > route_time and delta.total_seconds() > MAX_TIME_PAST:
            #    # the route was too long ago ago, lets skip it
            #    #logger.info('route %s was too long ago, skipped', route)
            #    continue
            if current_time < route_time and abs(delta.total_seconds()) > MAX_TIME_FUTURE:
                # the route is too much in the future, lets skip it
                #logger.info('route %s was too much in the future, skipped', route)
                continue
                print route['time'] + ' ' + route['departure']
            current_trips = nsapi.get_trips(route['time'], route['departure'], route['keyword'], route['destination'], True)
            optimal_trip = ns_api.Trip.get_optimal(current_trips, route['time'])
            if not optimal_trip:
                print "Optimal not found. Alert?"
                # TODO: Get the trip before and the one after route['time']?
            trips.append(optimal_trip)
            print(optimal_trip)

        new_or_changed_trips = ns_api.list_diff(prev_trips, trips)

        mc.set(str(userkey) + '_trips', ns_api.list_to_json(trips))

    except requests.exceptions.ConnectionError as e:
        print('[ERROR] connectionerror doing trips')
        errors.append(('Exception doing trips', e))
        trips = []

    return new_or_changed_trips


def get_changed_departures(mc, station, userkey):

    try:
        departures = []
        departures = nsapi.get_departures('Heemskerk')
        print departures

    except requests.exceptions.ConnectionError as e:
        print('[ERROR] connectionerror doing departures')
        errors.append(('Exception doing departures', e))





if not hasattr(main, '__file__'):
    """
    Running in interactive mode in the Python shell
    """
    print("NS Notifier running interactively in Python shell")

elif __name__ == '__main__':
    """
    NS Notifier is ran standalone, rock and roll
    """

    ## Open memcache
    mc = MemcacheClient(('127.0.0.1', 11211), serializer=json_serializer,
            deserializer=json_deserializer)

    ## NS Notifier userkey (will come from url/cli parameter in the future)
    try:
        userkey = settings.userkey
    except AttributeError:
        userkey = 1


    ## Are we planned to run? (E.g., not disabled through web)
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
    stations = get_stations(mc)


    ## Get the current disruptions (globally)
    disruptions = nsapi.get_disruptions()
    changed_disruptions = get_changed_disruptions(mc, disruptions)


    ## Get the information on the list of trips configured by the user
    trips = get_changed_trips(mc, settings.routes, userkey)
    print(trips)


    if settings.notification_type == 'pb':
        api_key = settings.pushbullet_key
        try:
            p = PushBullet(api_key)
        except pushbullet.errors.InvalidKeyError:
            print('Invalid PushBullet key')
        #logger.info('sending delays to device with id %s', (settings.device_id))
        #p.pushNote(settings.device_id, 'NS Vertraging', "\n\n".join(delays_tosend))
        if changed_disruptions:
            # There are disruptions that are new or changed since last run
            for disruption in changed_disruptions:
                message = format_disruption(disruption)
                print message
                p.pushNote(settings.device_id, message['header'], message['message'])
