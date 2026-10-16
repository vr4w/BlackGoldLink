"""Symmetric, explainable collection comparison. No network or persistence."""
from collections import Counter
from math import sqrt, log


def cosine(a, b, weights=None):
    weights = weights or {}
    if not a or not b:
        return 0.0
    common = sum(weights.get(x, 1) for x in a & b)
    return round(100 * common / sqrt(sum(weights.get(x, 1) for x in a) * sum(weights.get(x, 1) for x in b)), 1)


def rarity_weights(collections):
    """Optional later weighting within consenting platform members, not global rarity."""
    counts = Counter(x for collection in collections for x in set(collection))
    return {x: 1 + log((1 + len(collections)) / (1 + n)) for x, n in counts.items()}


def facets(items, field):
    return {str(v['id']) if isinstance(v, dict) else v for item in items for v in item.get(field, [])}


SCORE_VERSION = 'album-cosine-v2'
DEFAULT_SCORE_FACTORS = {'albums': 1.0}


def album_key(release, masters):
    master = masters[release['id']] if release['id'] in masters else release.get('master_id')
    return ('master', master) if master else ('release', release['id'])


def known_masters(*collections):
    values = {}
    for items in collections:
        for item in items:
            if item.get('master_id'):
                values.setdefault(item['id'],set()).add(item['master_id'])
    # Conflicting metadata must not make a directional or guessed album match.
    return {uid:next(iter(ids)) if len(ids)==1 else None for uid,ids in values.items()}


def album_groups(a, b):
    # Exact releases remain identical if only one import supplied their master.
    masters = known_masters(a,b)
    groups = []
    for items in (a, b):
        grouped = {}
        for item in items:
            grouped.setdefault(album_key(item, masters), {})[item['id']] = item
        groups.append({key: sorted(values.values(), key=lambda r:r['id']) for key,values in grouped.items()})
    return groups[0], groups[1]


def combine_components(components, factors=None):
    """Future explicit policies can include available factors without changing compare callers."""
    factors = DEFAULT_SCORE_FACTORS if factors is None else factors
    if not factors or any(value < 0 for value in factors.values()):
        raise ValueError('Score weights must be non-negative and nonempty.')
    if any(key not in components or components[key] is None for key,value in factors.items() if value):
        raise ValueError('Requested score component is unavailable.')
    total = sum(factors.values())
    if total <= 0:
        raise ValueError('At least one positive factor is required.')
    return round(sum(components[key] * weight for key,weight in factors.items() if weight) / total, 1)


def master_ids(items):
    if not items or any(not x.get('master_id') for x in items):
        return None
    return {x['master_id'] for x in items}


def compare(a, b, weights=None):
    ac, bc = {x['id'] for x in a['collection']}, {x['id'] for x in b['collection']}
    aw, bw = {x['id'] for x in a['wantlist']}, {x['id'] for x in b['wantlist']}
    aa, ba = facets(a['collection'], 'artists'), facets(b['collection'], 'artists')
    ag, bg = facets(a['collection'], 'genres'), facets(b['collection'], 'genres')
    am, bm = master_ids(a['collection']), master_ids(b['collection'])
    albums_a, albums_b = album_groups(a['collection'], b['collection'])
    keys_a, keys_b = set(albums_a), set(albums_b)
    album_weights = None if not weights else {key: weights.get(key,max(weights.get(item['id'],1) for item in albums_a.get(key,[])+albums_b.get(key,[]))) for key in keys_a|keys_b}
    shared = keys_a & keys_b
    common_albums = [dict(key=key,a=albums_a[key],b=albums_b[key],different_versions={r['id'] for r in albums_a[key]}!={r['id'] for r in albums_b[key]}) for key in sorted(shared)]
    components = dict(albums=cosine(keys_a,keys_b,album_weights), releases=cosine(ac,bc,weights), artists=cosine(aa,ba), genres=cosine(ag,bg),
                      masters=cosine(am,bm) if am is not None and bm is not None else None,
                      styles=cosine(facets(a['collection'],'styles'),facets(b['collection'],'styles')),
                      labels=cosine(facets(a['collection'],'labels'),facets(b['collection'],'labels')))
    return dict(score=combine_components(components), component_scores=components,
                album_common=shared,common_albums=common_albums,version_pairs=[item for item in common_albums if item['different_versions']],
                album_a_size=len(keys_a),album_b_size=len(keys_b),
                album_a_coverage=round(100*len(shared)/len(keys_a),1) if keys_a else 0,
                album_b_coverage=round(100*len(shared)/len(keys_b),1) if keys_b else 0,
                algorithm_version=SCORE_VERSION, score_factors=DEFAULT_SCORE_FACTORS.copy(), artist_score=cosine(aa, ba), genre_score=cosine(ag, bg),
                common=ac & bc, only_a=ac - bc, only_b=bc - ac,
                artists_common=aa & ba, artists_a=aa - ba, artists_b=ba - aa,
                genres_common=ag & bg, genres_a=ag - bg, genres_b=bg - ag,
                for_a=bc & aw, for_b=ac & bw,
                trade_a=(ac & bw) - aw, trade_b=(bc & aw) - bw,
                a_size=len(ac), b_size=len(bc), a_coverage=round(100*len(ac & bc)/len(ac),1) if ac else 0,
                b_coverage=round(100*len(ac & bc)/len(bc),1) if bc else 0)


def dna(items):
    return dict(releases=len({x['id'] for x in items}), artists=len(facets(items,'artists')),
                genres=Counter(g for x in items for g in x.get('genres',[])).most_common(8))
