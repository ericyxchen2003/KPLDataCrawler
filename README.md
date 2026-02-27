# KPLDataCrawler


This repository implements a lightweight crawler to scrape and download match-related data (in JSON format) from the official website of the Honor of Kings [King Pro League](https://pvp.qq.com/matchdata/index.html) (KPL).

## Installation
```
git clone https://github.com/ericyxchen2003/KPLDataCrawler.git
cd KPLDataCrawler
pip install -r requirements.txt
```

## Usage
```
python download_league_data.py <league_id>
```

## Data
Our tool supports downloading three types of data:
- League data
- Match data
- Battle data

### League data
League data contains the basic information of each match in the league, such as the names of the opposing teams, score, time, match stage, and so on.

For downloading league data, you need to provide the `league_id`:
```
python -m helper.get_league_data <league_id>
```

The `league_id` can be obtained from the URL of the corresponding league information on the official website. For example, the URL of the 2026 KPL Spring Split is `https://pvp.qq.com/matchdata/schedule.html?league_id=20260001`, so the `league_id` is `20260001`.

### Match data
Match data contains the `battle_id` of each battle in this match.

For downloading match data, you need to provide the `match_id`:
```
python -m helper.get_match_data <match_id>
```

The `match_id` can be obtained from the URL of the corresponding match information on the official website. For example, the URL of the match information for the game between Changsha TES.A and Beijing JDG on February 25 of the 2026 KPL Spring Split is `https://pvp.qq.com/matchdata/scheduleDetails.html?league_id=20260001&match_id=2026022502`, so the `match_id` is `2026022502`.

### Battle data
Battle data contains the detailed information of the battle, including each player, the selected heroes, BP information, the MVP player, item builds and so on.

For downloading battle data, you need to provide the `battle_id`:
```
python -m helper.get_battle_data <battle_id>
```

However, we cannot get the `battle_id` from the URL of the corresponding battle information on the official website. Instead, we need to get the `battle_id` from the corresponding match data.

## Download League Data

Our tool allows you to obtain all battle data in a league by providing its `league_id`, and return the data as a list in a single JSON file.

For downloading league data, please provide the `league_id`:
```
python -m download_league_data <league_id>
```

