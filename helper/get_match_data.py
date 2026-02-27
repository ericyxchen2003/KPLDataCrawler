#!/usr/bin/env python3
"""
Script to download match data from 王者荣耀KPL比赛 (King Pro League)
Fetches JSON data from the match API and saves it to a file.
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Optional
import requests


# API endpoint base URL
API_BASE_URL = "https://prod.comp.smoba.qq.com/leaguesite/match/battles/open"

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


def fetch_match_data(match_id: str, *, quiet: bool = False) -> Optional[dict]:
    """
    Fetch match data from the API.

    Args:
        match_id: The match ID (e.g., "2025060501")
        quiet: If True, suppress progress prints (e.g. when used with tqdm).

    Returns:
        Dictionary containing the match data, or None if request failed
    """
    url = f"{API_BASE_URL}?match_id={match_id}"

    try:
        if not quiet:
            print(f"Fetching match data for match_id: {match_id}")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        # The API returns text/plain, so we need to parse it as JSON
        data = response.json()

        # Check if the response indicates success
        if data.get("code") == 200:
            if not quiet:
                print(f"Successfully fetched match data")
            return data
        else:
            if not quiet:
                print(f"API returned error code: {data.get('code')}, message: {data.get('message')}")
            return None

    except requests.exceptions.RequestException as e:
        if not quiet:
            print(f"Error fetching match data: {e}")
        return None
    except json.JSONDecodeError as e:
        if not quiet:
            print(f"Error parsing JSON response: {e}")
        return None


def save_match_data(data: dict, output_path: Path, match_id: str) -> bool:
    """
    Save match data to a JSON file.

    Args:
        data: The match data dictionary
        output_path: Directory where to save the file
        match_id: Match ID used for filename

    Returns:
        True if saved successfully, False otherwise
    """
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    # Create filename from match_id
    filename = f"match_{match_id}.json"
    filepath = output_path / filename

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Match data saved to: {filepath}")
        return True
    except IOError as e:
        print(f"Error saving file: {e}")
        return False


def main():
    """Main function to handle command-line arguments and execute the script."""
    parser = argparse.ArgumentParser(
        description="Download match data from 王者荣耀KPL比赛 (King Pro League)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download a single match
  python helper/get_match_data.py 2025060501

  # Download and save to custom directory
  python helper/get_match_data.py 2025060501 --output ./data

  # Download and print to stdout instead of saving
  python helper/get_match_data.py 2025060501 --print-only
        """
    )

    parser.add_argument(
        "match_id",
        help="Match ID (e.g., '2025060501')"
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default="./match_data",
        help="Output directory for saved JSON files (default: ./match_data)"
    )

    parser.add_argument(
        "-p", "--print-only",
        action="store_true",
        help="Print JSON to stdout instead of saving to file"
    )

    args = parser.parse_args()

    # Fetch match data
    data = fetch_match_data(args.match_id)

    if data is None:
        print("Failed to fetch match data.", file=sys.stderr)
        sys.exit(1)

    # Print or save the data
    if args.print_only:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        output_path = Path(args.output)
        if not save_match_data(data, output_path, args.match_id):
            print("Failed to save match data.", file=sys.stderr)
            sys.exit(1)

    print("Done!")


if __name__ == "__main__":
    main()
