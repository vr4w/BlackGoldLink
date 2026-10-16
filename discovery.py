"""Directional collection gaps, independent of wantlists and the similarity score."""
from collection_view import is_vinyl
from matching import album_groups, album_key, known_masters


def collection_discoveries(own_collection, other_collection):
    """Find albums on the other shelf; known masters prevent pressing-only gaps.

    Vinyl comes first, then shared artists, styles and genres. Unknown masters
    stay separate: a matching title alone is not reliable evidence of an album.
    Empty collections cannot provide a basis for personal discoveries.
    """
    if not own_collection or not other_collection:
        return []
    own_groups, _ = album_groups(own_collection, other_collection)
    masters = known_masters(own_collection,other_collection)
    artists = {str(artist['id']) for release in own_collection for artist in release.get('artists', [])}
    styles = {style for release in own_collection for style in release.get('styles', [])}
    genres = {genre for release in own_collection for genre in release.get('genres', [])}
    candidates = []
    for release in other_collection:
        if album_key(release, masters) in own_groups:
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
        key = album_key(release, masters)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
