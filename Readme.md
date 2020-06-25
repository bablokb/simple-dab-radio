Simple DAB+ Radio
=================

This is a simple radio application using the DAB+-receiver board from
uGreen.

Hardware Requirements
---------------------

You need the following components:

  - a Raspberry Pi with 2x20 pins (a Pi-Zero will be fine)
  - the DAB-Board from uGreen either with long pins or
  - a pin-multiplexer board
  - a rotary-encoder
  - jumper-wires


Hardware Setup
--------------

Attach the DAB-Board to the Pi. Connect the rotary-encoder as follows

  - CLK: GPIO17
  - DATA: GPIO27
  - SW: GPIO22
  - Vcc: 3V3
  - GND: GND


Software Setup
--------------

Install (copy) the program `radio_cli` from the uGreen-site to
`/usr/local/sbin/radio_cli`. Follow the user's guide from uGreen to
configure your system for use with the DAB-Board. Test the board and
verify that it works.

Run

    radio_cli -b D -u -k

This will do a full scan of all radio-frequencies and create a file
`ensemblescan_xxx.json`. Copy this file to `/root/stations.json`.

Download and install the software of this project:

    git clone https://github.com/bablokb/simple-dab-radio.git
    cd simple-dab-radio
    sudo tools/install

This will

  - copy the application program `/usr/local/sbin/simple-dab-radio.py`
  - install a systemd-service for the program
  - activate the rotary-encoder in the file `/boot/config.txt`

You need a reboot after installation. The systemd-service will automatically
start `simple-dab-radio.py` during boot and stop the board cleanly during
shutdown.


Usage
-----

Pushing the rotary-encoder will switch between tuning and volume-control.
Note that the DAB-Board needs some time to tune to the selected radio-station,
so don't turn the knob too fast. Changing the volume is faster.


Advanced Configuration
----------------------

The application also supports I2S-setups. If you wan't to use I2S, then follow
uGreen's user's guide first to setup I2S for the board.

To activate I2S for this application, you have to edit the configuration file
`/root/.simple-dab-radio.json` and set `active: 1`:

    {
      "volume":  62,
      "station": 12,
      "name": "BR Klassik    ",
      "i2s": {
        "active": 1,
        "vol_cmd": "amixer -q set PCM {0}%",
        "vol_max": 100, 
        "play_cmd": "arecord -D sysdefault:CARD=audiosensepi -c 2 -r 48000 -f S16_LE -q | aplay -q"
        }
      }

Depending on your hardware, you might also have to change the mixer command
(`vol_cmd`) and the aplay options within the `play_cmd`.


Future Development
------------------

Some ideas for improvements:

  - use TTS to announce the selected station (works only with I2S)
  - use a small I2C-OLED-display (e.g. for station-logo)
  - only tune if the knob is at rest

