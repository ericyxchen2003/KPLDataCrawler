#!/usr/bin/env python3
"""
Download all battle data for a league from 王者荣耀KPL比赛 (King Pro League).

Given a league_id, loads league data (fetching and saving league_data/league_<league_id>.json
from the API if missing), then for each match fetches match data to get battle_ids,
then fetches each battle's data. Writes a single JSON file of the form:
  { "league_id": ..., "matches": [ { "match_id": ..., "battles": [ { "battle_id": ..., "data": {...} }, ... ] }, ... ] }
Matches are sorted by match_id ascending; battles within each match by battle_id ascending.
"""

import json
import argparse
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm


def _id_sort_key(id_val: str) -> tuple[int, int | str]:
    """Sort key: try numeric first for ascending order, else string."""
    if not id_val:
        return (0, 0)
    try:
        return (0, int(id_val))
    except (ValueError, TypeError):
        return (1, (id_val or "").lower())


# Import fetch functions from helper scripts
from helper.get_match_data import fetch_match_data
from helper.get_battle_data import fetch_battle_data
from helper.get_league_data import fetch_league_data, save_league_data


def load_league_file(league_data_dir: Path, league_id: str) -> list:
    """
    Load league JSON from league_data/league_<league_id>.json and return the list of matches.
    If the file does not exist, fetches league data from the API and saves it first.

    Args:
        league_data_dir: Directory containing league JSON files.
        league_id: League ID.

    Returns:
        List of match dicts (the "results" array).

    Raises:
        FileNotFoundError: If the league file is missing and fetch failed.
        ValueError: If the data has no "results" key.
    """
    league_path = league_data_dir / f"league_{league_id}.json"
    if league_path.exists():
        with open(league_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        print(f"League file not found at {league_path}; fetching from API...")
        data = fetch_league_data(league_id)
        if data is None:
            raise FileNotFoundError(
                f"Could not fetch league data for league_id={league_id}. "
                "Check the ID and network and try again."
            )
        save_league_data(data, league_data_dir, league_id)

    results = data.get("results")
    if results is None:
        raise ValueError(f"No 'results' key in league data for {league_id}")

    return results


def _fetch_match_battle_ids(match: dict) -> tuple[str | None, list[str]]:
    """Fetch match data and return (match_id, list of battle_ids). Returns (None, []) on failure."""
    match_id = match.get("match_id")
    if not match_id:
        return (None, [])
    match_data = fetch_match_data(match_id, quiet=True)
    if match_data is None:
        return (match_id, [])  # signal failure but keep match_id for warning
    results = match_data.get("results") or []
    battle_ids = [b["battle_id"] for b in results if b.get("battle_id")]
    return (match_id, battle_ids)


def collect_battle_ids_from_league(
    league_data_dir: Path, league_id: str, workers: int = 1
) -> list[tuple[str, str]]:
    """
    For each match in the league, fetch match data and collect (match_id, battle_id) for each battle.

    If workers > 1, match fetches run concurrently.

    Returns:
        List of (match_id, battle_id) tuples.
    """
    matches = load_league_file(league_data_dir, league_id)
    battle_tuples: list[tuple[str, str]] = []

    if workers <= 1:
        for match in tqdm(matches, desc="Fetching match data", unit="match"):
            match_id, battle_ids = _fetch_match_battle_ids(match)
            if match_id is None:
                continue
            if not battle_ids:
                tqdm.write(f"Warning: skipped match {match_id} (fetch failed or no battles)")
                continue
            for bid in battle_ids:
                battle_tuples.append((match_id, bid))
        return battle_tuples

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_match = {executor.submit(_fetch_match_battle_ids, m): m for m in matches}
        with tqdm(total=len(matches), desc="Fetching match data", unit="match") as pbar:
            for future in as_completed(future_to_match):
                match_id, battle_ids = future.result()
                if match_id is None:
                    pbar.update(1)
                    continue
                if not battle_ids:
                    tqdm.write(f"Warning: skipped match {match_id} (fetch failed or no battles)")
                    pbar.update(1)
                    continue
                for bid in battle_ids:
                    battle_tuples.append((match_id, bid))
                pbar.update(1)

    return battle_tuples


def _fetch_one_battle(
    match_id: str, battle_id: str, max_retries: int = 5
) -> tuple[str, str, dict | None]:
    """Fetch one battle with up to max_retries attempts; return (match_id, battle_id, data or None)."""
    for attempt in range(max_retries):
        resp = fetch_battle_data(battle_id, quiet=True)
        if resp is not None:
            data = resp.get("data")
            if data is not None:
                return (match_id, battle_id, data)
        if attempt < max_retries - 1:
            time.sleep(1)  # brief delay before retry
    return (match_id, battle_id, None)


def download_league_battles(
    league_id: str,
    league_data_dir: Path,
    output_path: Path,
    workers: int = 1,
    max_retries: int = 5,
) -> bool:
    """
    Download all battle data for the league and save to a single JSON file.

    Output format: { "league_id": ..., "matches": [ { "match_id": ..., "battles": [...] }, ... ] }.
    Matches sorted by match_id ascending; battles by battle_id ascending.
    If workers > 1, battle fetches run concurrently. Failed battle fetches are retried up to max_retries times.
    """
    battle_tuples = collect_battle_ids_from_league(league_data_dir, league_id, workers=workers)
    if not battle_tuples:
        print("No battles found for this league.", file=sys.stderr)
        return False

    # Group (match_id, battle_id) by match_id, then sort battle_ids per match
    match_to_battles: dict[str, list[str]] = defaultdict(list)
    for match_id, battle_id in battle_tuples:
        match_to_battles[match_id].append(battle_id)
    for battle_ids in match_to_battles.values():
        battle_ids.sort(key=_id_sort_key)

    # Sort match_ids ascending
    sorted_match_ids = sorted(match_to_battles.keys(), key=_id_sort_key)

    # Fetch all battles (concurrently if workers > 1)
    match_to_battle_data: dict[str, list[tuple[str, dict]]] = defaultdict(list)

    def fetch_with_retries(mid: str, bid: str) -> tuple[str, str, dict | None]:
        return _fetch_one_battle(mid, bid, max_retries=max_retries)

    if workers <= 1:
        for match_id in tqdm(sorted_match_ids, desc="Downloading battles", unit="match"):
            for battle_id in match_to_battles[match_id]:
                _, _, data = fetch_with_retries(match_id, battle_id)
                if data is not None:
                    match_to_battle_data[match_id].append((battle_id, data))
                else:
                    tqdm.write(f"Warning: skipped battle {battle_id} after {max_retries} attempts")
    else:
        total = sum(len(match_to_battles[m]) for m in sorted_match_ids)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(fetch_with_retries, m, b): (m, b)
                for m in sorted_match_ids
                for b in match_to_battles[m]
            }
            with tqdm(total=total, desc="Downloading battles", unit="battle") as pbar:
                for future in as_completed(futures):
                    match_id, battle_id, data = future.result()
                    if data is not None:
                        match_to_battle_data[match_id].append((battle_id, data))
                    else:
                        tqdm.write(f"Warning: skipped battle {battle_id} after {max_retries} attempts")
                    pbar.update(1)

    # Build output: sort battles by battle_id within each match
    matches_list: list[dict] = []
    total_battles = 0
    for match_id in sorted_match_ids:
        pairs = match_to_battle_data.get(match_id, [])
        pairs.sort(key=lambda p: _id_sort_key(p[0]))
        battles_for_match = [{"battle_id": bid, "data": d} for bid, d in pairs]
        if battles_for_match:
            matches_list.append({"match_id": match_id, "battles": battles_for_match})
            total_battles += len(battles_for_match)

    output = {
        "league_id": league_id,
        "matches": matches_list,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(matches_list)} matches, {total_battles} battles to {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download all battle data for a league (KPL). Reads league JSON, fetches each match's battles, then each battle's data, and writes one combined JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
If league_data/league_<league_id>.json does not exist, it is fetched from the API automatically.

Output is a JSON object: { "league_id": "...", "matches": [ { "match_id": "...", "battles": [...] }, ... ] }. Matches and battles are sorted by ID ascending.

Examples:
  python download_league_data.py 20250002
  python download_league_data.py 20250002 -j 20
  python download_league_data.py 20250002 -o ./league_data/league_20250002_battles.json
        """,
    )
    parser.add_argument("league_id", help="League ID (e.g. 20250002)")
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output JSON path (default: league_data/league_<league_id>_battles.json)",
    )
    parser.add_argument(
        "--league-data-dir",
        type=str,
        default="./league_data",
        help="Directory containing league_<league_id>.json (default: ./league_data)",
    )
    parser.add_argument(
        "-j", "--workers",
        type=int,
        default=16,
        metavar="N",
        help="Number of concurrent requests for match and battle fetches (default: 16). Use 1 for sequential.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        metavar="N",
        help="Max retries per battle when fetch fails or returns no data (default: 5).",
    )
    args = parser.parse_args()

    workers = max(1, args.workers)
    max_retries = max(1, args.max_retries)
    league_data_dir = Path(args.league_data_dir)
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = league_data_dir / f"league_{args.league_id}_battles.json"

    try:
        success = download_league_battles(
            args.league_id, league_data_dir, output_path,
            workers=workers, max_retries=max_retries,
        )
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if not success:
        sys.exit(1)
    print("Done!")


if __name__ == "__main__":
    main()
