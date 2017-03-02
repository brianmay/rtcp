""" Interface to PTV real time information. """
from hashlib import sha1
import hmac
import requests
from urllib import urlencode, quote


class Connection(object):
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
        r.raise_for_status()
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
        r.raise_for_status()
        j = r.json()
        return j

    def search(self, search_term, **kwargs):
        url_components = [
            '/v3/search/',
            str(search_term),
        ]

        url_path = quote("".join(url_components))

        args = dict(kwargs)
        query_string = urlencode(args)

        url = self.getUrl(url_path + '?' + query_string)

        r = requests.get(url)
        r.raise_for_status()
        j = r.json()
        return j
