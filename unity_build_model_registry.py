# pylint: disable=line-too-long, no-else-return
"""
Loads specified Unity asset files that centralize registrations of other asset references under 
their respective model domains or game-mechanics categories. Requires the guid index to be built
first.

The registry is one dictionary consisting of the following:
- META REGISTRY
-- _DOMAIN_LIST : a list of all model domains (or game mechanics categories)
-- _INDEX : a dictionary of all GUIDs and which domains they appear in
- model_registry : the dictionary of all assets, per domain, loaded in from their asset files.

Writes the registry to a file for inspection but also returns it to the caller, so that the caller
does not need to read the file. The file will be in the same folder as this script.
"""
import json
import re
from sys import stdout
from pathlib import Path

from unity_helper_parse_yaml import parse_yaml
from unity_helper_normalize_asset_tree import normalize_asset_tree



ROOT_PATH = Path(__file__).parent
WRITE_MODEL_REGISTRY_PATH = ROOT_PATH / "model_registry.json"

META_KEY = "META_REGISTRY"
META_KEY_DOMAIN_LIST = META_KEY + "_DOMAIN_LIST"
META_KEY_INDEX = META_KEY + "_INDEX"

MODEL_KEY = "model_registry"

GUID_PATTERN = re.compile(r"([0-9a-f]{32})")

TESTING_ITERATION_LIMIT = 1



# region registering metadata for guids

def register_guid(guid: str, domain: str, registry: dict, verbose: bool):
    """Registers a guid under the specified domain."""
    if guid not in registry[META_KEY_INDEX]:
        registry[META_KEY_INDEX][guid] = [domain]
    else:
        if domain not in registry[META_KEY_INDEX][guid]:
            registry[META_KEY_INDEX][guid].append(domain)
    if verbose:
        stdout.write(f"...indexed {guid} under domain {domain}\n")

def register_domain(domain_tree: dict|list|str, domain: str, registry: dict, verbose: bool):
    """Registers a new domain. This stays at the top or second levels of the asset data."""
    if domain not in registry[META_KEY_DOMAIN_LIST]:
        registry[META_KEY_DOMAIN_LIST].append(domain)
        if verbose:
            stdout.write(f"...added new {domain} to registry domain list\n")
    if isinstance(domain_tree, dict):
        for _, value in domain_tree.items():
            if isinstance(value, str) and GUID_PATTERN.fullmatch(value):
                register_guid(value, domain, registry, verbose)
    elif isinstance(domain_tree, list):
        for item in domain_tree:
            if isinstance(item, str) and GUID_PATTERN.fullmatch(item):
                register_guid(item, domain, registry, verbose)
    elif isinstance(domain_tree, str) and GUID_PATTERN.fullmatch(domain_tree):
        register_guid(domain_tree, domain, registry, verbose)

# endregion



# region build model registry from assets

def build_registry_from_asset(registry_asset_path: Path, registry_exclude_fields: list, registry: dict, verbose: bool) -> dict:
    """Builds a new model registry from one asset file."""
    asset_data = parse_yaml(registry_asset_path, verbose)
    for domain_key, raw_value in asset_data.items():
        if domain_key in registry_exclude_fields:
            if verbose:
                stdout.write(f"...dropped field {domain_key}\n")
            continue
        normalized_domain_tree = normalize_asset_tree(raw_value, verbose)
        register_domain(normalized_domain_tree, domain_key, registry, verbose)
        registry[MODEL_KEY][domain_key] = normalized_domain_tree
    return registry

def build_model_registry_from_assets(registry_assets_paths: list, registry_exclude_fields: list, verbose: bool = False, testing: bool = False) -> dict:
    """Builds a new model registry from the provided files."""
    registry = {}
    registry[META_KEY_DOMAIN_LIST] = []
    registry[META_KEY_INDEX] = {}
    registry[MODEL_KEY] = {}
    asset_number = 0
    if verbose:
        stdout.write(f"Building model registry from {len(registry_assets_paths)} assets...\n")
    for registry_asset_path in registry_assets_paths:
        asset_number += 1
        if testing and asset_number > TESTING_ITERATION_LIMIT:
            break
        build_registry_from_asset(registry_asset_path, registry_exclude_fields, registry, verbose)
    stdout.write(f"...finished building model registry from {asset_number} assets.\n")
    return registry

# endregion



#region build model registry from guid index

def build_model_registry_from_guid_index_with_entry(guid_index: dict, index_entry: str, registry: dict, verbose: bool) -> None:
    """Builds a new model registry from one guid index entry."""
    domain = Path(index_entry).name
    guids = []
    for guid, path in guid_index.items():
        if path.startswith(index_entry) and path.endswith(".json"):
            guids.append(guid)
    register_domain(guids, domain, registry, verbose)
    registry[MODEL_KEY][domain] = guids
    if verbose:
        stdout.write(f"...finished adding {domain} to model registry.\n")

def build_model_registry_from_guid_index(guid_index: dict, registry_indices: list, verbose: bool = False, testing: bool = False) -> dict:
    """Builds a new model registry from pipeline registry indices."""
    registry = {}
    registry[META_KEY_DOMAIN_LIST] = []
    registry[META_KEY_INDEX] = {}
    registry[MODEL_KEY] = {}
    domain_number = 0
    if verbose:
        stdout.write(f"Building model registry from {len(registry_indices)} guid index strings...\n")
    for index_entry in registry_indices:
        domain_number += 1
        if testing and domain_number > TESTING_ITERATION_LIMIT:
            stdout.write(f"...testing limit reached, stopping at {domain_number} domains...\n")
            break
        build_model_registry_from_guid_index_with_entry(guid_index, index_entry, registry, verbose)
    stdout.write(f"...finished building model registry from index entries for {domain_number} domains.\n")
    return registry

# endregion



def build_model_registry(guid_index: dict, game_config: dict, verbose: bool = False, testing: bool = False) -> dict:
    """Builds a new model registry from the provided files."""
    registry_mode = game_config["pipeline"]["registry"]["mode"]
    if registry_mode == "guid_index":
        registry_indices = game_config["pipeline"]["registry"]["indices"]
        return build_model_registry_from_guid_index(guid_index, registry_indices, verbose, testing)
    elif registry_mode == "asset":
        registry_assets_paths = [
            ROOT_PATH / asset_path for asset_path in game_config["pipeline"]["registry"]["assets"]
        ]
        registry_exclude = game_config["pipeline"]["registry"]["exclude"]
        return build_model_registry_from_assets(registry_assets_paths, registry_exclude, verbose, testing)
    else:
        raise ValueError(f"Invalid registry mode: {registry_mode}")



if __name__ == "__main__":
    read_default_guid_index_path = ROOT_PATH / "guid_index.json"
    read_default_config_path = ROOT_PATH / "unity_setup_game_config.json"
    with open(read_default_guid_index_path, "r", encoding="utf-8") as guid_index_file:
        main_guid_index = json.load(guid_index_file)
    with open(read_default_config_path, "r", encoding="utf-8") as game_config_file:
        main_config = json.load(game_config_file)
    stdout.write("Building model registry...\n")
    model_registry = build_model_registry(main_guid_index, main_config, verbose=True, testing=False)
    with open(WRITE_MODEL_REGISTRY_PATH, "w", encoding="utf-8") as model_registry_file:
        json.dump(model_registry, model_registry_file, indent=4)
    stdout.write("...done.\n")
