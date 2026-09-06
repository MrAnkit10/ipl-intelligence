"""Team-name normalization (blueprint section 42).

Cricsheet records the name a team played under at the time, so the same
on-field entity can appear under multiple strings across seasons (a
mid-competition city rename, or a plain spelling fix). TEAM_MAPPING merges
those into one canonical name for analytics, while leaving distinct
franchises that happen to share a city separate.

Judgment calls (reversible — just edit the dict below):
- Deccan Chargers -> Sunrisers Hyderabad: kept SEPARATE. Deccan Chargers'
  IPL license was terminated in 2012; Sunrisers Hyderabad is a newly
  awarded, separately owned franchise, not a rename.
- Gujarat Lions vs Gujarat Titans, Pune Warriors vs Rising Pune
  Supergiant(s): kept SEPARATE for the same reason (different franchises,
  same city).
- Rising Pune Supergiant / Rising Pune Supergiants: merged — this is the
  same 2016-17 franchise with an inconsistent trailing "s" across seasons
  in the source data, not a different team.

Never overwrite matches.parquet/deliveries.parquet with these values —
apply the mapping at analysis time so the original source strings stay
auditable.
"""

TEAM_MAPPING = {
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
}

TEAM_CODES = {
    "Royal Challengers Bengaluru": "RCB",
    "Mumbai Indians": "MI",
    "Chennai Super Kings": "CSK",
    "Kolkata Knight Riders": "KKR",
    "Rajasthan Royals": "RR",
    "Delhi Capitals": "DC",
    "Sunrisers Hyderabad": "SRH",
    "Punjab Kings": "PBKS",
    "Gujarat Titans": "GT",
    "Lucknow Super Giants": "LSG",
    "Deccan Chargers": "DC2",
    "Gujarat Lions": "GL",
    "Pune Warriors": "PW",
    "Rising Pune Supergiant": "RPS",
    "Kochi Tuskers Kerala": "KTK",
}


def canonical_team_name(name: str) -> str:
    return TEAM_MAPPING.get(name, name)


def team_code(canonical_name: str) -> str:
    return TEAM_CODES.get(canonical_name, canonical_name)
