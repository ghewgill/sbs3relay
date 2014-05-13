This script relays data between a Kinetic SBS-3 and FlightAware's ADSB service.

See https://flightaware.com/adsb/sbs3/ for background information.

## Requirements

This script requires:

* a [Kinetic SBS-3](http://kinetic.co.uk)
* Python 3
* a [FlightAware account](https://flightaware.com/adsb/)

## Usage

To use this script, set up your SBS-3 using the option "SBS-3 as Server" (the default port 10001 is fine). Copy the `sbsrelay.config.example` file to `sbsrelay.config` and edit it. Change the IP address in this file to the IP addres of your SBS-3.

Run this script as

    python3 sbsrelay.py

A status display will be shown on the screen listing visible aircraft.

## Bugs

* The altitude, latitude, and longitude are not fully decoded
