# Example configuration. Copy to settings.py and modify to your needs
username = 'your@email.address'
apikey = 'someVeryLongKeyThatNSWillProvideYou'
# https://www.ns.nl/ews-aanvraagformulier/

# Notifications types:
# pb: PushBullet
# pt: Pebble Time timeline (not yet implemented)
notification_type = 'pb' # Use PushBullet

# Pushbullet API key. See their website
pushbullet_key = "YOURKEYHERE"
# Device to push to. Run ns_notifications with an invalid device_id for the list of which to choose
pushbullet_device_id = "DEVICEKEYHERE"

# Set to True when you want the disruptions (storingen) to go to a channel
pushbullet_use_channel = False
pushbullet_channel_tag = 'yourPushBulletChannelTag'

# You might want to set this to True if you're already subscribed to someone else's (official) PushBullet Channel or just
# are not interested in the disruptions
# See for example https://www.pushbullet.com/channel?tag=treinverstoringen
skip_disruptions = False

# Uncomment the next two lines if you only want ERROR-level logging (or change to logging.WARNING for example)
#import logging
#debug_level = logging.ERROR

# 'minimum': amount of time a delay needs to be at minimum for which a notification is fired
# 'strict': if True and no connection is found for that exact time stamp, 'train cancelled' is fired
routes = [
        {'departure': 'Heemskerk', 'destination': 'Hoofddorp', 'time': '7:44', 'keyword': 'Beverwijk', 'minimum': 5 },
         {'departure': 'Amsterdam Sloterdijk', 'destination': 'Hoofddorp', 'time': '8:19', 'keyword': None },
         {'departure': 'Schiphol', 'destination': 'Hoofddorp', 'time': '9:15', 'keyword': None },
         {'departure': 'Hoofddorp', 'destination': 'Heemskerk', 'time': '17:05', 'keyword': 'Hoorn', 'minimum': 3 },
         {'departure': 'Amsterdam Sloterdijk', 'destination': 'Heemskerk', 'time': '17:39', 'keyword': 'Haarlem' },
         #{'departure': 'Amsterdam Sloterdijk', 'destination': 'Nijmegen', 'time': '21:40', 'keyword': None }, # test
         #{'departure': 'Amsterdam Sloterdijk', 'destination': 'Schiphol', 'time': '22:19', 'keyword': None }, # test
         #{'departure': 'Amsterdam Sloterdijk', 'destination': 'Amersfoort', 'time': '22:09', 'keyword': None }, # test
         ]
