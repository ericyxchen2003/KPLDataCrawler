#!/usr/bin/env python3
"""
Script to download league data from 王者荣耀KPL比赛 (King Pro League)
Fetches JSON data from the league matches API and saves it to a file.
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Optional
import requests


# API endpoint base URL
API_BASE_URL = "https://prod.comp.smoba.qq.com/leaguesite/matches/open"

# Headers to mimic browser request
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": "https://pvp.qq.com",
    "referer": "https://pvp.qq.com/",
    "sec-ch-ua": '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}


def fetch_league_data(league_id: str) -> Optional[dict]:
    """
    Fetch league data from the API.

    Args:
        league_id: The league ID (e.g., "20250002")

    Returns:
        Dictionary containing the league data, or None if request failed
    """
    url = f"{API_BASE_URL}?league_id={league_id}"

    try:
        print(f"Fetching league data for league_id: {league_id}")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        # The API returns text/plain, so we need to parse it as JSON
        data = response.json()

        # Check if the response indicates success
        if data.get("code") == 200:
            print(f"Successfully fetched league data")
            return data
        else:
            print(f"API returned error code: {data.get('code')}, message: {data.get('message')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching league data: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None


def save_league_data(data: dict, output_path: Path, league_id: str) -> bool:
    """
    Save league data to a JSON file.

    Args:
        data: The league data dictionary
        output_path: Directory where to save the file
        league_id: League ID used for filename

    Returns:
        True if saved successfully, False otherwise
    """
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    # Create filename from league_id
    filename = f"league_{league_id}.json"
    filepath = output_path / filename

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"League data saved to: {filepath}")
        return True
    except IOError as e:
        print(f"Error saving file: {e}")
        return False


def main():
    """Main function to handle command-line arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="Download league data from 王者荣耀KPL比赛 (King Pro League)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download a single league
  python helper/get_league_data.py 20250002

  # Download and save to custom directory
  python helper/get_league_data.py 20250002 --output ./data

  # Download and print to stdout instead of saving
  python helper/get_league_data.py 20250002 --print-only
        """
    )

    parser.add_argument(
        "league_id",
        help="League ID (e.g., '20250002')"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default="./league_data",
        help="Output directory for saved JSON files (default: ./league_data)"
    )

    parser.add_argument(
        "-p", "--print-only",
        action="store_true",
        help="Print JSON to stdout instead of saving to file"
    )

    args = parser.parse_args()

    # Fetch league data
    data = fetch_league_data(args.league_id)

    if data is None:
        print("Failed to fetch league data.", file=sys.stderr)
        sys.exit(1)

    # Print or save the data
    if args.print_only:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        output_path = Path(args.output)
        if not save_league_data(data, output_path, args.league_id):
            print("Failed to save league data.", file=sys.stderr)
            sys.exit(1)

    print("Done!")


if __name__ == "__main__":
    main()
