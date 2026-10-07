"""Dry, non-romantic copy. Upper bounds are continuous, including decimals."""
COMMENT_POOLS = [
(15, [
'Different shelves. Different worlds.', 'Well... at least you both own records.',
'Your shelves have agreed to disagree.', 'A very respectable lack of overlap.',
'Same format. Different universe.', 'The only common ground might be the turntable.',
'Plenty of room for a second opinion.', 'Your record shop routes rarely cross.',
'This is how unfamiliar territory begins.', 'Two collections, remarkably independent decisions.']),
(35, [
'A few records have crossed the border.', 'There is a small bridge between these shelves.',
'Some common ground. Bring a map.', 'Not strangers, according to a few records.',
'An occasional nod across the record store.', 'Different directions, a few shared stops.',
'Your shelves have exchanged a brief hello.', 'A little overlap goes a long way.',
'The conversation has a starting point.', 'Enough in common to compare the receipts.']),
(55, [
'Different taste, familiar territory.', 'You two could survive a record store together.',
'The shelves are beginning to recognise each other.', 'A healthy amount of musical agreement.',
'You might reach for the same bin.', 'Similar instincts. Different detours.',
'A few shared favourites, plenty left to discover.', 'Your shelves speak a similar language.',
'The overlap is doing some useful work.', 'Enough agreement to split the listening session.']),
(70, [
'Okay, there is definitely something going on here.', 'The shelves have found a shared frequency.',
'Your record store routes probably overlap.', 'There is a convincing amount of agreement.',
'Two perspectives, familiar records.', 'You may need to label the record bags.',
'The common ground is getting crowded.', 'Several bins would be worth checking together.',
'Your shelves could finish a few album titles.', 'Good overlap. Still room for surprises.']),
(85, [
'Now this is getting suspicious.', 'Someone has been copying someone’s homework.',
'Are you sure you do not share a record shelf?', 'Those shopping lists look oddly familiar.',
'You might owe the same record shop an explanation.', 'The shelves are comparing notes.',
'Independent collections. Surprisingly coordinated choices.', 'One of you should check the initials on the sleeves.',
'A shared taste for very specific decisions.', 'You probably know the same dusty corners.']),
(95, [
'Two shelves. An impressive amount of agreement.', 'Your record shops may have confused your orders.',
'Please check whose shopping bag this is.', 'A suspiciously familiar set of priorities.',
'The shelves could almost share an index.', 'There is very little arguing over the next record.',
'Someone has been reading someone else’s list.', 'Nearly the same route through the bins.',
'The overlap has started taking up most of the room.', 'You could swap shelf labels and almost get away with it.']),
(100, [
'At this point, check whether you are actually the same person.',
'Two users. One suspiciously similar record shelf.', 'This is less a comparison and more an identity check.',
'Please make sure these are two different shelves.', 'Your collections could share a filing cabinet.',
'The receipts might be more useful than the records now.', 'Almost a duplicate. Almost.',
'Somebody should check the delivery address.', 'The shelves appear to have rehearsed this.',
'Two collectors, remarkably few disagreements.'])]


def comments_for_score(score):
    for ceiling, comments in COMMENT_POOLS:
        if score <= ceiling:
            return comments
    return COMMENT_POOLS[-1][1]
