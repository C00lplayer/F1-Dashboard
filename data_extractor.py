"""
F1 FastF1 -> Power BI data pipeline  (fixed version)

Requirements:
    pip install -U fastf1 pandas numpy requests

    IMPORTANT: use a recent FastF1 (3.5+; 3.8.x at time of writing). Older
    versions fetch results from the retired ergast.com host, which is the #1
    reason Points / Position / Status come back empty.

Run:
    python f1_data_pipeline.py

Output (powerbi_data/):
    races.csv, drivers.csv, constructors.csv
    race_results.csv, sprint_results.csv, qualifying_results.csv
    race_driver_combined.csv, race_summary.csv, race_weather.csv
    fastest_laps.csv
    driver_standings.csv, constructor_standings.csv
    driver_cumulative_points.csv, constructor_cumulative_points.csv
    constructor_driver_contributions.csv, constructor_driver_totals.csv
    quali_vs_race.csv
    past_winners.csv
    next_race.csv, next_race_weather.csv
    track_coordinates.csv, track_corners.csv
    predictions.csv
"""

from pathlib import Path
import warnings

import fastf1
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# ============================================================
# CONFIGURATION
# ============================================================

SEASON = 2026

# How many previous seasons to search for past winners at the next circuit
PAST_YEARS = 8
# Loading laps for every past year is slow. Turn on if you want the
# fastest lap time for each past winner row.
PAST_WINNER_FASTEST_LAP = False

OUTPUT_DIR = Path("powerbi_data")
CACHE_DIR = Path("fastf1_cache")
LOCATIONS_FILE = Path("circuit_locations.csv")  # optional: RaceName,Latitude,Longitude

OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

print(f"FastF1 version: {fastf1.__version__}")

# Used ONLY if the API returns positions but no points (e.g. data lag)
RACE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
SPRINT_POINTS = [8, 7, 6, 5, 4, 3, 2, 1]


# ============================================================
# HELPERS
# ============================================================

def save(df, filename):
    path = OUTPUT_DIR / filename
    df.to_csv(path, index=False)
    print(f"Saved {path} ({len(df):,} rows)")


def fmt_lap(td):
    """Timedelta -> m:ss.mmm (blank when missing)."""
    if td is None or pd.isna(td):
        return ""
    total = td.total_seconds()
    minutes = int(total // 60)
    return f"{minutes}:{total - 60 * minutes:06.3f}"


def td_seconds(series):
    return pd.to_timedelta(series, errors="coerce").dt.total_seconds()


def td_strings(series):
    return pd.to_timedelta(series, errors="coerce").apply(fmt_lap)


def load_session(year, rnd, ident, laps=False, telemetry=False, weather=False):
    """Load a session. Results (Position/Points/Status...) always load."""
    session = fastf1.get_session(year, rnd, ident)
    session.load(laps=laps, telemetry=telemetry, weather=weather, messages=False)
    return session


def results_ready(res):
    return res is not None and len(res) > 0 and pd.to_numeric(
        res["Position"], errors="coerce"
    ).notna().any()


def tidy_results(res, event, session_type):
    """Convert a FastF1 SessionResults into a clean flat table."""
    res = pd.DataFrame(res).reset_index(drop=True)

    full = res["FullName"].astype(str).str.strip()
    driver = full.where(~full.isin(["", "nan", "None"]), res["Abbreviation"])

    position = pd.to_numeric(res["Position"], errors="coerce")
    points = pd.to_numeric(res["Points"], errors="coerce")
    points_source = "api"

    if points.isna().all() and position.notna().any():
        table = RACE_POINTS if session_type == "Race" else SPRINT_POINTS
        points = position.apply(
            lambda p: table[int(p) - 1] if pd.notna(p) and 1 <= p <= len(table) else 0.0
        )
        points_source = "computed_from_position"

    grid = pd.to_numeric(res["GridPosition"], errors="coerce")
    grid = grid.where(grid > 0)  # API can return -1 / 0 (pit-lane start)

    rnd = int(event["RoundNumber"])
    return pd.DataFrame({
        "Season": SEASON,
        "RaceId": str(rnd),
        "Round": rnd,
        "RaceName": event["EventName"],
        "RaceDate": event["RaceStartUtc"].strftime("%Y-%m-%d"),
        "SessionType": session_type,
        "Driver": driver,
        "Abbreviation": res["Abbreviation"],
        "DriverNumber": res["DriverNumber"],
        "Constructor": res["TeamName"],
        "Position": position,
        "ClassifiedPosition": res["ClassifiedPosition"].astype(str),
        "GridPosition": grid,
        "Points": points.fillna(0.0),
        "PointsSource": points_source,
        "Laps": pd.to_numeric(res["Laps"], errors="coerce"),
        "Status": res["Status"],
        "TimeSeconds": td_seconds(res["Time"]),
    })


def fastest_lap_table(session):
    """Per-driver fastest lap from lap data (results have no lap-time columns)."""
    laps = session.laps
    if laps is None or len(laps) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(laps)
    df = df[df["LapTime"].notna()]
    if "Deleted" in df.columns:
        df = df[~df["Deleted"].fillna(False).astype(bool)]
    if df.empty:
        return pd.DataFrame()

    idx = df.groupby("Driver")["LapTime"].idxmin()
    best = df.loc[idx, ["Driver", "LapTime", "LapNumber"]].copy()
    best = best.rename(columns={
        "Driver": "Abbreviation",
        "LapTime": "_lt",
        "LapNumber": "FastestLapNumber",
    })
    best["FastestLapSeconds"] = td_seconds(best["_lt"])
    best["FastestLapTime"] = best["_lt"].apply(fmt_lap)
    best["FastestLapRank"] = best["FastestLapSeconds"].rank(method="min").astype(int)
    return best.drop(columns="_lt")


def weather_summary(session):
    try:
        w = session.weather_data
        if w is None or len(w) == 0:
            return {}
        return {
            "AirTempAvg": round(float(w["AirTemp"].mean()), 1),
            "TrackTempAvg": round(float(w["TrackTemp"].mean()), 1),
            "HumidityAvg": round(float(w["Humidity"].mean()), 1),
            "WindSpeedAvg": round(float(w["WindSpeed"].mean()), 1),
            "RainDuringRace": bool(w["Rainfall"].any()),
        }
    except Exception:
        return {}


# ============================================================
# 1. SCHEDULE
# ============================================================

print("\nLoading season schedule...")

# include_testing=False removes pre-season testing (RoundNumber 0)
schedule = fastf1.get_event_schedule(SEASON, include_testing=False).copy()
schedule = schedule[schedule["RoundNumber"] > 0].copy()

# Race start (UTC). Session5 is the Race on every current format.
if "Session5DateUtc" in schedule.columns:
    race_start = pd.to_datetime(schedule["Session5DateUtc"])
else:
    race_start = pd.Series(pd.NaT, index=schedule.index)
schedule["RaceStartUtc"] = race_start.fillna(
    pd.to_datetime(schedule["EventDate"]) + pd.Timedelta(hours=14)
)

now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
is_done = (schedule["RaceStartUtc"] + pd.Timedelta(hours=3)) < now_utc

completed_events = schedule[is_done].sort_values("RoundNumber")
future_events = schedule[~is_done].sort_values("RoundNumber")

print(f"{len(completed_events)} completed rounds, {len(future_events)} upcoming")

races = pd.DataFrame({
    "RaceId": schedule["RoundNumber"].astype(int).astype(str),
    "Round": schedule["RoundNumber"].astype(int),
    "RaceName": schedule["EventName"],
    "Country": schedule["Country"],
    "Location": schedule["Location"],
    "EventFormat": schedule["EventFormat"],
    "EventDate": schedule["RaceStartUtc"].dt.strftime("%Y-%m-%d"),
    "RaceStartUtc": schedule["RaceStartUtc"].dt.strftime("%Y-%m-%d %H:%M"),
    "OfficialEventName": schedule["OfficialEventName"],
    "Completed": is_done.values,
}).sort_values("Round")

save(races, "races.csv")


# ============================================================
# 2. LOAD COMPLETED RACE / SPRINT / QUALIFYING DATA
# ============================================================

race_frames, sprint_frames, quali_frames = [], [], []
fastest_frames, weather_rows = [], []
driver_records, constructor_records = {}, {}

for _, event in completed_events.iterrows():
    rnd = int(event["RoundNumber"])
    name = event["EventName"]
    print(f"\nRound {rnd}: {name}")

    # ---------------- Race ----------------
    try:
        race = load_session(SEASON, rnd, "R", laps=True, weather=True)
    except Exception as e:
        print(f"  Race could not be loaded: {e}")
        continue

    if not results_ready(race.results):
        print("  Race results not published yet (Position empty) - skipping")
        continue

    rt = tidy_results(race.results, event, "Race")
    if rt["PointsSource"].iloc[0] != "api":
        print("  WARNING: API returned no points; computed from finishing position")

    fl = fastest_lap_table(race)
    if not fl.empty:
        rt = rt.merge(fl, on="Abbreviation", how="left")
        f = fl.sort_values("FastestLapSeconds").iloc[0]
        fastest_frames.append(rt[rt["Abbreviation"] == f["Abbreviation"]].iloc[[0]][[
            "RaceId", "Round", "RaceName", "Driver", "Abbreviation", "Constructor",
            "FastestLapTime", "FastestLapSeconds", "FastestLapNumber",
        ]])
    else:
        print("  No lap data available for fastest lap")
        for c in ["FastestLapNumber", "FastestLapSeconds", "FastestLapTime", "FastestLapRank"]:
            rt[c] = np.nan

    race_frames.append(rt)

    ws = weather_summary(race)
    if ws:
        weather_rows.append({"RaceId": str(rnd), "Round": rnd, "RaceName": name, **ws})

    # driver / constructor metadata
    for _, r in pd.DataFrame(race.results).iterrows():
        d = rt.loc[rt["Abbreviation"] == r["Abbreviation"], "Driver"].iloc[0]
        driver_records[d] = {
            "Driver": d,
            "Abbreviation": r["Abbreviation"],
            "FirstName": r["FirstName"],
            "LastName": r["LastName"],
            "CountryCode": r["CountryCode"],
            "DriverId": r["DriverId"],
            "HeadshotUrl": r["HeadshotUrl"],
        }
        constructor_records[r["TeamName"]] = {
            "Constructor": r["TeamName"],
            "TeamColor": r["TeamColor"],
            "TeamId": r["TeamId"],
        }

    # ---------------- Sprint (counts towards championship!) ----------------
    if "sprint" in str(event["EventFormat"]).lower():
        try:
            sprint = load_session(SEASON, rnd, "S")
            if results_ready(sprint.results):
                sprint_frames.append(tidy_results(sprint.results, event, "Sprint"))
            else:
                print("  Sprint results not available yet")
        except Exception as e:
            print(f"  Sprint could not be loaded: {e}")

    # ---------------- Qualifying ----------------
    try:
        quali = load_session(SEASON, rnd, "Q")
        qr = pd.DataFrame(quali.results).reset_index(drop=True)
        if len(qr):
            full = qr["FullName"].astype(str).str.strip()
            qpos = pd.to_numeric(qr["Position"], errors="coerce")
            quali_frames.append(pd.DataFrame({
                "Season": SEASON,
                "RaceId": str(rnd),
                "Round": rnd,
                "RaceName": name,
                "Driver": full.where(~full.isin(["", "nan", "None"]), qr["Abbreviation"]),
                "Abbreviation": qr["Abbreviation"],
                "Constructor": qr["TeamName"],
                "QualifyingPosition": qpos,
                "Q1": td_strings(qr["Q1"]), "Q2": td_strings(qr["Q2"]), "Q3": td_strings(qr["Q3"]),
                "Q1Seconds": td_seconds(qr["Q1"]),
                "Q2Seconds": td_seconds(qr["Q2"]),
                "Q3Seconds": td_seconds(qr["Q3"]),
            }))
    except Exception as e:
        print(f"  Qualifying could not be loaded: {e}")

if not race_frames:
    raise SystemExit(
        "\nNo race results could be loaded.\n"
        "  1) pip install -U fastf1  (old versions use the dead ergast.com host)\n"
        "  2) Check your internet / that the races have actually finished\n"
        "  3) Try deleting the fastf1_cache folder (it may have cached an empty response)"
    )


# ============================================================
# 3. CORE TABLES
# ============================================================

race_results = pd.concat(race_frames, ignore_index=True)
sprint_results = (
    pd.concat(sprint_frames, ignore_index=True) if sprint_frames else pd.DataFrame()
)
qualifying_results = (
    pd.concat(quali_frames, ignore_index=True) if quali_frames else pd.DataFrame(
        columns=["RaceId", "Abbreviation", "QualifyingPosition"]
    )
)
drivers = pd.DataFrame(list(driver_records.values()))
constructors = pd.DataFrame(list(constructor_records.values()))

save(drivers, "drivers.csv")
save(constructors, "constructors.csv")
save(race_results, "race_results.csv")
if not sprint_results.empty:
    save(sprint_results, "sprint_results.csv")
save(qualifying_results, "qualifying_results.csv")
if fastest_frames:
    save(pd.concat(fastest_frames, ignore_index=True), "fastest_laps.csv")
if weather_rows:
    save(pd.DataFrame(weather_rows), "race_weather.csv")

# Every points-scoring session (race + sprint) - used for all standings
points_events = pd.concat(
    [race_results, sprint_results], ignore_index=True
)[["Round", "RaceId", "RaceName", "Driver", "Abbreviation", "Constructor",
   "Points", "SessionType"]]


# ============================================================
# 4. QUALIFYING + RACE COMBINED
# ============================================================

combined = race_results.merge(
    qualifying_results[["RaceId", "Abbreviation", "QualifyingPosition"]],
    on=["RaceId", "Abbreviation"],
    how="left",
)
# API grid can be missing (-1) -> fall back to qualifying position
combined["StartPosition"] = combined["GridPosition"].fillna(combined["QualifyingPosition"])
# Positive = places gained vs qualifying
combined["PositionChange"] = combined["QualifyingPosition"] - combined["Position"]
combined["GridChange"] = combined["StartPosition"] - combined["Position"]

save(combined, "race_driver_combined.csv")


# ============================================================
# 5. RACE SUMMARY (winner / pole / fastest lap) for the Past Races page
# ============================================================

summary_rows = []
for rnd, g in combined.groupby("Round"):
    win = g[g["Position"] == 1]
    pole = g[g["QualifyingPosition"] == 1]
    fl = g[g["FastestLapRank"] == 1] if "FastestLapRank" in g else g.iloc[0:0]
    summary_rows.append({
        "Round": rnd,
        "RaceId": str(rnd),
        "RaceName": g["RaceName"].iloc[0],
        "Winner": win["Driver"].iloc[0] if len(win) else "",
        "WinnerConstructor": win["Constructor"].iloc[0] if len(win) else "",
        "WinnerStartPosition": win["StartPosition"].iloc[0] if len(win) else np.nan,
        "PoleDriver": pole["Driver"].iloc[0] if len(pole) else "",
        "PoleConstructor": pole["Constructor"].iloc[0] if len(pole) else "",
        "FastestLapDriver": fl["Driver"].iloc[0] if len(fl) else "",
        "FastestLapTime": fl["FastestLapTime"].iloc[0] if len(fl) else "",
    })
save(pd.DataFrame(summary_rows), "race_summary.csv")


# ============================================================
# 6. CUMULATIVE + STANDINGS
# ============================================================

race_names = races[["Round", "RaceId", "RaceName"]]


def per_round_and_cumulative(events, key):
    """Round points and running total per driver / constructor."""
    per_round = events.pivot_table(
        index="Round", columns=key, values="Points", aggfunc="sum", fill_value=0
    ).sort_index()
    cum = per_round.cumsum()
    out = per_round.stack().rename("RoundPoints").to_frame()
    out["CumulativePoints"] = cum.stack()
    return out.reset_index()


def trim_before_first_round(df, key, source):
    """Drop rows from before a driver/team first appeared (avoid fake 0-point rows)."""
    first = source.groupby(key)["Round"].min().rename("FirstRound")
    df = df.merge(first, on=key, how="left")
    return df[df["Round"] >= df["FirstRound"]].drop(columns="FirstRound")


# ---- Drivers ----
driver_cum = per_round_and_cumulative(points_events, "Driver")
driver_cum = trim_before_first_round(driver_cum, "Driver", race_results)
driver_cum = driver_cum.merge(race_names, on="Round", how="left")
driver_cum = driver_cum.sort_values(["Driver", "Round"])
save(
    driver_cum[["Round", "RaceId", "RaceName", "Driver", "RoundPoints", "CumulativePoints"]],
    "driver_cumulative_points.csv",
)

flags = race_results.assign(
    Win=(race_results["Position"] == 1).astype(int),
    Podium=(race_results["Position"] <= 3).astype(int),
)
wins = flags.pivot_table(index="Round", columns="Driver", values="Win",
                         aggfunc="sum", fill_value=0).cumsum().stack().rename("Wins")
podiums = flags.pivot_table(index="Round", columns="Driver", values="Podium",
                            aggfunc="sum", fill_value=0).cumsum().stack().rename("Podiums")

driver_standings = (
    driver_cum.rename(columns={"CumulativePoints": "Points"})
    .set_index(["Round", "Driver"])
    .join(wins)
    .join(podiums)
    .reset_index()
)

team_map = race_results[["Round", "Driver", "Constructor"]].drop_duplicates(["Round", "Driver"])
driver_standings = driver_standings.merge(team_map, on=["Round", "Driver"], how="left")
driver_standings = driver_standings.sort_values(["Driver", "Round"])
driver_standings["Constructor"] = driver_standings.groupby("Driver")["Constructor"].transform(
    lambda s: s.ffill().bfill()
)

sort_key = (
    driver_standings["Points"] * 1e6
    + driver_standings["Wins"].fillna(0) * 1e3
    + driver_standings["Podiums"].fillna(0)
)
driver_standings["Position"] = (
    sort_key.groupby(driver_standings["Round"]).rank(method="min", ascending=False).astype(int)
)
driver_standings["Season"] = SEASON
driver_standings = driver_standings.sort_values(["Round", "Position"])
save(
    driver_standings[["Season", "Round", "RaceId", "RaceName", "Position", "Driver",
                      "Constructor", "Points", "RoundPoints", "Wins", "Podiums"]],
    "driver_standings.csv",
)

# ---- Constructors ----
con_cum = per_round_and_cumulative(points_events, "Constructor")
con_cum = trim_before_first_round(con_cum, "Constructor", race_results)
con_cum = con_cum.merge(race_names, on="Round", how="left").sort_values(["Constructor", "Round"])
save(
    con_cum[["Round", "RaceId", "RaceName", "Constructor", "RoundPoints", "CumulativePoints"]],
    "constructor_cumulative_points.csv",
)

constructor_standings = con_cum.rename(columns={"CumulativePoints": "Points"}).copy()
constructor_standings["Position"] = (
    constructor_standings.groupby("Round")["Points"]
    .rank(method="min", ascending=False).astype(int)
)
constructor_standings["Season"] = SEASON
constructor_standings = constructor_standings.sort_values(["Round", "Position"])
save(
    constructor_standings[["Season", "Round", "RaceId", "RaceName", "Position",
                           "Constructor", "Points", "RoundPoints"]],
    "constructor_standings.csv",
)


# ============================================================
# 7. CONSTRUCTOR -> DRIVER CONTRIBUTION
# ============================================================

contribution = (
    points_events
    .groupby(["Round", "RaceId", "RaceName", "Constructor", "Driver"], as_index=False)["Points"]
    .sum()
    .rename(columns={"Points": "DriverPoints"})
)
contribution["ConstructorPoints"] = contribution.groupby(
    ["Round", "Constructor"])["DriverPoints"].transform("sum")
contribution["ContributionPct"] = np.where(
    contribution["ConstructorPoints"] > 0,
    contribution["DriverPoints"] / contribution["ConstructorPoints"] * 100,
    0.0,
)
save(contribution.sort_values(["Round", "Constructor"]),
     "constructor_driver_contributions.csv")

totals = (
    points_events.groupby(["Constructor", "Driver"], as_index=False)["Points"]
    .sum().rename(columns={"Points": "SeasonDriverPoints"})
)
totals["SeasonConstructorPoints"] = totals.groupby("Constructor")[
    "SeasonDriverPoints"].transform("sum")
totals["ContributionPct"] = np.where(
    totals["SeasonConstructorPoints"] > 0,
    totals["SeasonDriverPoints"] / totals["SeasonConstructorPoints"] * 100,
    0.0,
)
save(totals, "constructor_driver_totals.csv")


# ============================================================
# 8. QUALIFYING VS RACE
# ============================================================

quali_vs_race = (
    combined.groupby(["Driver", "Constructor"], as_index=False)
    .agg(
        AvgQualifyingPosition=("QualifyingPosition", "mean"),
        AvgFinishPosition=("Position", "mean"),
        Races=("RaceId", "nunique"),
    )
)
quali_vs_race["AvgPositionsGained"] = (
    quali_vs_race["AvgQualifyingPosition"] - quali_vs_race["AvgFinishPosition"]
)
save(quali_vs_race, "quali_vs_race.csv")


# ============================================================
# 9. NEXT RACE
# ============================================================

def find_round(year, location, race_name):
    """Find the round number of the same circuit in another season."""
    try:
        sched = fastf1.get_event_schedule(year, include_testing=False)
    except Exception:
        return None
    m = sched[sched["Location"].astype(str).str.lower() == str(location).lower()]
    if m.empty:
        m = sched[sched["EventName"].astype(str).str.lower() == str(race_name).lower()]
    return int(m.iloc[0]["RoundNumber"]) if not m.empty else None


WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 71: "Light snow", 73: "Snow",
    75: "Heavy snow", 80: "Rain showers", 81: "Heavy showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm",
}


def get_coordinates(race_name, location):
    if LOCATIONS_FILE.exists():
        loc = pd.read_csv(LOCATIONS_FILE)
        m = loc[loc["RaceName"] == race_name]
        if not m.empty:
            return float(m.iloc[0]["Latitude"]), float(m.iloc[0]["Longitude"])
    try:  # free geocoder fallback (city-level accuracy is fine for weather)
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1}, timeout=20,
        )
        r.raise_for_status()
        hit = r.json().get("results", [])
        if hit:
            return hit[0]["latitude"], hit[0]["longitude"]
    except Exception as e:
        print(f"  Geocoding failed: {e}")
    return None


def get_weather_forecast(lat, lon):
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            # Open-Meteo wants a comma-separated string, not a list
            "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m",
            "timezone": "auto",
            "forecast_days": 16,
        },
        timeout=20,
    )
    r.raise_for_status()
    h = r.json()["hourly"]
    w = pd.DataFrame({
        "DateTime": pd.to_datetime(h["time"]),
        "Temperature": h["temperature_2m"],
        "RainProbability": h["precipitation_probability"],
        "WeatherCode": h["weather_code"],
        "WindSpeed": h["wind_speed_10m"],
    })
    w["Date"] = w["DateTime"].dt.date.astype(str)
    w["WeatherDescription"] = w["WeatherCode"].map(WMO).fillna("Unknown")
    return w


next_race = pd.DataFrame()
next_event = None

if len(future_events) > 0:
    next_event = future_events.iloc[0]
    next_round = int(next_event["RoundNumber"])
    race_date = next_event["RaceStartUtc"].strftime("%Y-%m-%d")

    next_race = pd.DataFrame([{
        "Season": SEASON,
        "Round": next_round,
        "RaceName": next_event["EventName"],
        "OfficialEventName": next_event["OfficialEventName"],
        "Country": next_event["Country"],
        "Location": next_event["Location"],
        "EventFormat": next_event["EventFormat"],
        "RaceDate": race_date,
        "RaceStartUtc": next_event["RaceStartUtc"].strftime("%Y-%m-%d %H:%M"),
        "WeatherDescription": "",
        "WeatherProbability": np.nan,
        "SafetyCarPrediction": np.nan,
        "FastestLapPrediction": "",
        "PredictedP1": "", "PredictedP2": "", "PredictedP3": "",
    }])

    # ---------------- Weather ----------------
    coords = get_coordinates(next_event["EventName"], next_event["Location"])
    if coords:
        try:
            weather = get_weather_forecast(*coords)
            weather["RaceName"] = next_event["EventName"]
            rd = pd.Timestamp(race_date)
            window = weather[
                (weather["DateTime"] >= rd - pd.Timedelta(days=2))
                & (weather["DateTime"] < rd + pd.Timedelta(days=1))
            ]
            if window.empty:
                print("\nRace is beyond the 16-day forecast window; no weather yet")
            else:
                save(window, "next_race_weather.csv")
                race_day = window[window["Date"] == race_date]
                if not race_day.empty:
                    next_race.loc[0, "WeatherProbability"] = race_day["RainProbability"].max()
                    next_race.loc[0, "WeatherDescription"] = race_day["WeatherDescription"].mode().iloc[0]
        except Exception as e:
            print(f"Weather API failed: {e}")
    else:
        print("\nNo coordinates found - add the race to circuit_locations.csv for weather")

    save(next_race, "next_race.csv")
else:
    print("\nNo future race found (season finished?)")


# ============================================================
# 10. PAST WINNERS AT THE NEXT CIRCUIT
# ============================================================

if next_event is not None:
    print("\nCollecting past winners for", next_event["EventName"])
    rows = []

    for year in range(SEASON - 1, SEASON - 1 - PAST_YEARS, -1):
        rnd = find_round(year, next_event["Location"], next_event["EventName"])
        if rnd is None:
            continue
        try:
            s = load_session(year, rnd, "R", laps=PAST_WINNER_FASTEST_LAP)
            res = pd.DataFrame(s.results)
            win = res[pd.to_numeric(res["Position"], errors="coerce") == 1]
            if win.empty:
                continue
            w = win.iloc[0]
            grid = pd.to_numeric(w["GridPosition"], errors="coerce")
            row = {
                "Year": year,
                "RaceName": s.event["EventName"],
                "Winner": w["FullName"],
                "Constructor": w["TeamName"],
                "Qualifying": grid if grid > 0 else np.nan,  # grid slot
                "FastestLapTime": "",
            }
            if PAST_WINNER_FASTEST_LAP:
                fl = fastest_lap_table(s)
                if not fl.empty:
                    row["FastestLapTime"] = fl.sort_values("FastestLapSeconds").iloc[0]["FastestLapTime"]
            rows.append(row)
            print(f"  {year}: {w['FullName']}")
        except Exception as e:
            print(f"  {year}: could not load ({e})")

    save(pd.DataFrame(rows, columns=[
        "Year", "RaceName", "Winner", "Constructor", "Qualifying", "FastestLapTime"
    ]), "past_winners.csv")


# ============================================================
# 11. TRACK COORDINATES
# ============================================================
# The next race has not happened, so there is no telemetry for it. We use
# the most recent previous running of the same circuit instead.
# X/Y are the circuit's local plotting coordinates (NOT lat/lon).
# Telemetry MUST be loaded (telemetry=True) or X/Y will not exist.

if next_event is not None:
    print("\nBuilding track outline...")
    done = False
    for year in range(SEASON - 1, SEASON - 6, -1):
        if done:
            break
        rnd = find_round(year, next_event["Location"], next_event["EventName"])
        if rnd is None:
            continue
        for ident in ("Q", "R"):
            try:
                s = load_session(year, rnd, ident, laps=True, telemetry=True)
                lap = s.laps.pick_fastest()
                if lap is None:
                    continue
                tel = lap.get_telemetry()
                if "X" not in tel.columns or "Y" not in tel.columns:
                    continue

                track = tel[["X", "Y"]].dropna().reset_index(drop=True)
                track["Point"] = track.index
                track["RaceName"] = next_event["EventName"]
                track["SourceYear"] = year
                save(track, "track_coordinates.csv")

                try:
                    info = s.get_circuit_info()
                    corners = pd.DataFrame(info.corners)
                    corners["Rotation"] = info.rotation
                    corners["RaceName"] = next_event["EventName"]
                    save(corners, "track_corners.csv")
                except Exception as e:
                    print(f"  No corner info: {e}")

                done = True
                break
            except Exception as e:
                print(f"  {year} {ident}: {e}")
    if not done:
        print("  Could not build track outline (no previous running of this circuit?)")


# ============================================================
# 12. PREDICTIONS (fill from your own model)
# ============================================================

prediction_file = OUTPUT_DIR / "predictions.csv"
if not prediction_file.exists():
    pd.DataFrame(columns=[
        "RaceName", "Driver", "PredictionType", "Prediction", "Probability"
    ]).to_csv(prediction_file, index=False)
    print(f"Created empty prediction file: {prediction_file}")


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "=" * 60)
print("F1 DATA PIPELINE COMPLETE")
print("=" * 60)
print(f"\nPower BI files are in: {OUTPUT_DIR.resolve()}\n")
for file in sorted(OUTPUT_DIR.glob("*.csv")):
    try:
        n = len(pd.read_csv(file))
    except pd.errors.EmptyDataError:
        n = 0
    print(f"  {file.name:<45} {n:,} rows")
