"""Directional collection gaps, independent of wantlists and the similarity score."""
from collection_view import is_vinyl


def collection_discoveries(own_collection, other_collection):
    """Find albums on the other shelf; known masters prevent pressing-only gaps.

    Vinyl comes first, then shared artists, styles and genres. Unknown masters
    stay separate: a matching title alone is not reliable evidence of an album.
    Empty collections cannot provide a basis for personal discoveries.
    """
    if not own_collection or not other_collection:
        return []
    own_ids = {release['id'] for release in own_collection}
    own_masters = {release['master_id'] for release in own_collection if release.get('master_id')}
    artists = {str(artist['id']) for release in own_collection for artist in release.get('artists', [])}
    styles = {style for release in own_collection for style in release.get('styles', [])}
    genres = {genre for release in own_collection for genre in release.get('genres', [])}
    candidates = []
    for release in other_collection:
        if release['id'] in own_ids or (release.get('master_id') and release['master_id'] in own_masters):
            continue
        candidates.append(dict(release=release, vinyl=is_vinyl(release),
            shared_artists=[artist['name'] for artist in release.get('artists', []) if str(artist['id']) in artists],
            shared_styles=sorted(styles.intersection(release.get('styles', []))),
            shared_genres=sorted(genres.intersection(release.get('genres', [])))))
    candidates.sort(key=lambda item: (not item['vinyl'], not bool(item['shared_artists']),
        -len(item['shared_artists']), -len(item['shared_styles']), -len(item['shared_genres']),
        item['release'].get('title', '').casefold(), item['release']['id']))
    result, seen = [], set()
    for item in candidates:
        release = item['release']
        key = ('master', release['master_id']) if release.get('master_id') else ('release', release['id'])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
