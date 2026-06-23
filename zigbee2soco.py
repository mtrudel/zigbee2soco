#!/usr/bin/python3

import sys
import os

# debug code in case docker doesn't find the modules
#for path in sys.path:
#    print(path)


try:
    multiplier=int(os.environ.get("VOLUME_MULTIPLIER"))
except:
    multiplier=1

try:
    mqttprefix=os.environ.get("PREFIX")
except:
    mqttprefix="zigbee/stereo"

try:
    mqtthost=os.environ.get("MQTT_HOST")
except:
    mqtthost="localhost"

try:
    mqttport=os.environ.get("MQTT_PORT")
except:
    mqttport=1883


try:
    mqttuser=os.environ.get("MQTT_USER")
except:
    mqttuser=None

try:
    mqttpass=os.environ.get("MQTT_PASS")
except:
    mqttpass=None


import paho.mqtt.client as mqtt
import soco
from soco.plugins.sharelink import ShareLinkPlugin
import traceback
import time, datetime



# class, to keep some "globals" contained

class Z2S:

    def __init__(self):
        self.discover()

    def discover(self):
        self.zones = {x.player_name:x for x in  soco.discover()}

        print("ZONES: "+str(self.zones))
        return self.zones

    def pause(self, speaker):
        self.state = self.zones[speaker].get_current_transport_info()['current_transport_state']
        #priant(state)

        if self.state == "PLAYING":
            print("Pause "+speaker)
            self.zones[speaker].group.coordinator.pause()

        else:
            print("Play "+speaker)
            try:
                self.zones[speaker].group.coordinator.play()
            except:
                print("Unable to play tune on "+speaker+". Try playing something from the Sonos controller first.")
                pass

    def skipforward(self, speaker):
        print("skip forward "+speaker)

        self.zones[speaker].group.coordinator.next()

    def skipback(self, speaker):
        print("skip back "+speaker)

        self.state = self.zones[speaker].get_current_transport_info()['current_transport_state']
        if self.state == "PLAYING":
            a = time.strptime(self.zones[speaker].get_current_track_info()['position'], "%H:%M:%S")
            seconds = datetime.timedelta(hours=a.tm_hour, minutes=a.tm_min, seconds=a.tm_sec).seconds
            if seconds < 5:
                self.zones[speaker].group.coordinator.previous()
            else:
                self.zones[speaker].seek("0:00:00")

    def volup(self, speaker):
        self.state = self.zones[speaker].get_current_transport_info()['current_transport_state']
        if self.state == "PLAYING":
            nv =  min(self.zones[speaker].volume+multiplier,100)
            self.zones[speaker].volume = nv

    def voldown(self, speaker):
        self.state = self.zones[speaker].get_current_transport_info()['current_transport_state']
        if self.state == "PLAYING":
            nv =  max(self.zones[speaker].volume-multiplier,0)
            self.zones[speaker].volume = nv

    def dots(self, speaker):
        self.state = self.zones["Kitchen"].get_current_transport_info()['current_transport_state']
        if self.state == "PLAYING":
            self.zones[speaker].join(self.zones["Kitchen"])

    def dotslong(self, speaker):
        self.zones[speaker].unjoin()

    def twodots(self, speaker):
        # Kind of Blue
        self.zones[speaker].clear_queue()
        sharelink=ShareLinkPlugin(self.zones[speaker])
        sharelink.add_share_link_to_queue("https://open.spotify.com/album/4sb0eMpDn3upAFfyi4q2rw?si=Rll4sJsjRpy223qzmPcLxg")
        self.zones[speaker].play_from_queue(index=0)

    def twodotslong(self, speaker):
        # Poolside radio
        self.zones[speaker].clear_queue()
        sharelink=ShareLinkPlugin(self.zones[speaker])
        sharelink.add_share_link_to_queue("https://open.spotify.com/playlist/37i9dQZF1E4sEET1Q6Yq9z?si=4f9edbe2eb224c9d")
        self.zones[speaker].play_from_queue(index=0)

############## mqtt callbacks ########################

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, z2s, flags, rc):
    print("MQTT Connected with result code "+str(rc))
    if rc==4:
        print ("MQTT connection refused - bad username or password")
    elif rc==5:
        print("MQTT connection refused - not authorized")

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(mqttprefix+"/+/action")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, z2s, msg):

    print(msg.topic+" "+str(msg.payload))

    payload = msg.payload.decode("utf-8")

    try:
        topic = msg.topic
        topic = topic.replace(mqttprefix+"/","")
        topic = topic.replace("/action","")
        #print(topic)
        #print(zones)

    except:
        print(traceback.format_exc())
        print (sys.exc_info()[0])


    # move this to the object
    if not topic in z2s.zones:
        print("No such speaker "+topic+" running discover")
        z2s.discover()

        if not topic in z2s.zones:
            print ("Not found after rescan")
            return

    if payload == "play_pause" or payload == "toggle":
        # both gen1 and gen2 have play_pause
        z2s.pause(topic)
    elif payload == "skip_forward" or payload == "track_next":
        # gen1 - skip_forward, gen2 - track_next
        z2s.skipforward(topic)
    elif payload == "track_previous":
        # gen2 - track_previous
        z2s.skipback(topic)
    elif payload == "rotate_right" or payload == "volume_up" or payload == "volume_up_hold":
        # gen1 - rotate, gen2 - volume...
        z2s.volup(topic)
    elif payload == "rotate_left"  or payload == "volume_down" or payload == "volume_down_hold":
        # gen1 - rotate, gen2 - volume...
        z2s.voldown(topic)
    elif payload == "dots_1_initial_press":
        z2s.dots(topic)
    elif payload == "dots_1_long_press":
        z2s.dotslong(topic)
    elif payload == "dots_2_initial_press":
        z2s.twodots(topic)
    elif payload == "dots_2_long_press":
        z2s.twodotslong(topic)

    # not implemented:
    # dots buttons

    # skip_backward
    # skip_backward can be implemented by calling device_previous() but (in my experience) the wanted behavior is
    # to reset the currently playing tune to 0 at the first click, then, if the skip_backward is pressed again before
    # (a short time) has elapsed, we jump back one tune. This means that we need to get the play time, check it, then do something


################################

z2s = Z2S()

client = mqtt.Client(userdata=z2s)
if mqttuser:
    #print ("Using mqtt user name "+mqttuser+" / password '"+mqttpass+"'")
    client.username_pw_set(mqttuser, mqttpass)
client.on_connect = on_connect
client.on_message = on_message



print ("Connecting to "+mqtthost+":"+str(mqttport))
client.connect(mqtthost, int(mqttport), 60)

print ("zigbee2soco starting processing of events")

# mqtt loop
client.loop_forever()
