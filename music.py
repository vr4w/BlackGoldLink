"""Release-linked YouTube videos, never scraped search or audio extraction."""
import re
from urllib.parse import urlsplit,parse_qs

def youtube_id(url):
    try:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443):return None
        host=(parsed.hostname or '').lower()
        if host=='youtu.be': candidate=parsed.path.strip('/')
        elif host in ('youtube.com','www.youtube.com','m.youtube.com'):
            if parsed.path=='/watch':candidate=parse_qs(parsed.query).get('v',[''])[0]
            elif parsed.path.startswith('/embed/'):candidate=parsed.path.split('/')[2]
            else:return None
        else:return None
        return candidate if re.fullmatch(r'[A-Za-z0-9_-]{11}',candidate) else None
    except (ValueError,TypeError):return None
