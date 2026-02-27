#!/usr/bin/env python3
"""
Download all battle data for a league from 王者荣耀KPL比赛 (King Pro League).

Given a league_id, loads league data (fetching and saving league_data/league_<league_id>.json
from the API if missing), then for each match fetches match data to get battle_ids,
then fetches each battle's data. Writes a single JSON file: a list of battles,
each of the form { "battle_id": ..., "data": { "match_id": ..., ... } }.
"""

import json
import argparse
import sys
from pathlib import Path

from tqdm import tqdm

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


def collect_battle_ids_from_league(league_data_dir: Path, league_id: str) -> list[tuple[str, str]]:
    """
    For each match in the league, fetch match data and collect (match_id, battle_id) for each battle.

    Returns:
        List of (match_id, battle_id) tuples in order.
    """
    matches = load_league_file(league_data_dir, league_id)
    battle_tuples: list[tuple[str, str]] = []

    for match in tqdm(matches, desc="Fetching match data", unit="match"):
        match_id = match.get("match_id")
        if not match_id:
            continue
        match_data = fetch_match_data(match_id, quiet=True)
        if match_data is None:
            tqdm.write(f"Warning: skipped match {match_id} (fetch failed)")
            continue
        results = match_data.get("results")
        if not results:
            continue
        for battle in results:
            bid = battle.get("battle_id")
            if bid:
                battle_tuples.append((match_id, bid))

    return battle_tuples


def download_league_battles(
    league_id: str,
    league_data_dir: Path,
    output_path: Path,
) -> bool:
    """
    Download all battle data for the league and save to a single JSON file.

    Each item in the output list is { "battle_id": ..., "data": { "match_id": ..., ... } }.
    """
    battle_tuples = collect_battle_ids_from_league(league_data_dir, league_id)
    if not battle_tuples:
        print("No battles found for this league.", file=sys.stderr)
        return False

    battles_list: list[dict] = []

    for match_id, battle_id in tqdm(battle_tuples, desc="Downloading battle data", unit="battle"):
        battle_response = fetch_battle_data(battle_id, quiet=True)
        if battle_response is None:
            tqdm.write(f"Warning: skipped battle {battle_id} (fetch failed)")
            continue
        data = battle_response.get("data")
        if data is None:
            tqdm.write(f"Warning: skipped battle {battle_id} (no 'data' in response)")
            continue
        # Add match_id inside data so each battle indicates which match it belongs to
        data_with_match = {**data, "match_id": match_id}
        battles_list.append({
            "battle_id": battle_id,
            "data": data_with_match,
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(battles_list, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(battles_list)} battles to {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Download all battle data for a league (KPL). Reads league JSON, fetches each match's battles, then each battle's data, and writes one combined JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
If league_data/league_<league_id>.json does not exist, it is fetched from the API automatically.

Output is a JSON array; each element is { "battle_id": "...", "data": { "match_id": "...", ... } }.

Examples:
  python download_league_data.py 20250002
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
    args = parser.parse_args()

    league_data_dir = Path(args.league_data_dir)
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = league_data_dir / f"league_{args.league_id}_battles.json"

    try:
        success = download_league_battles(args.league_id, league_data_dir, output_path)
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
