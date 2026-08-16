# DesignDoc Revision Notes

Proposed changes/revisions to docs/DesignDoc.md, kept separate so the design doc itself stays untouched by anyone but its author. Feel free to fold whatever's useful back in, or ignore.

## Scraping (step 1) — audio rate-limiting

Confirmed: skipping soundbyte downloads (as noted in the doc) resolves the 429 error. Ran a 10-word test with audio disabled — completed quickly with no rate-limit errors, and word/gloss/part-of-speech extraction all worked correctly. Sample output:

```
것    thing; something; that which; what; ...           Dependent noun
하다   (transitive) to do; ...                            Verb
있다   to stay, remain in a location                       Adjective, Verb
되다   to become                                           Adjective, Verb
나    I, me; the first-person singular plain pronoun      Noun, Pronoun
없다   to have none; (to be) lacking; (to be) nonexistent  Adjective, Verb
사람   human being, person                                 Counter, Noun
우리   cage, pen, coop, enclosure ...                       Counter, Noun, Pronoun
아니다  to not be (something)                               Adjective
같다   (to be) the same                                     Adjective
```

The rate limit is specifically on `upload.wikimedia.org` (the file/media host), not `en.wiktionary.org` (word pages and the frequency list have never 429'd). `scraper.py`'s `scrape()` now defaults to `fetch_audio=False` for this reason; the audio-downloading code (`parse_audio_url`, `download_audio`) is still there and works, just opt-in via `fetch_audio=True`.

Possible future approaches for soundbytes, if wanted:
- Much longer delay specifically between audio requests (separate from page-fetch delay).
- Batch/spread audio downloads across multiple runs over time.
- A different audio source than Wikimedia Commons.
