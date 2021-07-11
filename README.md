# birdwatch

Twitter scraper similar to Twint, but without the bloat. It also
supports higher rates than snscrape.

Currently birdwatch works well for most use cases, but is a bit
bare-bones and very unstable at higher speeds.

## usage

birdwatch is currently usable as a Python library.

Create a session with `init_session` then pass it into `from_user` to
get a user's tweets:

	import birdwatch

	session = birdwatch.init_session()
	tweets = birdwatch.from_user(session, "parafactual", count=2000)

`count` defaults to 1000 and is not exact.
