"""Presentation filters; never alter imported data or matching inputs."""
import hashlib

def media_names(release):
    return {str(item.get('name','')).casefold() for item in release.get('formats',[]) if isinstance(item,dict)}

def is_vinyl(release):
    return 'vinyl' in media_names(release)

def visible_releases(items,medium='vinyl'):
    seen=set();result=[]
    for release in items:
        if release['id'] in seen: continue
        seen.add(release['id'])
        names=media_names(release)
        if medium=='vinyl' and not is_vinyl(release):continue
        if medium=='other' and (not names or is_vinyl(release)):continue
        if medium=='unknown' and names:continue
        result.append(release)
    return result

def record_spines(items):
    seen=set();result=[]
    for release in visible_releases(items):
        key=('master',release['master_id']) if release.get('master_id') else ('release',release['id'])
        if key in seen:continue
        seen.add(key)
        seed=int(hashlib.sha256(str(release['id']).encode()).hexdigest()[:8],16)
        result.append(dict(release=release,tone=seed%12,width=seed%4,lean=seed%5,wear=seed%3))
    return result
