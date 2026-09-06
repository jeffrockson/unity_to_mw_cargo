# pylint: disable=line-too-long
"""
Orchestrates conversion of AssetRipper extracted project to cargo-query-ready mediawiki data.
"""
import json
import argparse
from sys import stdout
from pathlib import Path

from unity_assemble_guid_index import assemble_guid_index
from unity_build_model_registry import build_model_registry
from unity_compile_domain_data import compile_domain_data
from unity_deploy_standardization import deploy_standardization
from unity_extract_cargo_manifest import extract_cargo_manifest
from unity_format_wiki_pages import format_wiki_pages
from unity_go_bot_upload import go_bot_upload



ROOT_PATH = Path(__file__).parent
DEFAULT_GAME_CONFIG = ROOT_PATH / "unity_setup_game_config.json"



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default=DEFAULT_GAME_CONFIG)
    args = parser.parse_args()
    game_config_path = ROOT_PATH / args.config if args.config else DEFAULT_GAME_CONFIG
    stdout.write("Starting Unity game data pipeline\n---\n")
    with open(game_config_path, "r", encoding="utf-8") as game_config_file:
        game_config = json.load(game_config_file)
    # A - guid index
    guid_index = assemble_guid_index(verbose=True)
    # B - model registry
    model_registry = build_model_registry(guid_index, game_config)
    # C - domain data
    domain_data = compile_domain_data(model_registry, guid_index, game_config)
    # D - standardized data
    standardized = deploy_standardization(domain_data)
    # E - cargo manifest
    cargo_manifest = extract_cargo_manifest(standardized, game_config)
    # F - wiki content
    wiki_content = format_wiki_pages(cargo_manifest)
    # G - upload to wiki
    go_bot_upload(wiki_content, verbose=True)
    stdout.write("---\nFinished Unity game data pipeline\n")
