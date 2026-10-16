"""Score-aware, non-romantic record-collector humour. No external text service."""
ZERO_COMMENTS = [
    '0%. Different planets. Both apparently have turntables.',
    'No shared albums. This listening party needs a referee.',
    'Zero overlap. The conversation should be excellent.',
    'Same hobby. Completely different evidence.'
]
COMMENT_POOLS = [
(15, ['Same format. Different universe.', 'Your record shops probably need different maps.',
      'A very respectable lack of overlap.', 'Two collections, proudly independent.',
      'The turntable is common ground. It is a start.', 'A small link. A large discovery budget.',
      'Almost strangers. Musically speaking.', 'One common album can start a very long argument.']),
(35, ['A few albums have crossed the border.', 'Some common ground. Bring a map.',
      'Different collections. A few very good coincidences.', 'Enough overlap to compare the receipts.',
      'Your collections have exchanged a polite nod.', 'Different routes. A few shared record shops.',
      'The conversation has a starting point.', 'A small musical conspiracy is forming.']),
(55, ['You two could survive a record store together.', 'Different taste, familiar territory.',
      'A healthy amount of musical agreement.', 'You might reach for the same bin.',
      'Similar instincts. Different detours.', 'Familiar favourites. Plenty left to discover.',
      'Enough agreement to share the next listening session.', 'The overlap is doing some useful work.']),
(70, ['Your collections have found a shared frequency.', 'You may need to label the record bags.',
      'There is a convincing amount of agreement.', 'Your record shop routes probably overlap.',
      'Two perspectives. Quite a few familiar albums.', 'Several bins would be worth checking together.',
      'Good overlap. Still room for surprises.', 'Your collections could finish a few album titles.']),
(85, ['Someone has been copying someone’s homework.', 'Those shopping lists look oddly familiar.',
      'One of you should check the initials on the sleeves.', 'Independent collections. Coordinated choices.',
      'A shared taste for very specific decisions.', 'You probably know the same dusty record shops.',
      'Your collections are comparing notes.', 'This is getting suspicious. In a vinyl sort of way.']),
(95, ['Please check whose shopping bag this is.', 'Your record shops may have confused your orders.',
      'A suspiciously familiar set of priorities.', 'Very little arguing over the next album.',
      'Nearly the same route through the bins.', 'The overlap has started taking up most of the room.',
      'Someone has been reading someone else’s list.', 'Two collections. One very specific habit.']),
(100, ['At this point, check whether you are actually the same person.', 'This is starting to look like an identity check.',
       'Your collections could share a filing cabinet.', 'The receipts might be more useful than the records now.',
       'Someone should check the delivery address.', 'Two collectors. Remarkably few disagreements.',
       'Independent record buying is apparently overrated.', 'Your collections appear to have rehearsed this.'])]


def comments_for_score(score):
    if score == 0:
        return ZERO_COMMENTS
    for ceiling, comments in COMMENT_POOLS:
        if score <= ceiling:
            return comments
    return COMMENT_POOLS[-1][1]


def conversation_for_score(score):
    if score is None:
        return ['Leave a message. The next record can wait.', 'Say hello. Good conversations have a B-side.']
    if score == 0:
        return ['0%? Different planets? You should probably discuss this.', 'No shared albums. Say hello and defend your record collection.']
    if score < 35:
        return ['A small link. A big excuse to recommend a record.', 'Introduce your collections. They barely know each other.']
    if score < 70:
        return ['You have a few albums to talk about. Say hello.', 'Compare notes before the next record-store visit.']
    return ['That much in common? Compare the receipts. Say hello.', 'Your collections already get along. Your turn.']


def online_for_score(score):
    if score == 0:
        return ['Online now. Establish interplanetary contact.', 'Online now. Time to investigate that 0%.']
    if score is not None and score >= 70:
        return ['Online now. Ask who copied whose collection.', 'Online now. Compare notes before the next needle drop.']
    return ['Online now. Say hello before the next side starts.', 'Online now. A good time to recommend a record.']
