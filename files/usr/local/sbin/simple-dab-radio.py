#!/usr/bin/python3

import evdev, signal, select, json, os, sys, traceback, pprint, subprocess, shlex

# --- application-class   ----------------------------------------------------

class Radio(object):

  _STATE_VOLUME = 0
  _STATE_TUNER  = 1
  _RADIO_CLI    = "/usr/local/sbin/radio_cli"
  _CMD_VOLUME   = _RADIO_CLI + " -l {0}"
  _CMD_TUNER    = _RADIO_CLI + " -c {0} -e {1} -f {2} -p"

  # --- constructor   --------------------------------------------------------

  def __init__(self):
    """ constructor """

    self._upd_func = [self.update_volume,self.update_tuner]

    self.done      = False
    self._state    = Radio._STATE_VOLUME
    self._stations = []

  # --- start radio   --------------------------------------------------------

  def start(self):
    """ start (boot) the radio """

    rc = subprocess.call([Radio._RADIO_CLI,"-b","D","-o",str(self._i2s)])
    print("start return-code: %d" % rc)
    
  # --- stop radio   --------------------------------------------------------

  def stop(self):
    """ stop the radio """

    rc = subprocess.call([Radio._RADIO_CLI,"-k"])
    print("stop return-code: %d" % rc)
    self.done = True
    self.save_settings()
    if self._i2s_pid is not None and self._i2s_pid.poll():
      self._i2s_pid.kill()
    
  # --- read settings   ------------------------------------------------------

  def read_settings(self):
    """ read settings from $HOME/.simple-dab-radio.json """

    sname = os.path.expanduser('~/.simple-dab-radio.json')
    if os.path.exists(sname):
      with open(sname,"r") as f:
        settings = json.load(f)
      self._value = [settings['volume'],settings['station']]
    else:
      self._value = [25,0]      # [volume,station]

    # check i2s-attribute
    if "i2s" in settings:
      self._i2s          = settings['i2s']['active']
      self._i2s_vol_cmd  = settings['i2s']['vol_cmd']
      self._i2s_vol_max  = settings['i2s']['vol_max']
      self._i2s_play_cmd = settings['i2s']['play_cmd']
    else:
      self._i2s          = 0
      self._i2s_vol_cmd  = "amixer -q set PCM {0}%"
      self._i2s_vol_max  = 100
      self._i2s_play_cmd = "arecord -D sysdefault:CARD=audiosensepi -c 2 -r 48000 -f S16_LE -q | aplay -q"

    # configure volume-command and playback command
    if self._i2s:
      self._cmd_vol  = self._i2s_vol_cmd
      self._vol_max  = self._i2s_vol_max
      self._i2s_pid  = None
    else:
      self._cmd_vol  = Radio._CMD_VOLUME
      self._vol_max  = 63

  # --- save settings   ------------------------------------------------------

  def save_settings(self):
    """ save settings to $HOME/.simple-dab-radio.json """

    settings = {
      'volume':  self._value[0],
      'station': self._value[1],
      'name': self._stations[self._value[1]]["label"],  # only informational
      'i2s': {
        'active':   self._i2s,
        'vol_cmd':  self._i2s_vol_cmd,
        'vol_max':  self._i2s_vol_max,
        'play_cmd': self._i2s_play_cmd
        }
      }

    sname = os.path.expanduser('~/.simple-dab-radio.json')
    print("saving settings to: %s" % sname)
    with open(sname,"w") as f:
      json.dump(settings,f,indent=2)

  # --- parse station-list   -------------------------------------------------

  def read_stations(self,fname):
    """ read services from station-list. The file should be created
        with: radio_cli -b D -u -k
    """

    with open(fname,"r") as f:
      dabinfo = json.load(f)

    # scan all ensembles
    for ensemble in dabinfo["ensembleList"]:

      # parse ensemble if valid
      if ensemble["DigradStatus"]["valid"]:
        services = ensemble["DigitalServiceList"]["ServiceList"]
        tune_idx = ensemble["DigradStatus"]["tune_index"]
        for service in services:
          station = {}
          station["tune_idx"] = tune_idx
          if not service["AudioOrDataFlag"]:
            station["label"]  = service["Label"]
            station["srvid"]  = service["ServId"]
            station["compid"] = service["ComponentList"][0]["comp_ID"]
            self._stations.append(station)

    pprint.pprint(self._stations)

  # --- change volume   ------------------------------------------------------

  def update_volume(self):
    """ update volume """

    # clamp volume to 0-vol_max
    vol = self._value[Radio._STATE_VOLUME]
    vol = min(vol,self._vol_max)
    vol = max(vol,0)
    self._value[Radio._STATE_VOLUME] = vol
    
    print("updating volume to %d" % vol)
    args = shlex.split(self._cmd_vol.format(vol))
    rc = subprocess.call(args)
    print("update_volume return-code: %d" % rc)

  # --- change station   -----------------------------------------------------

  def update_tuner(self):
    """ update station """

    if self._i2s and  (
      self._i2s_pid is None or self._i2s_pid.poll() is not None):
      # and start playing
      args = shlex.split(self._i2s_play_cmd)
      print("starting to play with %r",(args,))
      self._i2s_pid = subprocess.Popen(args,shell=True)

    # wrap around
    idx = self._value[Radio._STATE_TUNER]
    idx = idx % len(self._stations)
    self._value[Radio._STATE_TUNER] = idx

    station = self._stations[idx]
    print("tuning to %s" % station["label"])
    args = shlex.split(
      Radio._CMD_TUNER.format(station["compid"],
                              station["srvid"],
                              station["tune_idx"]))
    rc = subprocess.call(args)
    print("update_tuner return-code: %d" % rc)

  # --- process events from rotary-encoder   ---------------------------------

  def process_events(self):
    """ scan all input-devices and process events
        note: on a Raspberry Pi with a rotary-encoder there are two
        input-devices, one for rotation and one for push
    """
    devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
    devices = {dev.fd: dev for dev in devices}
  
    while not self.done:
      fds, _1, _2 = select.select(devices, [], [])
      for fd in fds:
        for event in devices[fd].read():
          event = evdev.util.categorize(event)
          if isinstance(event, evdev.events.RelEvent):
            # rotation: change value and call update-function
            self._value[self._state] += event.event.value
            self._upd_func[self._state]()
          elif isinstance(event, evdev.events.KeyEvent):
            if event.keycode == "KEY_ENTER" and event.keystate == event.key_up:
              # push: toggle state
              self._state = 1 - self._state
              print("changing state to: %d" % self._state)
            elif event.keycode == "KEY_LEFT" and event.keystate == event.key_up:
              # simulate rotate left
              self._value[self._state] -= 1
              self._upd_func[self._state]()
            elif event.keycode == "KEY_RIGHT" and event.keystate == event.key_up:
              # simulate rotate right
              self._value[self._state] += 1
              self._upd_func[self._state]()

# --------------------------------------------------------------------------

def signal_handler(_signo, _stack_frame):
  """ Signal-handler to cleanup threads """

  global radio
  radio.stop()
  sys.exit(0)

# --------------------------------------------------------------------------

if __name__ == "__main__":

  if len(sys.argv) < 2:
    station_file = os.path.expanduser("~/stations.json")
  else:
    station_file = sys.argv[1]

  # setup signal handlers
  signal.signal(signal.SIGTERM, signal_handler)
  signal.signal(signal.SIGINT, signal_handler)

  try:
    radio = Radio()
    radio.read_stations(station_file)
    radio.read_settings()
    radio.start()
    radio.update_volume()
    radio.update_tuner()
    radio.process_events()
  except:
    if not radio.done:
      print(traceback.format_exc())
    radio.stop()
