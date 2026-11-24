# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Single-purpose tool that scrapes canonical albums from [musicgenretree.org](https://www.musicgenretree.org/text_classics.html) (~1,100 albums across music genres), searches for them in MusicBrainz, and creates/populates a "Music Genre Tree – Classics" series there.

## Commands

```bash
# Search albums and cache results
python musictree_to_mb.py --export-csv resultados.csv

# Resume interrupted search from cache
python musictree_to_mb.py --load-csv resultados.csv --export-csv resultados.csv

# Create MB series and add albums (requires auth)
python musictree_to_mb.py --load-csv resultados.csv \
    --username USER --password PASS

# Simulate without modifying MusicBrainz
python musictree_to_mb.py --dry-run

# Add albums to an existing series
python musictree_to_mb.py --load-csv resultados.csv \
    --username USER --password PASS --series-mbid <MBID>
```

Other flags: `--skip-search`, `--no-resume`, `--verbose/-v`

## Dependencies

```
requests
beautifulsoup4
urllib3
```

No database needed — `resultados.csv` is the persistent cache.

## Architecture

All logic lives in `musictree_to_mb.py`. The workflow is:

1. **Scrape** `musicgenretree.org` → parse HTML with BeautifulSoup → `Album` dataclass list
2. **Search MusicBrainz** — three-tier fallback per album (exact title+artist → exact title → partial title+artist first word), scoring matches (threshold: 60)
3. **Write series** — create MB series via authenticated web session, add release groups as series relationships

**HTTP resilience:** 5 retries per request, exponential backoff (2s base, ×1.5), 1.2s rate-limit delay, rotation between two MB mirrors on SSL errors.

**CSV cache** (`resultados.csv`): stores `mb_release_group_id`, `mb_artist_id`, and `search_status` (`pending`/`found`/`not_found`/`ambiguous`/`error`) so runs can be resumed.

**Manual fallback:** exports `mb_series_relationships.json` for manual import if automated series creation fails.

## Current State

`resultados.csv` has 1,109 albums: ~1,047 found (94%), ~62 not found. Re-running with `--load-csv` skips already-resolved albums unless `--no-resume` is passed.
