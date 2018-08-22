 # -*- coding: utf-8 -*-
"""
NS trip information
"""
import ns_api
import click
from pymemcache.client import Client as MemcacheClient
import datetime
import json
import requests
import socket
import __main__ as main
import logging
import sys
import os

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

VERSION_NSAPI = '2.7.4'


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


## Check for an update of the notifier
def get_repo_version():
    """
    Get the current version on GitHub
    """
    url = 'https://raw.githubusercontent.com/aquatix/ns-notifications/master/VERSION'
    try:
        response = requests.get(url)
        if response.status_code != 404:
            return response.text.replace('\n', '')
    except requests.exceptions.ConnectionError:
        #return -1
        return None
    return None


def get_local_version():
    """
    Get the locally installed version
    """
    with open ("VERSION", "r") as versionfile:
        return versionfile.read().replace('\n', '')


def check_versions(mc):
    """
    Check whether version of ns-notifier is up-to-date and ns-api is latest version too
    """
    message = {'header': 'ns-notifications needs updating', 'message': None}
    current_version = None
    try:
        version = mc.get('ns-notifier_version')
    except socket.error:
        raise MemcachedNotInstalledException
    if not version:
        version = get_repo_version()
        current_version = get_local_version()
        if not version:
            # 404 or timeout on remote VERSION file, refresh with current_version
            mc.set('ns-notifier_version', current_version, MEMCACHE_VERSIONCHECK_TTL)
        elif version != current_version:
            message['message'] = 'Current version: ' + str(current_version) + '\nNew version: ' + str(version)
            mc.set('ns-notifier_version', version, MEMCACHE_VERSIONCHECK_TTL)

    version = mc.get('ns-api_version')
    if not version:
        if ns_api.__version__ != VERSION_NSAPI:
            # ns-api needs updating
            if message['message']:
                message['message'] = message['message'] + '\n'
            else:
                message['message'] = ''
            message['message'] = message['message'] + 'ns-api needs updating'
            mc.set('ns-api_version', VERSION_NSAPI, MEMCACHE_VERSIONCHECK_TTL)

    if not message['message']:
        # No updating needed, return None object
        message = None
    return message


## Often-used handles
def get_logger():
    """
    Create logging handler
    """
    ## Create logger
    logger = logging.getLogger('ns_notifications')
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler('ns_notifications.log')
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


def update_trips(mc, nsapi, routes, userkey):
    """
    Get the new or changed trips for userkey
    """
    today = datetime.datetime.now().strftime('%d-%m')
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


def get_changed_departures(mc, station, userkey):

    try:
        departures = []
        departures = nsapi.get_departures('Heemskerk')
        print(departures)

    except requests.exceptions.ConnectionError as e:
        #print('[ERROR] connectionerror doing departures')
        errors.append(('Exception doing departures', e))


## Main program
@click.group()
def cli():
    """
    NS-Notifications
    """
    #run_all_notifications()
    #print 'right'
    pass


if not hasattr(main, '__file__'):
    """
    Running in interactive mode in the Python shell
    """
    print("NS Notifier running interactively in Python shell")

elif __name__ == '__main__':
    """
    NS Notifier is ran standalone, rock and roll
    """
    cli()
    #run_all_notifications()
