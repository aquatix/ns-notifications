import logging
from pymemcache.client import Client as MemcacheClient
from flask import Flask
from flask import jsonify
from flask import request
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

@app.route('/')
def nsapi_status():
    logger.info('[%s][status] nsapi_run: %s', request.remote_addr, mc.get('nsapi_run'))
    result = []
    result.append('<h2>NS api status</h2>')
    try:
        should_run = mc.get('nsapi_run')
        result.append("nsapi_run: %s" % mc['nsapi_run'])
    except KeyError:
        result.append("nsapi_run not found")
    result.append('<h2>Disruptions</h2>')
    try:
        prev_disruptions = mc.get('prev_disruptions')
        disruptions = ns_api.list_from_json(prev_disruptions['unplanned'])
        for disruption in disruptions:
            message = format_disruption(disruption)
            logger.debug(message)
            result.append('<h3>' + message['header'] + '</h3>')
            if message['message']:
                result.append('<pre>' + message['message'] + '</pre>')
            else:
                result.append('<pre>Nothing to see here</pre>')
    except TypeError:
        result.append('No disruptions found')
        track = get_current_traceback(skip=1, show_hidden_frames=True,
                                      ignore_system_exceptions=False)
        track.log()
        #abort(500)
    result.append('<h2>Delays</h2>')
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
        result.append('No trips found')
        track = get_current_traceback(skip=1, show_hidden_frames=True,
                                      ignore_system_exceptions=False)
        track.log()
        #abort(500)
    return "\n".join(result)

@app.route('/disable/<location>')
def disable_notifier(location=None):
    location_prefix = '[{0}][location: {1}]'.format(request.remote_addr, location)
    try:
        should_run = mc.get('nsapi_run')
        logger.info('%s nsapi_run was %s, disabling' % (location_prefix, should_run))
    except KeyError:
        logger.info('%s no nsapi_run tuple in memcache, creating with value False' % location_prefix)
    mc.set('nsapi_run', False)
    return 'Disabling notifications'

@app.route('/enable/<location>')
def enable_notifier(location=None):
    location_prefix = '[{0}][location: {1}]'.format(request.remote_addr, location)
    try:
        should_run = mc.get('nsapi_run')
        logger.info('%s nsapi_run was %s, enabling' % (location_prefix, should_run))
    except KeyError:
        logger.info('%s no nsapi_run tuple in memcache, creating with value True' % location_prefix)
    mc.set('nsapi_run', True)
    return 'Enabling notifications'

if __name__ == '__main__':
    # Run on public interface (!) on non-80 port
    app.debug = True
    app.run(host='0.0.0.0', port=8086)
