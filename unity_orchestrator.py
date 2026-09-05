# pylint: disable=line-too-long
"""
Orchestrates conversion of AssetRipper extracted project to cargo-query-ready mediawiki data.
"""
import json
from sys import stdout
from pathlib import Path

from unity_assemble_guid_index import assemble_guid_index
from unity_build_model_registry import build_model_registry_from_index, build_model_registry_from_assets
from unity_compile_domain_data import compile_domain_data
from unity_deploy_standardization import deploy_standardization
from unity_extract_cargo_manifest import extract_cargo_manifest
from unity_format_wiki_pages import format_wiki_pages
from unity_go_bot_upload import go_bot_upload



ROOT_PATH = Path(__file__).parent
GAME_CONFIG = ROOT_PATH / "unity_setup_game_config.json"



if __name__ == "__main__":
    stdout.write("Starting Unity game data pipeline\n---\n")
    with open(GAME_CONFIG, "r", encoding="utf-8") as game_config_file:
        game_config_loaded = json.load(game_config_file)
    # A - guid index
    guid_index = assemble_guid_index()
    # B - model registry
    registry_mode = game_config_loaded["pipeline"]["registry"]["mode"]
    if registry_mode == "guid_index":
        registry_indices = game_config_loaded["pipeline"]["registry"]["indices"]
        model_registry = build_model_registry_from_index(registry_indices, guid_index)
    elif registry_mode == "asset":
        registry_assets = [
            ROOT_PATH / asset_path
            for asset_path in game_config_loaded["pipeline"]["registry"]["assets"]
        ]
        model_registry = build_model_registry_from_assets(registry_assets)
    else:
        raise ValueError(f"Invalid registry mode: {registry_mode}")
    # C - domain data
    domain_data = compile_domain_data(model_registry, guid_index)
    # D - standardized data
    standardized = deploy_standardization(domain_data)
    # E - cargo manifest
    cargo_manifest = extract_cargo_manifest(standardized)
    # F - wiki content
    wiki_content = format_wiki_pages(cargo_manifest)
    # G - upload to wiki
    go_bot_upload(wiki_content, verbose=True)
    stdout.write("\n---\nFinished Unity game data pipeline\n")
