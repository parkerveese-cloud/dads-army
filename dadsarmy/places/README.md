# Places to go

`uk.tsv.gz` lists about 58,000 places across the UK that could be a refuge or a help point in an emergency:

- community centres and halls
- leisure centres (but not private clubs or single-sport venues)
- libraries
- hospitals with emergency care (A&E or a minor injuries unit)
- fire and police stations
- emergency assembly points
- named hills, with their heights
- named parks

Dads Army reads it on your own machine to find the ones near home, so finding them needs no internet and tells nobody where you live.

**It's a list of possibilities, not official refuges.** Councils decide where rest centres open when people have to leave their homes, and announce it at the time. Local radio and the council's website will say where.

## Where it comes from

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available under the [Open Database Licence (ODbL)](https://opendatacommons.org/licenses/odbl/). This file is a database derived from OpenStreetMap, and is shared under the same licence.

It was built from the Geofabrik extract of the United Kingdom, using `tools/build_places.py` in this repository. The file's first line gives the date it was built. Some places are missing or out of date: you can correct them on [openstreetmap.org](https://www.openstreetmap.org).

## Format

The file is gzipped, tab-separated text with one place per line:

| Column | What it is |
|---|---|
| 1 | Latitude |
| 2 | Longitude |
| 3 | Type code: see the table below |
| 4 | Name |
| 5 | Height in metres, for hills |

| Code | Type |
|---|---|
| `c` | Community centre or hall |
| `l` | Leisure centre |
| `b` | Library |
| `h` | Hospital with A&E |
| `f` | Fire station |
| `p` | Police station |
| `a` | Emergency assembly point |
| `e` | High ground |
| `k` | Park |
