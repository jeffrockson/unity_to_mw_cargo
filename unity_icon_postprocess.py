# pylint: disable=line-too-long, too-many-arguments, too-many-positional-arguments
"""
Post-processes IconAddress (and related) fields from domain_data.json into cropped PNGs.

Standalone add-on: does not modify orchestrator outputs. Requires guid_index.json and
domain_data.json on disk under ROOT_PATH.
"""
import json
import argparse
from pathlib import Path
from sys import stdout
from math import floor, ceil
from PIL import Image
from unity_helper_parse_yaml import parse_yaml



ROOT_PATH = Path(__file__).parent
READ_DEFAULT_GAME_CONFIG = ROOT_PATH / "unity_setup_game_config.json"
READ_GUID_INDEX_PATH = ROOT_PATH / "guid_index.json"
READ_DOMAIN_DATA_PATH = ROOT_PATH / "domain_data.json"
WRITE_ICONS_DIR = ROOT_PATH / "icons_out"
WRITE_ICON_MANIFEST_PATH = ROOT_PATH / "icon_manifest.json"

DOMAIN_DATA_KEY = "domains_data"

CONFIG_ICONS = "icon_postprocess"
CONFIG_OUTPUT = "output_dir"
CONFIG_Y_FLIP = "y_flip"

CONFIG_DERIVE_ICONS = "derive_icons"
CONFIG_ICON_FIELDS = "icon_fields"
CONFIG_SPRITE_SEARCH_FOLDERS = "search_folders"

CONFIG_ADD_ICONS = "add_icons"
CONFIG_FOLDER = "folder"
CONFIG_PREFIX = "prefix"

MANIFEST_ASSETS = "assets"
MANIFEST_TEXTURES = "textures"

MANIFEST_TEXTURE_DATA = "m_RD"
MANIFEST_TEX = "texture"
MANIFEST_GUID = "guid"
MANIFEST_RECT = "textureRect"

ICON_TEX = "texture"
ICON_X = "x"
ICON_Y = "y"
ICON_WIDTH = "width"
ICON_HEIGHT = "height"

TESTING_ITERATION_LIMIT = 10



def crop_and_save_from_atlas(y_flip: bool, icon_name: str, asset_data: dict, atlas: Image.Image, verbose: bool) -> None:
    """Crop and save one icon from the given atlas."""
    x = floor(asset_data[ICON_X])
    y = asset_data[ICON_Y]
    width = ceil(asset_data[ICON_WIDTH])
    height = ceil(asset_data[ICON_HEIGHT])
    if y_flip:
        y = floor(atlas.height - y - height)
    else:
        y = floor(y)
    icon = atlas.crop((x, y, x + width, y + height))
    if verbose:
        stdout.write(f"Cropped icon: {icon_name} with size {width}x{height}\n")
    icon.save(Path(WRITE_ICONS_DIR / f"{icon_name}.png"))

def extract_icons_from_atlas(manifest_assets: dict, icons_config: dict, guid: str, atlas: Image.Image, verbose: bool, testing: bool) -> None:
    """Crop and save icons from the given atlas."""
    y_flip = icons_config.get(CONFIG_Y_FLIP, False)
    icon_number = 0
    for asset_name, asset_data in manifest_assets.items():
        icon_number += 1
        if testing and icon_number > TESTING_ITERATION_LIMIT:
            break
        if asset_data[ICON_TEX] != guid:
            continue
        crop_and_save_from_atlas(y_flip, asset_name, asset_data, atlas, verbose)

def load_atlas(folder: str) -> Image.Image|None:
    """Load an atlas image or sprite sheet from the given folder and filename."""
    path = Path(ROOT_PATH / folder)
    if not path.exists():
        return None
    return Image.open(path).convert("RGBA")

def load_and_crop_textures(manifest: dict, icons_config: dict, verbose: bool, testing: bool) -> None:
    """Load and crop textures for all icons in the manifest."""
    WRITE_ICONS_DIR.mkdir(exist_ok=True)
    manifest_assets = manifest[MANIFEST_ASSETS]
    manifest_textures = manifest[MANIFEST_TEXTURES]
    for guid, folder in manifest_textures.items():
        atlas = load_atlas(folder)
        if not atlas:
            continue
        extract_icons_from_atlas(manifest_assets, icons_config, guid, atlas, verbose, testing)



def resolve_texture_paths(guid_index: dict, manifest: dict, verbose: bool) -> None:
    """Preload all textures referenced in the manifest."""
    manifest_assets = manifest[MANIFEST_ASSETS]
    manifest_textures = manifest[MANIFEST_TEXTURES]
    for asset_key in manifest_assets.keys():
        texture_guid = manifest_assets[asset_key][ICON_TEX]
        texture_location = guid_index[texture_guid]
        texture_path = Path(ROOT_PATH / texture_location)
        if not texture_path.exists():
            continue
        if texture_guid in manifest_textures:
            continue
        manifest_textures[texture_guid] = texture_location
        if verbose:
            stdout.write(f"Preloaded texture: {texture_guid} (first required by {asset_key})\n")



def cull_icon_asset_data(asset_data: dict) -> dict:
    """Cull icon asset data to only the necessary fields."""
    inner_asset_data = asset_data[MANIFEST_TEXTURE_DATA]
    texture = inner_asset_data[MANIFEST_TEX]
    rect = inner_asset_data[MANIFEST_RECT]
    return {
        ICON_TEX: texture[MANIFEST_GUID],
        ICON_X: rect[ICON_X],
        ICON_Y: rect[ICON_Y],
        ICON_WIDTH: rect[ICON_WIDTH],
        ICON_HEIGHT: rect[ICON_HEIGHT]
    }

def load_icon_asset(manifest_assets: dict, icon_key: str, folder: str, verbose: bool) -> None:
    """Parse a Unity Sprite .asset YAML file. Returns dict with texture_guid, x, y, width, height (m_Rect)."""
    folder_path = Path(ROOT_PATH / folder)
    asset_path = folder_path / f"{icon_key}.asset"
    if not asset_path.exists():
        return
    asset_data = parse_yaml(asset_path)
    manifest_assets[icon_key] = cull_icon_asset_data(asset_data)
    if verbose:
        stdout.write(f"Loaded icon asset: {icon_key}\n")

def compile_icon_assets(manifest_assets: dict, icon_config: dict, verbose: bool) -> None:
    """Compile icon asset data for all icons in manifest."""
    derive_config = icon_config.get(CONFIG_DERIVE_ICONS)
    if not derive_config:
        return
    search_folders = derive_config.get(CONFIG_SPRITE_SEARCH_FOLDERS, [])
    if len(search_folders) == 0:
        return
    for icon_key in list(manifest_assets.keys()):
        for folder in search_folders:
            load_icon_asset(manifest_assets, icon_key, folder, verbose)
        if manifest_assets[icon_key] == {}:
            del manifest_assets[icon_key]



def add_icons_by_config(manifest_assets: dict, icons_config: dict, verbose: bool) -> None:
    """Add any icons explicitly defined in the config."""
    add_config = icons_config.get(CONFIG_ADD_ICONS)
    if not add_config:
        return
    for rule in add_config:
        folder = rule[CONFIG_FOLDER]
        prefix = rule[CONFIG_PREFIX]
        folder_path = Path(ROOT_PATH / folder)
        for asset_path in folder_path.glob(f"{prefix}*.asset"):
            manifest_assets[asset_path.stem] = {}
            if verbose:
                stdout.write(f"Adding icon: {asset_path.stem}\n")



def collect_referenced_icon_addresses(domain_data: dict, manifest_assets: dict, icons_config: dict, verbose: bool = False) -> None:
    """Walk domain_data and collect all icon addresses from each record."""
    derive_config = icons_config.get(CONFIG_DERIVE_ICONS)
    if not derive_config:
        return
    icon_fields = derive_config.get(CONFIG_ICON_FIELDS, [])
    if len(icon_fields) == 0:
        return
    for domain_name, domain in domain_data.items():
        for guid, record in domain.items():
            for key, value in record.items():
                if key in icon_fields:
                    if not value or value == "" or isinstance(value, list):
                        if verbose:
                            stdout.write(f"Skipping invalid value for key {key}: '{value}' from {domain_name}/{guid}\n")
                        continue
                    if value in manifest_assets:
                        continue
                    manifest_assets[value] = {}
                    if verbose:
                        stdout.write(f"Added icon: {value}\n")
    if verbose:
        stdout.write(f"Collected {len(manifest_assets)} icon addresses\n")



def icon_postprocess(guid_index: dict, domain_data: dict, icons_config: dict, verbose: bool = False, testing: bool = False) -> dict:
    """Orchestrate load, collect, crop, and manifest write. Returns exit code."""
    manifest = {
        MANIFEST_ASSETS: {},
        MANIFEST_TEXTURES: {}
    }
    collect_referenced_icon_addresses(domain_data[DOMAIN_DATA_KEY], manifest[MANIFEST_ASSETS], icons_config, verbose=False)
    add_icons_by_config(manifest[MANIFEST_ASSETS], icons_config, verbose=False)
    compile_icon_assets(manifest[MANIFEST_ASSETS], icons_config, verbose)
    resolve_texture_paths(guid_index, manifest, verbose=False)
    load_and_crop_textures(manifest, icons_config, verbose, testing)
    return manifest



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", default=READ_DEFAULT_GAME_CONFIG)
    args = parser.parse_args()
    game_config_path = ROOT_PATH / args.config if args.config else READ_DEFAULT_GAME_CONFIG
    stdout.write("Starting icon atlas postprocessing\n---\n")
    with open(game_config_path, "r", encoding="utf-8") as game_config_file:
        main_game_config = json.load(game_config_file)
        main_icons_config = main_game_config[CONFIG_ICONS]
    with open(READ_GUID_INDEX_PATH, "r", encoding="utf-8") as guid_index_file:
        main_guid_index = json.load(guid_index_file)
    with open(READ_DOMAIN_DATA_PATH, "r", encoding="utf-8") as domain_data_file:
        main_domain_data = json.load(domain_data_file)
    icons_manifest = icon_postprocess(main_guid_index, main_domain_data, main_icons_config, verbose=True, testing=False)
    # dump manifest to file
    with open(WRITE_ICON_MANIFEST_PATH, "w", encoding="utf-8") as manifest_file:
        json.dump(icons_manifest, manifest_file, indent=4)
    stdout.write("---\nFinished icon atlas postprocessing\n")
