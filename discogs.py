"""Discogs OAuth 1.0a and read-only paginated imports using stdlib HTTP."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from covers import trusted_image_url
from urllib.parse import quote, urlencode, urlsplit, parse_qsl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API = 'https://api.discogs.com'

class DiscogsError(Exception):
    pass


def esc(value):
    return quote(str(value), safe='~')


def oauth_header(method, url, key, secret, token='', token_secret='', extra=None, nonce=None, timestamp=None):
    oauth = {'oauth_consumer_key': key, 'oauth_nonce': nonce or secrets.token_hex(16),
             'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(timestamp or int(time.time())), 'oauth_version':'1.0'}
    if token:
        oauth['oauth_token'] = token
    oauth.update(extra or {})
    parts = urlsplit(url)
    params = list(oauth.items()) + parse_qsl(parts.query, keep_blank_values=True)
    normalized = '&'.join(f'{k}={v}' for k,v in sorted((esc(k),esc(v)) for k,v in params))
    base_url = f'{parts.scheme}://{parts.netloc}{parts.path}'
    base = '&'.join(map(esc, [method.upper(),base_url,normalized]))
    signing_key = f'{esc(secret)}&{esc(token_secret)}'
    oauth['oauth_signature'] = base64.b64encode(hmac.new(signing_key.encode(),base.encode(),hashlib.sha1).digest()).decode()
    return 'OAuth ' + ', '.join(f'{esc(k)}="{esc(v)}"' for k,v in sorted(oauth.items()))


class Discogs:
    def __init__(self, key, secret, agent, throttle=lambda:None, token='', token_secret='', cooldown=lambda seconds:None):
        self.key, self.secret, self.agent = key, secret, agent
        self.token, self.token_secret, self.throttle = token, token_secret, throttle
        self.cooldown = cooldown

    def request(self, path, params=None, extra=None, form=False, method='GET'):
        if method != 'GET' and not (method == 'POST' and path in ('/oauth/request_token','/oauth/access_token')):
            raise DiscogsError('Schreibzugriffe auf Discogs sind deaktiviert.')
        url = API + path + ('?' + urlencode(params) if params else '')
        for attempt in range(4):
            self.throttle()
            headers = {'User-Agent':self.agent, 'Authorization':oauth_header(method,url,self.key,self.secret,self.token,self.token_secret,extra), 'Accept':'application/json'}
            try:
                with urlopen(Request(url, headers=headers,method=method,data=b'' if method=='POST' else None), timeout=25) as response:
                    raw = response.read(8_000_000)
                    result = dict(parse_qsl(raw.decode())) if form else json.loads(raw)
                    remaining = response.headers.get('X-Discogs-Ratelimit-Remaining')
                    if remaining == '0':
                        self.cooldown(60)
                    return result
            except HTTPError as error:
                if error.code == 429 or error.code >= 500:
                    if attempt < 3:
                        try: delay = float(error.headers.get('Retry-After','60'))
                        except ValueError: delay = 60
                        delay = min(max(delay, 2 ** attempt), 120)
                        self.cooldown(delay)
                        time.sleep(delay)
                        continue
                raise DiscogsError(f'Discogs antwortet mit HTTP {error.code}. Bitte später erneut verbinden oder synchronisieren.') from None
            except (URLError, TimeoutError, ValueError):
                raise DiscogsError('Discogs ist derzeit nicht erreichbar oder liefert ungültige Daten.') from None
        raise DiscogsError('Discogs ist vorübergehend ausgelastet.')

    def request_token(self, callback):
        return self.request('/oauth/request_token',extra={'oauth_callback':callback},form=True,method='POST')

    def access_token(self, verifier):
        return self.request('/oauth/access_token',extra={'oauth_verifier':verifier},form=True,method='POST')

    def identity(self):
        return self.request('/oauth/identity')

    def import_list(self, username, kind, progress=lambda page,total:None):
        path = f'/users/{quote(username,safe="")}/' + ('collection/folders/0/releases' if kind == 'collection' else 'wants')
        items, page = {}, 1
        while True:
            result = self.request(path,{'page':page,'per_page':100})
            pagination = result['pagination']
            progress(page,pagination['pages'])
            for entry in result['releases' if kind == 'collection' else 'wants']:
                info = entry['basic_information']
                release_id = int(info['id'])
                items[release_id] = {'id':release_id, 'title':info.get('title',''), 'year':info.get('year',0),
                    'artists':[{'id':int(a['id']),'name':a['name']} for a in info.get('artists',[])],
                    'genres':info.get('genres',[]), 'styles':info.get('styles',[]),
                    'formats':[{'name':str(f.get('name','')),'qty':str(f.get('qty','1')),'descriptions':[str(x) for x in f.get('descriptions',[])]} for f in info.get('formats',[])],
                    'master_id':int(info.get('master_id') or 0),
                    'labels':[{'id':int(label['id']),'name':label['name']} for label in info.get('labels',[])],
                    'thumb_url':info.get('thumb','') if trusted_image_url(info.get('thumb','')) else ''}
            if page >= pagination['pages']:
                return list(items.values())
            if page > 1000:
                raise DiscogsError('Import zu groß für die erste Version.')
            page += 1
