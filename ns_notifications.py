 # -*- coding: utf-8 -*-
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
import logging
import sys

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
    return {'header': 'Traject: ' + disruption.line, 'message': u'⚠ ' + disruption.reason + "\n" + disruption.message}
    #return {'header': 'Traject: ' + disruption.line, 'message': disruption.reason + "\n" + disruption.message}


def format_trip(trip, text_type='long'):
    """
    text_type: (long|symbol)
    """
    trip_delay = trip.delay
    message = u''
    if trip_delay['requested_differs']:
        #message = message + 'Vertrekt andere tijd: ' + ns_api.simple_time(trip_delay['requested_differs']) + "\n"
        #message = message + u'↦ ' + ns_api.simple_time(trip.requested_time) + u' ➔ ' + ns_api.simple_time(trip_delay['requested_differs'])# + "\n"
        message = message + u'↦ ' + ns_api.simple_time(trip_delay['requested_differs']) + u' (' + ns_api.simple_time(trip.requested_time)
    if trip_delay['departure_delay']:
        #message = message + 'Vertraging: ' + ns_api.simple_time(trip_delay['departure_delay']) + "\n"
        message = message + u' 🕖 ' + ns_api.simple_time(trip_delay['departure_delay']) +")\n"
    if trip.arrival_time_actual != trip.arrival_time_planned:
        #message = message + 'Andere aankomsttijd: ' + ns_api.simple_time(trip.arrival_time_actual) + ' ipv ' + ns_api.simple_time(trip.arrival_time_planned) + ' (' + ns_api.simple_time(trip.arrival_time_actual - trip.arrival_time_planned) + ")\n"
        message = message + u'⇥ ' + ns_api.simple_time(trip.arrival_time_actual) + u' (' + ns_api.simple_time(trip.arrival_time_planned) + u' 🕖 ' + ns_api.simple_time(trip.arrival_time_actual - trip.arrival_time_planned) + ")\n"
    subtrips = []
    for part in trip.trip_parts:
        if part.has_delay:
            subtrips.append(part.transport_type + ' naar ' + part.destination + ' van ' + ns_api.simple_time(part.departure_time) + ' vertrekt van spoor ' + part.stops[0].platform)
            for stop in part.stops:
                if stop.delay:
                    #subtrips.append('Stop ' + stop.name + ' @ ' + ns_api.simple_time(stop.time) + ' ' + stop.delay)
                    subtrips.append(u'🚉 ' + stop.name + ' @ ' + ns_api.simple_time(stop.time) + ' ' + stop.delay)
    message = message + u'\n'.join(subtrips)
    return {'header': trip.trip_parts[0].transport_type + ' ' + trip.departure + '-' + trip.destination + ' (' + ns_api.simple_time(trip.requested_time) + ')', 'message': message}


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
    #prev_disruptions = None
    prev_disruptions = mc.get('prev_disruptions')
    # TODO: check whether this went ok
    if prev_disruptions == None or prev_disruptions == []:
        prev_disruptions = {'unplanned': [], 'planned': []}

    #print prev_disruptions['unplanned']
    #prev_disruptions['unplanned'] = ns_api.list_from_json(prev_disruptions['unplanned'])
    prev_disruptions_unplanned = ns_api.list_from_json(prev_disruptions['unplanned'])
    #prev_disruptions['planned'] = ns_api.list_from_json(prev_disruptions['planned'])

    #new_or_changed_unplanned = ns_api.list_diff(prev_disruptions['unplanned'], disruptions['unplanned'])
    new_or_changed_unplanned = ns_api.list_diff(prev_disruptions_unplanned, disruptions['unplanned'])
    #print('New or changed unplanned disruptions:')
    #print(new_or_changed_unplanned)

    #unchanged_unplanned = ns_api.list_same(prev_disruptions['unplanned'], disruptions['unplanned'])

    #prev_unplanned = new_or_changed_unplanned + unchanged_unplanned
    #prev_unplanned = new_or_changed_unplanned + prev_disruptions_unplanned
    save_unplanned = ns_api.list_merge(prev_disruptions_unplanned, new_or_changed_unplanned)

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
    #mc.set('prev_disruptions', {'unplanned': ns_api.list_to_json(prev_unplanned), 'planned': []})
    #mc.set('prev_disruptions', {'unplanned': ns_api.list_to_json(disruptions['unplanned']), 'planned': []}, MEMCACHE_TTL)
    mc.set('prev_disruptions', {'unplanned': ns_api.list_to_json(save_unplanned), 'planned': []}, MEMCACHE_TTL)
    return new_or_changed_unplanned


def get_changed_trips(mc, routes, userkey):
    """
    Get the new or changed trips for userkey
    """
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
        if len(route['time']) == 5:
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
        optimal_trip = ns_api.Trip.get_optimal(current_trips, route['time'])
        if not optimal_trip:
            print "Optimal not found. Alert?"
            # TODO: Get the trip before and the one after route['time']?
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

    ## Open memcache
    mc = MemcacheClient(('127.0.0.1', 11211), serializer=json_serializer,
            deserializer=json_deserializer)

    ## NS Notifier userkey (will come from url/cli parameter in the future)
    try:
        userkey = settings.userkey
    except AttributeError:
        userkey = 1


    ## Are we planned to run? (E.g., not disabled through web)
    try:
        should_run = mc.get('nsapi_run')
    except:
        should_run = True
    if should_run == None:
        should_run = True
        #logger.info('no run tuple in memcache, creating')
        mc.set('nsapi_run', should_run)

    #print('should run? ' + str(should_run))
    logger.debug('Should run: ' + str(should_run))

    if not should_run:
        sys.exit(0)

    errors = []
    nsapi = ns_api.NSAPI(settings.username, settings.apikey)

    ## Get the list of stations
    stations = get_stations(mc)


    ## Get the current disruptions (globally)
    changed_disruptions = []
    get_disruptions = True
    try:
        if settings.skip_disruptions:
            get_disruptions = False
    except AttributeError:
        logger.error('Missing pushbullet_channel_tag setting')
    if get_disruptions:
        try:
            disruptions = nsapi.get_disruptions()
            changed_disruptions = get_changed_disruptions(mc, disruptions)
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            print('[ERROR] connectionerror doing disruptions')
            logger.error('Exception doing disruptions ' + repr(e))
            errors.append(('Exception doing disruptions', e))


    ## Get the information on the list of trips configured by the user
    try:
        trips = get_changed_trips(mc, settings.routes, userkey)
        #print(trips)
    except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
        print('[ERROR] connectionerror doing trips')
        logger.error('Exception doing trips ' + repr(e))
        errors.append(('Exception doing trips', e))
        trips = []



    if settings.notification_type == 'pb':
        api_key = settings.pushbullet_key
        try:
            p = PushBullet(api_key)
        except pushbullet.errors.InvalidKeyError:
            print('Invalid PushBullet key')
            sys.exit(1)
        devs = p.devices
        sendto_device = None
        try:
            if settings.pushbullet_device_id != None:
                for dev in devs:
                    #print dev.device_iden + ' ' + dev.nickname
                    if dev.device_iden == settings.pushbullet_device_id:
                        sendto_device = dev
        except AttributeError:
            # pushbullet_device_id wasn't even found in settings.py
            pass
        if not sendto_device:
            print "Please select a device from the PushBullet list and set as pushbullet_device_id in settings.py"
            for dev in devs:
                print("{: >20} {: >40}".format(dev.device_iden, dev.nickname))
            sys.exit(1)
        if changed_disruptions:
            # There are disruptions that are new or changed since last run
            sendto_channel = None
            try:
                if settings.pushbullet_use_channel:
                    channels = p.channels
                    for channel in channels:
                        #print dev.device_iden + ' ' + dev.nickname
                        if channel.channel_tag == settings.pushbullet_channel_tag:
                            sendto_channel = channel
                    if not sendto_channel:
                        logger.error('PushBullet channel configured, but tag "' + settings.pushbullet_channel_tag + '" not found')
                        print('PushBullet channel configured, but tag "' + settings.pushbullet_channel_tag + '" not found')
            except AttributeError, e:
                logger.error('PushBullet channel settings not found - ' + str(e))
                print('PushBullet channel settings not found, see settings_example.py - ' + str(e))

            for disruption in changed_disruptions:
                message = format_disruption(disruption)
                logger.debug(message)
                #print message
                if sendto_channel:
                    sendto_channel.push_note(message['header'], message['message'])
                else:
                    p.push_note(message['header'], message['message'], sendto_device)
        if trips:
            for trip in trips:
                if trip.has_delay:
                    message = format_trip(trip)
                    #print message
                    logger.debug(message)
                    #p.push_note('title', 'body', sendto_device)
                    p.push_note(message['header'], message['message'], sendto_device)
