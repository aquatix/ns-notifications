 # -*- coding: utf-8 -*-
"""
NS trip notifier
"""
import ns_api
import click
from pushbullet import PushBullet
import pushbullet
from pymemcache.client import Client as MemcacheClient
import datetime
import json
import requests
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

VERSION_NSAPI = '2.3'


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
    response = requests.get(url)
    if response.status_code == 404:
        return None
    else:
        return response.text.replace('\n', '')


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
    version = mc.get('ns-notifier_version')
    if not version:
        version = get_repo_version()
        current_version = get_local_version()
        if version != current_version:
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


def get_pushbullet_config(logger=None):
    """
    Return PushBullet handle and device to send to
    """

    api_key = settings.pushbullet_key
    try:
        p = PushBullet(api_key)
    except pushbullet.errors.InvalidKeyError:
        print('Invalid PushBullet key')
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        if logger:
            logger.error('PushBullet connection error while getting config - ' + str(e))
        return None, None
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
        #sys.exit(1)

    return p, sendto_device


## Format messages
def format_disruption(disruption):
    """
    Format a disruption on a trajectory
    """
    return {'timestamp': ns_api.simple_time(disruption.timestamp), 'header': u'Traject: ' + disruption.line, 'message': u'⚠ ' + disruption.reason + "\n" + disruption.message}
    #return {'header': 'Traject: ' + disruption.line, 'message': disruption.reason + "\n" + disruption.message}


def format_trip(trip, text_type='long'):
    """
    Format a Trip, providing an overview of all events (delays, messages etc)

    text_type: (long|symbol)
    """
    trip_delay = trip.delay
    message = u''
    if trip_delay['requested_differs']:
        #message = message + u'↦ ' + ns_api.simple_time(trip_delay['requested_differs']) + u' (' + ns_api.simple_time(trip.requested_time)
        message = message + u'↦ ' + ns_api.simple_time(trip.requested_time)
    if trip_delay['departure_delay']:
        #message = message + u' 🕖 ' + ns_api.simple_time(trip_delay['departure_delay']) +")\n"
        message = message + u' +' + ns_api.simple_time(trip_delay['departure_delay']) +"\n"
    if trip.arrival_time_actual != trip.arrival_time_planned:
        #message = message + u'⇥ ' + ns_api.simple_time(trip.arrival_time_actual) + u' (' + ns_api.simple_time(trip.arrival_time_planned) + u' 🕖 ' + ns_api.simple_time(trip.arrival_time_actual - trip.arrival_time_planned) + ")\n"
        message = message + u'⇥ ' + ns_api.simple_time(trip.arrival_time_planned) + u' +' + ns_api.simple_time(trip.arrival_time_actual - trip.arrival_time_planned) + "\n"

    if trip.trip_remarks:
        for remark in trip.trip_remarks:
            if remark.is_grave:
                message = u'⚠ ' + message + remark.message + '\n'
            else:
                message = u'★ ' + message + remark.message + '\n'

    subtrips = []
    for part in trip.trip_parts:
        if part.has_delay:
            #subtrips.append(part.transport_type + ' naar ' + part.destination + ' van ' + ns_api.simple_time(part.departure_time) + ' vertrekt van spoor ' + part.stops[0].platform)
            subtrips.append(part.transport_type + ' naar ' + part.destination + ' van ' + ns_api.simple_time(part.departure_time) + ' (spoor ' + part.stops[0].platform + ')')
            for stop in part.stops:
                if stop.delay:
                    #subtrips.append('Stop ' + stop.name + ' @ ' + ns_api.simple_time(stop.time) + ' ' + stop.delay)
                    subtrips.append(u'🚉 ' + stop.name + ' @ ' + ns_api.simple_time(stop.time) + ' ' + stop.delay)
    message = message + u'\n'.join(subtrips)
    message = message + '\n\n(ns-notifier)'
    return {'header': trip.trip_parts[0].transport_type + ' ' + trip.departure + '-' + trip.destination + ' (' + ns_api.simple_time(trip.requested_time) + ')', 'message': message}


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


def get_changed_trips(mc, nsapi, routes, userkey):
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
        #optimal_trip = ns_api.Trip.get_optimal(current_trips, route['time'])
        if not optimal_trip:
            print "Optimal not found. Alert?"
            # TODO: Get the trip before and the one after route['time']?
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
        print departures

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


#@cli.command('run_disruptions')
@cli.command()
#@click.option('-f', '--feedname', prompt='Feed name')
def run_disruptions():
    """
    Only check for disruptions
    """
    click.secho('Needs implementing', fg='red')


#@cli.command('run_all_notifications')
@cli.command()
def run_all_notifications():
    """
    Check for both disruptions and configured trips
    """
    logger = get_logger()

    ## Open memcache
    mc = MemcacheClient(('127.0.0.1', 11211), serializer=json_serializer,
            deserializer=json_deserializer)

    ## Check whether there's a new version of this notifier
    update_message = check_versions(mc)
    try:
        if update_message and settings.auto_update:
            # Create (touch) file that the run_notifier script checks on for 'update needed'
            open(os.path.dirname(os.path.realpath(__file__)) + '/needs_updating', 'a').close()
            update_message = None
    except AttributeError:
        # 'auto_update' likely not defined in settings.py, default to False
        pass

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
        mc.set('nsapi_run', should_run, MEMCACHE_DISABLING_TTL)


    # HACK, change when moved to Click and parameters
    try:
        if settings.skip_trips == True and settings.skip_disruptions == False:
            should_run = True
    except AttributeError:
        logger.error('Tried overriding should_run, but no skip_* found')

    #print('should run? ' + str(should_run))
    logger.debug('Should run: ' + str(should_run))

    if not should_run:
        sys.exit(0)

    errors = []
    nsapi = ns_api.NSAPI(settings.username, settings.apikey)

    ## Get the list of stations
    stations = get_stations(mc, nsapi)


    ## Get the current disruptions (globally)
    changed_disruptions = []
    get_disruptions = True
    try:
        if settings.skip_disruptions:
            get_disruptions = False
    except AttributeError:
        logger.error('Missing skip_disruptions setting')
    if get_disruptions:
        try:
            disruptions = nsapi.get_disruptions()
            changed_disruptions = get_changed_disruptions(mc, disruptions)
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            #print('[ERROR] connectionerror doing disruptions')
            logger.error('Exception doing disruptions ' + repr(e))
            errors.append(('Exception doing disruptions', e))


    ## Get the information on the list of trips configured by the user
    trips = []
    get_trips = True
    try:
        if settings.skip_trips:
            get_trips = False
    except AttributeError:
        logger.error('Missing skip_trips setting')
    if get_trips:
        try:
            trips = get_changed_trips(mc, nsapi, settings.routes, userkey)
            #print(trips)
        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            #print('[ERROR] connectionerror doing trips')
            logger.error('Exception doing trips ' + repr(e))
            errors.append(('Exception doing trips', e))

    # User is interested in arrival delays
    arrival_delays = True
    try:
        arrival_delays = settings.arrival_delays
    except AttributeError:
        pass

    if settings.notification_type == 'pb':
        p, sendto_device = get_pushbullet_config(logger)
        if not sendto_device:
            sys.exit(1)

        if update_message:
            p.push_note(update_message['header'], update_message['message'], sendto_device)

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
                if not arrival_delays:
                    # User is only interested in departure
                    notification_needed = trip.has_departure_delay(arrival_check=False)
                else:
                    notification_needed = trip.has_delay
                if notification_needed:
                    message = format_trip(trip)
                    #print message
                    logger.debug(message)
                    #p.push_note('title', 'body', sendto_device)
                    p.push_note(message['header'], message['message'], sendto_device)


@cli.command('remove_pushbullet_pushes')
def remove_pushbullet_pushes():
    """
    Clean up older pushes in PushBullet config
    """
    logger = get_logger()

    p, sendto_device = get_pushbullet_config(logger)

    if not sendto_device:
        sys.exit(1)

    # Only get the latest 1000 as history might be huge
    pushes = p.get_pushes(None, 1000)
    logger.debug('Removing pushes, found: ' + str(len(pushes[1])))
    counter = 0
    for push in pushes[1]:
        tag_disruption = 'Traject: '
        tag_trip = '(ns-notification)'
        try:
            #print push['title'][0:len(tag_disruption)]
            #print push['body'][(-1 * len(tag_trip)):]
            if (push['title'][0:len(tag_disruption)] == tag_disruption) or (push['body'][(-1 * len(tag_trip)):] == tag_trip):
                #print ("deleting " + str(push))
                counter = counter + 1
                logger.debug("deleting " + str(push))
                p.delete_push(push['iden'])
        except KeyError:
            # Likely 'body' not found, skipping
            pass
    logger.info('Finished removing pushes, deleted: ' + str(counter))


@cli.command()
def updated():
    """
    Send 'ns-notifcations was updated' message after (automatic) upgrade
    """
    logger = get_logger()
    if settings.notification_type == 'pb':
        p, sendto_device = get_pushbullet_config(logger)
        if not sendto_device:
            sys.exit(1)

        local_version = get_local_version()
        p.push_note('ns-notifier updated', 'Notifier was updated to ' + local_version + ', details might be in your (cron) email', sendto_device)


@cli.command()
def test():
    """
    Send test message
    """
    logger = get_logger()
    if settings.notification_type == 'pb':
        p, sendto_device = get_pushbullet_config(logger)
        if not sendto_device:
            sys.exit(1)

        local_version = get_local_version()
        p.push_note('ns-notifier test', 'Test message from ns-notifier ' + local_version + '. Godspeed!', sendto_device)

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
