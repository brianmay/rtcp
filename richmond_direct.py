#!/usr/bin/python2

import argparse
import configparser
from hashlib import sha1
import hmac
import datetime
import requests
import pytz
from tzlocal import get_localzone
from urllib import urlencode, quote


class Ptv(object):
    def __init__(self, dev_id, key):
        self.dev_id = dev_id
        self.key = key

    def getUrl(self, request):
        dev_id = self.dev_id
        key = str(self.key)
        request = request + ('&' if ('?' in request) else '?')
        raw = request+'devid={0}'.format(dev_id)
        hashed = hmac.new(key, raw, sha1)
        signature = hashed.hexdigest()
        return ('https://timetableapi.ptv.vic.gov.au'
                + raw + '&signature={1}'.format(dev_id, signature))

    def get_pattern(self, run_id, route_type, **kwargs):
        url_path = quote(
            '/v3/pattern/run/'+str(run_id)+'/route_type/'+str(route_type))

        args = dict(kwargs)
        args['date_utc'] = kwargs['date_utc'].isoformat() + "Z"

        query_string = urlencode(args)

        url = self.getUrl(url_path + '?' + query_string)

        r = requests.get(url)
        j = r.json()
        return j

    def get_departures(self, route_type, stop_id, route_id=None, **kwargs):
        url_components = [
            '/v3/departures',
            '/route_type/'+str(route_type),
            '/stop/'+str(stop_id)
        ]
        if route_id is not None:
            url_components.append("/route/"+str(route_id))

        url_path = quote("".join(url_components))

        args = dict(kwargs)
        args['date_utc'] = kwargs['date_utc'].isoformat() + "Z"

        query_string = urlencode(args)

        url = self.getUrl(url_path + '?' + query_string)

        r = requests.get(url)
        j = r.json()
        return j


def time_hhmm(string):
    split = string.split(":")
    if len(split) != 2:
        raise argparse.ArgumentTypeError("time '%r' is not valid" % string)

    try:
        hh = int(split[0])
        mm = int(split[1])
    except ValueError:
        raise argparse.ArgumentTypeError("time '%r' is not valid" % string)

    try:
        time = datetime.time(hour=hh, minute=mm)
    except ValueError:
        raise argparse.ArgumentTypeError("time '%r' is not valid" % string)

    return time


def main():
    parser = argparse.ArgumentParser(
        description='Guesstimates connections at Richmond'
        ' station for direct service.')
    parser.add_argument(
        'departure_time',
        type=time_hhmm,
        help='Departure time for first train.')
    parser.add_argument(
        'departure_station',
        type=int,
        help='Departure station for first train.')
    args = parser.parse_args()

    # configuration
    config = configparser.ConfigParser()
    config.read('config.ini')

    ptv_section = config['ptv']
    dev_id = ptv_section.getint('dev_id')
    key = ptv_section['key']

    ptv = Ptv(dev_id, key)

    today = datetime.date.today()

    # our timezone
    to_zone = get_localzone()

    # service we are currently on
    departed_time = args.departure_time
    departed_dt = datetime.datetime.combine(today, departed_time)
    print(departed_dt)
    departed_stop_id = args.departure_station
    departed_route_type = 0

    # where we expect to change
    change_stop_id = 1162

    # where we expect to finish
    destination_stop_id = 1071

    # convert time to UTC
    from_zone = get_localzone()
    departed_dt_local = from_zone.localize(departed_dt, is_dst=None)
    departed_dt_utc = departed_dt_local.astimezone(pytz.utc)

    # Get the run_id
    j = ptv.get_departures(
            route_type=departed_route_type, stop_id=departed_stop_id,
            direction_id=0, max_results=1, date_utc=departed_dt_utc)
    run_id = j['departures'][0]['run_id']
    print("run_id = %s" % run_id)

    departure = j['departures'][0]
    if departure['estimated_departure_utc'] is not None:
        departure_dt_string = departure['estimated_departure_utc']
        departure_is_realtime = True
    else:
        departure_dt_string = departure['scheduled_departure_utc']
        departure_is_realtime = False

    departure_dt_utc = datetime.datetime.strptime(
        departure_dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
    departure_dt_local = departure_dt_utc.astimezone(to_zone)

    print("departure time (UTC) = %s (%s)"
          % (departure_dt_utc, departure_is_realtime))
    print("departure time (local) = %s (%s)"
          % (departure_dt_local, departure_is_realtime))

    # Get the stopping patterns
    j = ptv.get_pattern(
        run_id=run_id,
        route_type=departed_route_type,
        date_utc=departed_dt_utc,
    )

    # Get the change stop departure details
    departures = filter(
        lambda d: d['stop_id'] == departed_stop_id, j['departures'])
    assert len(departures) == 1

    # Get the change stop departure details
    departures = filter(
        lambda d: d['stop_id'] == change_stop_id, j['departures'])
    assert len(departures) == 1

    # Get the expected arrival time at change_stop
    departure = departures[0]
    if departure['estimated_departure_utc'] is not None:
        change_dt_string = departure['estimated_departure_utc']
        change_is_realtime = True
    else:
        change_dt_string = departure['scheduled_departure_utc']
        change_is_realtime = False

    change_dt_utc = datetime.datetime.strptime(
        change_dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
    change_dt_local = change_dt_utc.astimezone(to_zone)

    print("change time (UTC) = %s (%s)"
          % (change_dt_utc, change_is_realtime))
    print("change time (local) = %s (%s)"
          % (change_dt_local, change_is_realtime))

    # Look up departures after change time
    j = ptv.get_departures(
            route_type=0, stop_id=change_stop_id,
            direction_id=0, expand="run",
            max_results=10, date_utc=change_dt_utc)

    results = []

    for departure in j['departures']:
        run = j['runs'][str(departure['run_id'])]

        # get the departure time from change stop
        if departure['estimated_departure_utc'] is not None:
            departure_dt_string = departure['estimated_departure_utc']
            departure_is_realtime = True
        else:
            departure_dt_string = departure['scheduled_departure_utc']
            departure_is_realtime = False

        departure_dt_utc = datetime.datetime.strptime(
            departure_dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        departure_dt_local = departure_dt_utc.astimezone(to_zone)

        # skip if too early
        if departure_dt_utc < change_dt_utc:
            continue

        # get pattern for this run
        pattern = ptv.get_pattern(
            departure['run_id'], route_type=0, date_utc=departure_dt_utc)

        # get the destination for this run
        if 'departures' not in pattern:
            continue

        destinations = filter(
            lambda d: d['stop_id'] == destination_stop_id,
            pattern['departures'],
        )
        assert len(destinations) == 1
        # destination = destinations[0]

        # is this a direct service?
        parliament = filter(
            lambda d: d['stop_id'] == 1155, pattern['departures'])
        direct = len(parliament) == 0

        # get the time we arrive at the destination
        # if destination['estimated_departure_utc'] is not None:
        #     arrival_dt_string = destination['estimated_departure_utc']
        #     arrival_is_realtime = True
        # else:
        #     arrival_dt_string = destination['scheduled_departure_utc']
        #     arrival_is_realtime = False
        # arrival_dt_utc = datetime.datetime.strptime(
        #     arrival_dt_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        # arrival_dt_local = arrival_dt_utc.astimezone(to_zone)

        if direct:
            arrival_dt_utc = departure_dt_utc + datetime.timedelta(minutes=4)
        else:
            arrival_dt_utc = departure_dt_utc + datetime.timedelta(minutes=14)
        arrival_dt_local = arrival_dt_utc.astimezone(to_zone)
        arrival_is_realtime = departure_is_realtime

        results.append({
            'departure_dt_local': departure_dt_local,
            'departure_dt_utc': departure_dt_utc,
            'departure_is_realtime': departure_is_realtime,
            'arrival_dt_local': arrival_dt_local,
            'arrival_dt_utc': arrival_dt_utc,
            'arrival_is_realtime': arrival_is_realtime,
            'departure': departure,
            'run': run,
            'pattern': pattern,
            'direct': direct,
        })

    print("")

    sorted_results = sorted(results, key=lambda r: r['arrival_dt_local'])
    for result in sorted_results:
        print("%s (%s) %s (%s) platform %s (%s) direct %s" % (
            result['departure_dt_local'],
            result['departure_is_realtime'],
            result['arrival_dt_local'],
            result['arrival_is_realtime'],
            result['departure']['platform_number'],
            result['departure']['at_platform'],
            result['direct']
        ))

    utcnow = datetime.datetime.utcnow()
    utcnow = change_dt_utc
    for result in sorted_results:
        print("%s (%s) %s (%s) platform %s (%s) direct %s" % (
            result['departure_dt_utc'].replace(tzinfo=None)
            - utcnow.replace(tzinfo=None),
            result['departure_is_realtime'],
            result['arrival_dt_utc'].replace(tzinfo=None)
            - utcnow.replace(tzinfo=None),
            result['arrival_is_realtime'],
            result['departure']['platform_number'],
            result['departure']['at_platform'],
            result['direct']
        ))


if __name__ == "__main__":
    main()
