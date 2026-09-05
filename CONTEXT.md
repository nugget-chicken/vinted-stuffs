# Vinted hunt

A buyer-side screening context: which second-hand listings are worth paying shipping and Vinted fees for, and when several listings from one seller become one checkout.

## Language

**Hunt**:
A saved search for one kind of thing the buyer wants (type, sizes, query, notes, hunt price).
_Avoid_: Watch (except as config key), alert, scrape

**Keep**:
A listing that is a true hunt match, steal or hunt value, at or above the score bar, and not high scam risk — and, if it is ordinary clothing sold alone, above the solo floor.
_Avoid_: Deal, hit, pass

**Solo floor**:
100 RON listing price. Ordinary clothing at or below this is never a keep by itself, unless it is a steal-band true match — then fees are worth it. Sneakers and premium knitwear are not bound by this clothing floor.
_Avoid_: Min price, price_from (do not put a floor on search; the scorer judges cheap listings)

**Hunt fit**:
Whether a listing genuinely matches a hunt's type, sizes, query, and notes — not merely the brand or a keyword.
_Avoid_: Relevant, match (unqualified)

**Bundle**:
Two or more listings from the same seller in one checkout: at least one keep, plus extra hunt-fit pieces that score at least 6 and are not skip or high scam risk, such that one checkout extra makes the combined absolute saving worth it. Prior keeps and extras stay in the bundle pool and can join a later checkout if they are still listed.
_Avoid_: Cart, lot, combo

**Bundle extra**:
A hunt-fit listing that is not a keep on its own, but is good enough to ride with a keep in a bundle (score at least 6, not skip, not high scam risk).
_Avoid_: Filler, add-on (unqualified)

**Checkout extra**:
The assumed buyer cost once per checkout for shipping plus Vinted fees, on top of listing prices. 25 RON when the seller is in Romania; 40 RON when the seller is in Poland or Hungary; 25 RON otherwise. One extra per seller checkout, not per item.
_Avoid_: Shipping (alone), fee, postage

**Seen key**:
The pair of a listing id and a hunt name. A listing already judged for one hunt can still be judged for a later hunt.
_Avoid_: seen_ids (legacy global suppress only)

**Closet crawl**:
After at least one hunt-fit from a seller, fetch up to 12 more of their active listings and score them against every hunt.
_Avoid_: Full scrape, monitor user (unqualified)

**Value band**:
steal, hunt, acceptable, or skip — price versus quality for that exact piece, after fees, not "under the search cap".
_Avoid_: Discount, percentage off
