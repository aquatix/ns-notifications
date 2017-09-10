import logging
import os
from pymemcache.client import Client as MemcacheClient
from flask import Flask, jsonify, request, render_template
from werkzeug.debug import get_current_traceback
from ns_notifications import *

app = Flask(__name__)

# create logger
logger = logging.getLogger('nsapi_server')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('nsapi_server.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

# Connect to the Memcache daemon
mc = MemcacheClient(('127.0.0.1', 11211), serializer=json_serializer,
        deserializer=json_deserializer)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', error=e), 404


@app.route('/')
def index():
    return ''


@app.route('/<userkey>/')
def nsapi_status(userkey):
    logger.info('[%s][status] nsapi_run: %s', request.remote_addr, mc.get('nsapi_run'))
    result = {}
    #result.append('<html><head><title>NS Storingen</title></head><body>')
    #result.append('<h2>NS api status</h2>')
    try:
        should_run = mc.get('nsapi_run')
        result['nsapi_run'] = "%s" % mc['nsapi_run']
    except KeyError:
        result['nsapi_run'] = "nsapi_run not found"
    result['disruptions'] = []
    try:
        prev_disruptions = mc.get('prev_disruptions')
        disruptions = ns_api.list_from_json(prev_disruptions['unplanned'])
        for disruption in disruptions:
            message = format_disruption(disruption)
            logger.debug(message)
            result.append(u'<h3>' + message['header'] + '</h3>')
            if message['message']:
                if message['timestamp']:
                    result.append('<p>' + message['timestamp'] + '</p>')
                result.append('<pre>' + message['message'] + '</pre>')
            else:
                result.append('<pre>Nothing to see here</pre>')
    except TypeError:
        #result.append('No disruptions found')
        track = get_current_traceback(skip=1, show_hidden_frames=True,
                                      ignore_system_exceptions=False)
        track.log()
        #abort(500)
    #result.append('<h2>Delays</h2>')
    result['delays'] = []
    try:
        prev_delays = mc.get('1_trips')
        delays = ns_api.list_from_json(prev_delays)
        for delay in delays:
            message = format_trip(delay)
            if not message['message']:
                message['message'] = 'Geen bijzonderheden'
            result.append('<h3>' + message['header'] + '</h3>')
            result.append('<pre>' + message['message'] + '</pre>')
    except TypeError:
        #result.append('No trips found')
        track = get_current_traceback(skip=1, show_hidden_frames=True,
                                      ignore_system_exceptions=False)
        track.log()
        #abort(500)
    #result.append('</body></html>')
    #return u'\n'.join(result)
    return render_template('status.html', content=result)


@app.route('/<userkey>/listroutes')
def list_routes(userkey):
    """List all routes (trajectories) in the user's settings, including some info on them"""
    data = {}
    return render_template('routes.html', data=data)


@app.route('/<userkey>/nearby/<lat>/<lon>/json')
def get_nearby_stations(userkey, lat, lon):
    """Look up nearby stations based on lat lon coordinates"""
    return jsonify({'message': 'Not implemented yet'})


@app.route('/<userkey>/disable/<location>')
def disable_notifier(userkey, location=None):
    location_prefix = '[{0}][location: {1}]'.format(request.remote_addr, location)
    try:
        should_run = mc.get('nsapi_run')
        logger.info('%s nsapi_run was %s, disabling' % (location_prefix, should_run))
    except KeyError:
        logger.info('%s no nsapi_run tuple in memcache, creating with value False' % location_prefix)
    mc.set('nsapi_run', False, MEMCACHE_DISABLING_TTL)
    return 'Disabling notifications'


@app.route('/<userkey>/enable/<location>')
def enable_notifier(userkey, location=None):
    location_prefix = '[{0}][location: {1}]'.format(request.remote_addr, location)
    try:
        should_run = mc.get('nsapi_run')
        logger.info('%s nsapi_run was %s, enabling' % (location_prefix, should_run))
    except KeyError:
        logger.info('%s no nsapi_run tuple in memcache, creating with value True' % location_prefix)
    mc.set('nsapi_run', True, MEMCACHE_DISABLING_TTL)
    return 'Enabling notifications'


if __name__ == '__main__':
    # Run on public interface (!) on non-80 port
    app.run(host='0.0.0.0', port=8086, debug=True)
