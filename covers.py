"""Read-only, bounded thumbnail fetch. No OAuth tokens sent to image hosts."""
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
ALLOWED_IMAGE_HOSTS={'i.discogs.com','img.discogs.com','st.discogs.com'}
MAX_IMAGE_BYTES=2_000_000

def trusted_image_url(url):
    try:
        p=urlsplit(url)
        return p.scheme=='https' and p.hostname in ALLOWED_IMAGE_HOSTS and p.port in (None,443) and not p.username and not p.password
    except (TypeError,ValueError): return False

class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not trusted_image_url(newurl): raise ValueError('Image redirect rejected')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_cover(url,agent):
    if not trusted_image_url(url): raise ValueError('Image host rejected')
    with build_opener(SafeRedirect()).open(Request(url,headers={'User-Agent':agent}),timeout=8) as response:
        kind=response.headers.get_content_type();data=response.read(MAX_IMAGE_BYTES+1)
        if len(data)>MAX_IMAGE_BYTES: raise ValueError('Image too large')
        valid=((kind=='image/jpeg' and data.startswith(b'\xff\xd8\xff')) or (kind=='image/png' and data.startswith(b'\x89PNG\r\n\x1a\n')) or (kind=='image/gif' and data.startswith((b'GIF87a',b'GIF89a'))) or (kind=='image/webp' and data[:4]==b'RIFF' and data[8:12]==b'WEBP'))
        if not valid: raise ValueError('Invalid image response')
        return data,kind
