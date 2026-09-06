"""Venue-name normalization (blueprint section 43).

Cricsheet records venue names inconsistently across seasons — sometimes
with a city suffix, sometimes without, sometimes with a punctuation
variant, and in a few cases under a since-changed official name. Left
unmerged, the same physical ground fragments into 2-3 separate "venues" in
every venue-level analysis, and dilutes the venue feature signal in both
ML models (win probability, player performance) since the model sees them
as unrelated categories.

Discovered while writing sql/analytics_queries.sql's venue-profile query
and seeing e.g. "Wankhede Stadium" and "Wankhede Stadium, Mumbai" as
separate rows.

Judgment calls (reversible — just edit the dict below):
- Feroz Shah Kotla -> Arun Jaitley Stadium, Delhi: same ground, renamed in
  2019.
- Sardar Patel Stadium, Motera -> Narendra Modi Stadium, Ahmedabad: same
  ground, renamed in 2021.
- Subrata Roy Sahara Stadium -> Maharashtra Cricket Association Stadium,
  Pune: same ground under an earlier sponsorship name (used in 2012-2014
  IPL seasons).
- Sheikh Zayed Stadium -> Zayed Cricket Stadium, Abu Dhabi: same ground
  (Sheikh Zayed Cricket Stadium, Abu Dhabi) recorded under a shorter name
  in some seasons; slightly lower confidence than the other three, but no
  other distinct Abu Dhabi venue exists in this dataset to confuse it with.
Every other entry is a plain suffix/punctuation variant of the same
string (e.g. "M.Chinnaswamy Stadium" vs "M Chinnaswamy Stadium, Bengaluru")
and merged with high confidence. Venues that appear only once in the raw
data (no variant to compare against) are left untouched rather than
guessing at a city to append.

Never overwrite matches.parquet/deliveries.parquet with these values —
apply the mapping at analysis/feature-build time, same as team names.
"""

VENUE_MAPPING = {
    "Arun Jaitley Stadium": "Arun Jaitley Stadium, Delhi",
    "Feroz Shah Kotla": "Arun Jaitley Stadium, Delhi",
    "Brabourne Stadium": "Brabourne Stadium, Mumbai",
    "Dr DY Patil Sports Academy": "Dr DY Patil Sports Academy, Mumbai",
    "Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium": (
        "Dr. Y.S. Rajasekhara Reddy ACA-VDCA Cricket Stadium, Visakhapatnam"
    ),
    "Eden Gardens": "Eden Gardens, Kolkata",
    "Himachal Pradesh Cricket Association Stadium": "Himachal Pradesh Cricket Association Stadium, Dharamsala",
    "M Chinnaswamy Stadium": "M Chinnaswamy Stadium, Bengaluru",
    "M.Chinnaswamy Stadium": "M Chinnaswamy Stadium, Bengaluru",
    "MA Chidambaram Stadium": "MA Chidambaram Stadium, Chepauk, Chennai",
    "MA Chidambaram Stadium, Chepauk": "MA Chidambaram Stadium, Chepauk, Chennai",
    "Maharaja Yadavindra Singh International Cricket Stadium, New Chandigarh": (
        "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur"
    ),
    "Maharashtra Cricket Association Stadium": "Maharashtra Cricket Association Stadium, Pune",
    "Subrata Roy Sahara Stadium": "Maharashtra Cricket Association Stadium, Pune",
    "Sardar Patel Stadium, Motera": "Narendra Modi Stadium, Ahmedabad",
    "Punjab Cricket Association IS Bindra Stadium": "Punjab Cricket Association IS Bindra Stadium, Mohali",
    "Punjab Cricket Association IS Bindra Stadium, Mohali, Chandigarh": (
        "Punjab Cricket Association IS Bindra Stadium, Mohali"
    ),
    "Punjab Cricket Association Stadium, Mohali": "Punjab Cricket Association IS Bindra Stadium, Mohali",
    "Rajiv Gandhi International Stadium": "Rajiv Gandhi International Stadium, Uppal, Hyderabad",
    "Rajiv Gandhi International Stadium, Uppal": "Rajiv Gandhi International Stadium, Uppal, Hyderabad",
    "Sawai Mansingh Stadium": "Sawai Mansingh Stadium, Jaipur",
    "Shaheed Veer Narayan Singh International Stadium": "Shaheed Veer Narayan Singh International Stadium, Raipur",
    "Sheikh Zayed Stadium": "Zayed Cricket Stadium, Abu Dhabi",
    "Wankhede Stadium": "Wankhede Stadium, Mumbai",
}


def canonical_venue_name(name: str) -> str:
    return VENUE_MAPPING.get(name, name)
