# pylint: disable=
"""
This script is used to build a GUID index from Unity game assets.

Assumes the Assets directory is located in the same directory as this script. If they aren't,
update the configuration constant.

Writes the index to a file for inspection but also returns it to the caller, so that the caller
does not need to read the file. The file will be in the same folder as this script.
"""
from sys import stdout
import json
import re
from pathlib import Path



ROOT_PATH = Path(__file__).parent
READ_ASSETS_PATH = ROOT_PATH / "Assets"
WRITE_INDEX_PATH = ROOT_PATH / "guid_index.json"

GUID_DEFINITION_PATTERN = re.compile(r"guid: ([0-9a-f]{32})")

TESTING_ITERATION_LIMIT = 20



def read_asset_file(asset_path: Path, guid_index: dict, verbose: bool):
    """Read an asset and add any GUID found to the guid_index."""
    asset_file = asset_path.read_text(encoding="utf-8")
    line_number = 0
    for line in asset_file.splitlines():
        line_number += 1
        line_match = GUID_DEFINITION_PATTERN.match(line)
        if line_match:
            guid = line_match.group(1)
            asset_path_to_save = asset_path.with_suffix("") # changes .asset.meta to .asset
            guid_index[guid] = str(asset_path_to_save.relative_to(ROOT_PATH))
            if verbose:
                stdout.write(f"...found GUID {guid} in {asset_path_to_save}\n")
            break # only one guid per .asset.meta file



def assemble_guid_index(verbose: bool = False, testing: bool = False) -> dict:
    """Build a new GUID index from Unity game assets."""
    guid_index = {}
    file_number = 0
    if verbose:
        stdout.write(f"Building GUID index from {READ_ASSETS_PATH}...\n")
    for asset_path in READ_ASSETS_PATH.rglob("*.meta"):
        file_number += 1
        if testing and file_number > 20:
            break
        if verbose and file_number % 2000 == 0:
            stdout.write(f"...processed {file_number} files...\n")
        read_asset_file(asset_path, guid_index, verbose)
    with open(WRITE_INDEX_PATH, "w", encoding="utf-8") as file:
        json.dump(guid_index, file, indent=2)
    stdout.write(f"...finished building GUID index over {file_number} total files.\n")
    return guid_index



if __name__ == "__main__":
    assemble_guid_index(verbose=False, testing=False)
