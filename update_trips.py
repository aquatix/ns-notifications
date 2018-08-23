 # -*- coding: utf-8 -*-
"""
NS trip information updater
"""
import datetime
import json
import logging
import sys

import click
import ns_api
import requests
from pymemcache.client import Client as MemcacheClient

import __main__ as main

try:
    import settings
except ImportError:
    print('Copy settings_example.py to settings.py and set the configuration to your own preferences')
    sys.exit(1)


# Only plan routes that are at maximum half an hour in the past or an hour in the future
MAX_TIME_PAST = 1800
MAX_TIME_FUTURE = 3600

# Set max time to live for a key to an hour
MEMCACHE_TTL = 3600
MEMCACHE_VERSIONCHECK_TTL = 3600 * 12
MEMCACHE_DISABLING_TTL = 3600 * 6


class MemcachedNotInstalledException(Exception):
    pass


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


## Often-used handles
def get_logger():
    """
    Create logging handler
    """
    ## Create logger
    logger = logging.getLogger('nsapi_updater')
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler('nsapi_updater.log')
    fh.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    return logger


## Retrieval
def get_stations(mc, nsapi):
    """
    Gets the list of all stations, put in cache if not already there
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


def update_trips_for_user(mc, nsapi, routes, userkey):
    """
    Gets up-to-date information on trips for `userkey`
    """
    today_date = datetime.datetime.now().strftime('%d-%m-%Y')
    current_time = datetime.datetime.now()

    trips = []

    for route in routes:
        if len(route['time']) <= 5:
            route_time = datetime.datetime.strptime(today_date + " " + route['time'], "%d-%m-%Y %H:%M")
        else:
            route_time = datetime.datetime.strptime(route['time'], "%d-%m-%Y %H:%M")
        delta = current_time - route_time
        if current_time > route_time and delta.total_seconds() > MAX_TIME_PAST:
            # the route was too long ago ago, lets skip it
            continue
        if current_time < route_time and abs(delta.total_seconds()) > MAX_TIME_FUTURE:
            # the route is too much in the future, lets skip it
            continue
        try:
            keyword = route['keyword']
        except KeyError:
            keyword = None
        current_trips = nsapi.get_trips(route['time'], route['departure'], keyword, route['destination'], True)
        optimal_trip = ns_api.Trip.get_actual(current_trips, route['time'])
        #optimal_trip = ns_api.Trip.get_optimal(current_trips)
        if not optimal_trip:
            #print("Optimal not found. Alert?")
            # TODO: Get the trip before and the one after route['time']?
            pass
        else:
            try:
                # User set a minimum treshold for departure, skip if within this limit
                minimal_delay = int(route['minimum'])
                trip_delay = optimal_trip.delay
                if (not optimal_trip.has_delay) or (optimal_trip.has_delay and trip_delay['departure_delay'] != None and trip_delay['departure_delay'].seconds//60 < minimal_delay and optimal_trip.going):
                    # Trip is going, has no delay or one that is below threshold, ignore
                    optimal_trip = None
            except KeyError:
                # No 'minimum' setting found, just continue
                pass
        if optimal_trip:
            trips.append(optimal_trip)
        #print(optimal_trip)

    new_or_changed_trips = ns_api.list_diff(prev_trips, trips)
    #prev_trips = new_or_changed_trips + trips
    save_trips = ns_api.list_merge(prev_trips, trips)

    mc.set(str(userkey) + '_trips', ns_api.list_to_json(save_trips), MEMCACHE_TTL)
    return new_or_changed_trips


## Main program
@click.group()
def cli():
    """
    NS trip information updater
    """
    pass


@click.command()
def update_trips():
    logger = get_logger()

    # Connect to the Memcache daemon
    mc = MemcacheClient(('127.0.0.1', 11211), serializer=json_serializer,
                        deserializer=json_deserializer)

    nsapi = ns_api.NSAPI(settings.username, settings.apikey)

    for userkey in settings.userconfigs:
        userconfig = settings.userconfigs[userkey]
        logger.debug('Getting trips for user %s', userkey)
        update_trips_for_user(mc, nsapi, userconfig['routegroups'], userkey)


if not hasattr(main, '__file__'):
    """
    Running in interactive mode in the Python shell
    """
    print("NS trip information updater is running interactively in Python shell")

elif __name__ == '__main__':
    """
    Running stand-alone
    """
    cli()
