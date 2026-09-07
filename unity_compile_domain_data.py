# pylint: disable=line-too-long, no-else-return, no-else-continue, too-many-arguments, too-many-locals, too-many-positional-arguments, too-many-return-statements, simplifiable-if-statement

"""
Gathers domain data for all domains from asset files in the model registry and the guid index.
"""
import json
import re
from re import Pattern
from sys import stdout
from pathlib import Path

from unity_helper_parse_yaml import parse_yaml
from unity_helper_normalize_asset_tree import normalize_asset_tree
from unity_helper_merge_config import merge_config



ROOT_PATH = Path(__file__).parent
WRITE_DOMAIN_DATA_PATH = ROOT_PATH / "domain_data.json"

META_KEY_PREFIX = "META_DOMAIN_"
META_KEY_FIELDS = META_KEY_PREFIX + "FIELDS"
META_KEY_GUID_REF_INDEX = META_KEY_PREFIX + "REF_INDEX"

META_FIELDS = "META_FIELDS"
META_ITEMS = "META_ITEMS"
META_TYPES = "META_TYPES"

META_TYPE_NULL = "null"
META_TYPE_BOOL = "Boolean"
META_TYPE_INT = "Integer"
META_TYPE_FLOAT = "Float"
META_TYPE_STRING = "Text"
META_TYPE_GUID = "String"
META_TYPE_GUID_LIST = "List of String"
META_TYPE_LIST = "inspect list"
META_TYPE_DICT = "inspect dict"
META_TYPE_UNKNOWN = "must inspect"

MODEL_KEY = "model_registry"

DATA_KEY = "domains_data"

CONFIG_DOMAIN_NAME_KEY = "_domain_name"
CONFIG_STRINGS_KEY = "strings"
L10N_SUFFIX_KEY = "key_suffix"

CONFIG_EXCLUDE_KEY = "exclude"
CONFIG_EXPAND_KEY = "expand"
CONFIG_SEPARATE_KEY = "separate"
SEPARATE_GUID_PREFIX = "guid_prefix"
SEPARATE_DOMAIN = "domain"
CONFIG_DEDUPE_KEY= "deduplication"
DEDUPE_KEEP = "keep"
DEDUPE_REMOVE = "remove"
DEDUPE_DOMAIN = "domain"
DEDUPE_KEY = "key"

REF_TYPE_KEY = "ref_type"
REF_TYPE_GUID = "guid"
REF_TYPE_NAME = "name"
GUID_PATTERN = re.compile(r"([0-9a-f]{32})")
UNIQUE_NAME_PATTERN = re.compile(r"(?:m_Name|Name)")

L10N_DEFAULT_KEY = "key"
L10N_ENGLISH_KEY_SUFFIX = "_en"

TESTING_ITERATION_LIMIT = 15



#region references metadata

def register_references_in_list(node_key: str, node: list, references: dict, ref_pattern: Pattern) -> dict:
    """Registers all guid references in the list."""
    for item in node:
        if isinstance(item, str) and ref_pattern.fullmatch(item):
            if item not in references:
                references[item] = []
            if node_key not in references[item]:
                references[item].append(node_key)
        elif isinstance(item, dict):
            register_references_in_dict(item, references, ref_pattern)
    return references

def register_references_in_dict(node: dict, references: dict, ref_pattern: Pattern) -> dict:
    """Registers all guid references in the node."""
    for key, value in node.items():
        if isinstance(value, str) and ref_pattern.fullmatch(value):
            if value not in references:
                references[value] = []
            if key not in references[value]:
                references[value].append(key)
        elif isinstance(value, dict):
            register_references_in_dict(value, references, ref_pattern)
        elif isinstance(value, list):
            register_references_in_list(key, value, references, ref_pattern)
    return references

def register_references(model_data: dict, ref_pattern: Pattern) -> dict:
    """Registers all guid references in the model data against the key they're found in."""
    references = {}
    for _, domain_data in model_data.items():
        if not isinstance(domain_data, dict):
            continue
        for _, guid_data in domain_data.items():
            if not isinstance(guid_data, dict):
                continue
            register_references_in_dict(guid_data, references, ref_pattern)
    return references

#endregion



#region types metadata

def classify_field_type(key: str, value: object) -> str:
    """Classifies the field type based on the python type of the value."""
    if value is None:
        return META_TYPE_NULL
    if isinstance(value, bool):
        return META_TYPE_BOOL
    if isinstance(value, float):
        return META_TYPE_FLOAT
    if isinstance(value, int):
        return META_TYPE_INT
    if isinstance(value, str):
        if GUID_PATTERN.fullmatch(value) or UNIQUE_NAME_PATTERN.fullmatch(key):
            return META_TYPE_GUID
        else:
            return META_TYPE_STRING
    if isinstance(value, list):
        if value and all(isinstance(item, str) and GUID_PATTERN.fullmatch(item) for item in value):
            return META_TYPE_GUID_LIST
        return META_TYPE_LIST
    if isinstance(value, dict):
        return META_TYPE_DICT
    return META_TYPE_UNKNOWN

def finalize_fields_schema_for_node(schema_node: dict) -> None:
    """Finishes the schema by reducing types and converting sets to lists."""
    if META_TYPES in schema_node:
        types = schema_node[META_TYPES]
        if META_TYPE_INT in types and META_TYPE_FLOAT in types:
            types.discard(META_TYPE_INT)
        if META_TYPE_NULL in types and len(types) > 1:
            types.discard(META_TYPE_NULL)
        if META_TYPE_INT in types and META_TYPE_STRING in types:
            types.discard(META_TYPE_INT)
        if META_TYPE_GUID in types and META_TYPE_STRING in types:
            types.discard(META_TYPE_GUID)
        if types:
            schema_node[META_TYPES] = sorted(types)
        else:
            del schema_node[META_TYPES]
    if META_FIELDS in schema_node:
        for child in schema_node[META_FIELDS].values():
            finalize_fields_schema_for_node(child)
    if META_ITEMS in schema_node:
        finalize_fields_schema_for_node(schema_node[META_ITEMS])

def finalize_fields_schema(schema: dict) -> None:
    """Finishes the schema."""
    for node in schema.values():
        finalize_fields_schema_for_node(node)

def register_domain_fields_in_value(key: str, value: object, schema_node: dict) -> None:
    """Classify value, merge type on this node, recurse into dict/list children."""
    field_type = classify_field_type(key, value)
    if field_type not in (META_TYPE_DICT, META_TYPE_LIST):
        schema_node.setdefault(META_TYPES, set()).add(field_type)
    if isinstance(value, dict):
        register_domain_fields_in_dict(value, schema_node.setdefault(META_FIELDS, {}))
    elif isinstance(value, list):
        register_domain_fields_in_list(key, value, schema_node)

def register_domain_fields_in_dict(node: dict, schema_node: dict) -> None:
    """Merges each key into schema in one dict node."""
    for key, value in node.items():
        child = schema_node.setdefault(key, {})
        register_domain_fields_in_value(key, value, child)

def register_domain_fields_in_list(key: str, node: list, schema_node: dict) -> None:
    """Merges each item into schema in one list node."""
    items_schema = schema_node.setdefault(META_ITEMS, {})
    for item in node:
        register_domain_fields_in_value(key, item, items_schema)

def register_domain_fields(model_data: dict) -> dict:
    """Registers every seen field and its seen types once per domain."""
    fields = {}
    for _, row in model_data.items():
        if not isinstance(row, dict):
            continue # should all be dicts tho
        register_domain_fields_in_dict(row, fields)
    finalize_fields_schema(fields)
    return fields

#endregion



#region exclude

def filter_node_by_domain_exclude_list(node: object, exclude_list: list) -> None:
    """Filters dict nodes by the exclude keys."""
    if isinstance(node, dict):
        for key in exclude_list:
            if key in node:
                del node[key]

#endregion


#region expand/strings

def is_localizable_field(key: str, value: any, domain_config: dict) -> bool:
    """Checks if the node has string keys."""
    key_suffix = domain_config["strings"].get(L10N_SUFFIX_KEY, L10N_DEFAULT_KEY)
    if isinstance(value, str) and key.endswith(key_suffix):
        return True
    else:
        return False

def calc_string_lookup(field_key: str, field_value: str, domain_config: dict) -> str|None:
    """Build an I2 lookup path from a *Term field and its value.
    ("DescriptionTerm", "Apartment")
        -> "Description/Apartment"
    ("ProgressTerm", "Building/SpaceshipBuilder/Task/Launch")
        -> "Building/SpaceshipBuilder/Task/Launch" """
    if "/" in field_value:
        return field_value
    key_suffix = domain_config["strings"].get(L10N_SUFFIX_KEY, L10N_DEFAULT_KEY)
    if field_key == key_suffix:
        return field_value
    stem = field_key[: -len(key_suffix)]
    return f"{stem}/{field_value}"

def lookup_en_string(lookup_key: str, en_strings: dict) -> str|None:
    """Looks up an english string from a lookup key."""
    if lookup_key in en_strings:
        return en_strings[lookup_key]
    for key, entry in en_strings.items():
        if key.endswith(lookup_key):
            return entry
    return None

def insert_value_after_field(record: dict, after_key: str, new_key: str, new_value: str) -> None:
    """Inserts a value after a field in a record."""
    reordered = {}
    for key, value in record.items():
        reordered[key] = value
        if key == after_key:
            reordered[new_key] = new_value
    record.clear()
    record.update(reordered)

def add_any_l10n_strings_to_node(node: dict, field_name: str, domain_config: dict, en_strings: dict, verbose: bool) -> None:
    """Expands a string field with its english localization string and adds it to the record."""
    value = node[field_name]
    new_key = calc_string_lookup(field_name, value, domain_config)
    found = lookup_en_string(new_key, en_strings)
    if found:
        insert_value_after_field(node, field_name, field_name + L10N_ENGLISH_KEY_SUFFIX, found)
        if verbose:
            stdout.write(f"...expanded string key {field_name} to {found}...\n")

def expand_strings_in_node(node: object, domain_config: dict, en_strings: dict, verbose: bool) -> None:
    """Expands all string keys in a dict with their english strings."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if is_localizable_field(key, value, domain_config):
                add_any_l10n_strings_to_node(node, key, domain_config, en_strings, verbose)

#endregion



#region expand/sub-include

def select_asset_data_from_dict(final_node: dict, current_node: dict, include_list: list):
    """Recursively selects the fields from include_list but flattens them to final_node."""
    if isinstance(current_node, dict):
        for key, value in current_node.items():
            if key in include_list:
                if value is not None:
                    final_node[key] = value
            elif isinstance(value, dict):
                select_asset_data_from_dict(final_node, value, include_list)
            elif isinstance(value, list):
                for item in value:
                    select_asset_data_from_dict(final_node, item, include_list)

def select_asset_data(asset_data: dict, include_list: list) -> dict:
    """Selects only the included keys."""
    new_asset_data = {}
    select_asset_data_from_dict(new_asset_data, asset_data, include_list)
    return new_asset_data

#endregion



#region expand/references

def replace_selected_guid(selected_key: str, guid: str, guid_index: dict, domain_config: dict, verbose: bool) -> dict:
    """Replaces a guid inside a selected field with its asset data."""
    if verbose:
        stdout.write(f"...expanding guid {guid} under selected key {selected_key}...\n")
    if guid not in guid_index:
        stdout.write(f"...WARNING: guid {guid} not found in guid index...\n")
        return guid
    inner_asset_path = Path(guid_index[guid])
    inner_asset_data = normalize_asset_tree(load_file(inner_asset_path, verbose=False), verbose=False)
    include_list = domain_config[CONFIG_EXPAND_KEY][selected_key]
    selected_asset_data = select_asset_data(inner_asset_data, include_list)
    if verbose:
        stdout.write(f"...expanded guid {guid} with {len(selected_asset_data.keys())} keys...\n")
    return {
        "guid": guid,
        **selected_asset_data
    }

def expand_by_ref_type(selected_key: str, selected_value: object, guid_index: dict, domain_config: dict, verbose: bool) -> object:
    """Expands the selected field by the reference type."""
    ref_type = domain_config[REF_TYPE_KEY]
    if ref_type == REF_TYPE_GUID and GUID_PATTERN.fullmatch(selected_value):
        guid = selected_value
        return replace_selected_guid(selected_key, guid, guid_index, domain_config, verbose)
    return selected_value

def expand_selected_field(selected_key: str, selected_value: object, guid_index: dict, domain_config: dict, verbose: bool) -> object:
    """Expands the selected field's guids or leave as-is."""
    if selected_value is None or selected_value == {} or selected_value == [] or selected_value == "":
        return None
    if isinstance(selected_value, str):
        return expand_by_ref_type(selected_key, selected_value, guid_index, domain_config, verbose)
    elif isinstance(selected_value, list):
        new_list = []
        for item in selected_value:
            if isinstance(item, str):
                new_list.append(expand_by_ref_type(selected_key, item, guid_index, domain_config, verbose))
            else:
                new_list.append(item)
        return new_list
    return selected_value

def expand_references_in_node(node: object, guid_index: dict, domain_config: dict, verbose: bool) -> None:
    """Expands all references required by the domain config in the node."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if key in domain_config[CONFIG_EXPAND_KEY]:
                node[key] = expand_selected_field(key, value, guid_index, domain_config, verbose)

#endregion



#region expand/traversal

def apply_traversal_actions(node: dict, guid_index: dict, domain_config: dict, en_strings: dict, verbose: bool) -> None:
    """Applies all traversal actions to the current node."""
    filter_node_by_domain_exclude_list(node, domain_config[CONFIG_EXCLUDE_KEY])
    expand_strings_in_node(node, domain_config, en_strings, verbose)
    expand_references_in_node(node, guid_index, domain_config, verbose)

def traverse_node(node: object, guid_index: dict, domain_config: dict, en_strings: dict, verbose: bool) -> None:
    """Traverses the tree and hands off actions for appropriate nodes."""
    if isinstance(node, dict):
        apply_traversal_actions(node, guid_index, domain_config, en_strings, verbose)
        for subnode in node.values():
            traverse_node(subnode, guid_index, domain_config, en_strings, verbose)
    elif isinstance(node, list):
        for item in node:
            traverse_node(item, guid_index, domain_config, en_strings, verbose)

#endregion



#region expand/load

def load_file(asset_path: Path, verbose: bool = False) -> dict:
    """Load a registry asset file as a dict."""
    if asset_path.suffix == ".json":
        lines = []
        for line in asset_path.read_text(encoding="utf-8").splitlines():
            if "//" in line:
                line = line[:line.index("//")].rstrip()
            if not line.strip() or line.lstrip().startswith("//"):
                continue
            lines.append(line)
        asset_data = json.loads("\n".join(lines))
        return asset_data
    return parse_yaml(asset_path, verbose)

def load_guid_into_registry(guid: str, guid_index: dict, domain_config: dict, en_strings: dict, verbose: bool) -> dict|list:
    """Expands the registered guid into its model data."""
    if guid not in guid_index:
        stdout.write(f"...WARNING: guid {guid} not found in guid index...\n")
        return guid
    asset_data = load_file(Path(guid_index[guid]), verbose=False)
    norm_asset_data = normalize_asset_tree(asset_data, verbose=False)
    traverse_node(norm_asset_data, guid_index, domain_config, en_strings, verbose)
    if verbose:
        stdout.write(f"...guid expanded to {len(norm_asset_data)} items...\n")
    return norm_asset_data

def expand_domain(domain_model_registry: dict, guid_index: dict, domain_config: dict, en_strings: dict, verbose: bool, testing: bool) -> dict:
    """Goes through all entries in the domain model registry and expands their references."""
    model_data = {}
    item_number = 0
    iterable_domain_model_registry = domain_model_registry if isinstance(domain_model_registry, list) else [domain_model_registry]
    for guid in iterable_domain_model_registry:
        if testing and item_number > TESTING_ITERATION_LIMIT:
            return model_data
        item_number += 1
        if verbose:
            stdout.write(f"...processing guid #{item_number} of {len(iterable_domain_model_registry)}: {guid}...\n")
        asset_data = load_guid_into_registry(guid, guid_index, domain_config, en_strings, verbose)
        if isinstance(asset_data, list):
            for index, record in enumerate(asset_data):
                prefix = f"aaaa{index:04x}"
                synth_guid = synthesize_new_guid(prefix, guid)
                model_data[synth_guid] = record
        else:
            model_data[guid] = asset_data
        if verbose:
            stdout.write(f"...finished processing guid {guid}...\n")
    return model_data

#endregion



#region dedupe

def run_deduplication(all_config: dict, domain_data: dict, verbose: bool) -> None:
    """Runs the deduplication process."""
    deduplication_config = all_config[CONFIG_DEDUPE_KEY]
    removed_records = 0
    for dedupe_pair in deduplication_config:
        keep_domain = dedupe_pair[DEDUPE_KEEP][DEDUPE_DOMAIN]
        keep_key = dedupe_pair[DEDUPE_KEEP][DEDUPE_KEY]
        remove_domain = dedupe_pair[DEDUPE_REMOVE][DEDUPE_DOMAIN]
        remove_key = dedupe_pair[DEDUPE_REMOVE][DEDUPE_KEY]
        keep_keys = set()
        if keep_domain not in domain_data or remove_domain not in domain_data:
            continue
        for keep_record in domain_data[keep_domain].values():
            if keep_key in keep_record:
                keep_keys.add(keep_record[keep_key])
        for guid in list(domain_data[remove_domain].keys()):
            if remove_key in domain_data[remove_domain][guid]:
                remove_value = domain_data[remove_domain][guid][remove_key]
                if remove_value in keep_keys:
                    del domain_data[remove_domain][guid]
                    removed_records += 1
    if verbose:
        stdout.write(f"...removed {removed_records} duplicate records...\n")

#endregion



#region separate

def synthesize_new_guid(guid_prefix: str, parent_guid: str, occurence_index: int = 0) -> str:
    """32-char guid: config prefix + tail from parent; last 4 hex digits encode occurrence_index."""
    borrow_length = len(parent_guid) - len(guid_prefix)
    parent_tail = parent_guid[:borrow_length]
    if occurence_index:
        parent_tail = parent_tail[:-4] + f"{occurence_index:04x}"
    return guid_prefix + parent_tail

def separate_data(parent_guid: str, parent_record: dict, separate_key: str, separation_rule: dict, all_domain_data: dict, occurence_index: int = 0) -> int:
    """Separates the data from the parent record into a new record."""
    if parent_record[separate_key] is None or parent_record[separate_key] == {} or parent_record[separate_key] == [] or parent_record[separate_key] == "":
        return 0
    subrecord_to_move = parent_record.pop(separate_key)
    synthetic_guid = synthesize_new_guid(separation_rule[SEPARATE_GUID_PREFIX], parent_guid, occurence_index)
    parent_record[separate_key] = synthetic_guid
    target_domain = separation_rule[SEPARATE_DOMAIN]
    if target_domain not in all_domain_data:
        all_domain_data[target_domain] = {}
    subrecord_to_move = { separate_key: subrecord_to_move }
    all_domain_data[target_domain][synthetic_guid] = subrecord_to_move
    return 1

def run_domain_separation_on_record(parent_guid: str, record: dict, separate_key: str, separation_rule: dict, all_domain_data: dict) -> int:
    """Runs the domain separation process on a record and returns the number of records moved."""
    if isinstance(record, dict):
        moved_records = 0
        for index, subvalue in enumerate(record.values()):
            if isinstance(subvalue, dict) and separate_key in subvalue:
                moved_records += separate_data(parent_guid, subvalue, separate_key, separation_rule, all_domain_data, index)
            elif isinstance(subvalue, list):
                for index, item in enumerate(subvalue):
                    if isinstance(item, dict) and separate_key in item:
                        moved_records += separate_data(parent_guid, item, separate_key, separation_rule, all_domain_data, index)
    return moved_records

def run_domain_separation(all_config: dict, all_domain_data: dict, verbose: bool) -> None:
    """Runs the domain separation process on records."""
    moved_records = 0
    for domain in list(all_domain_data.keys()):
        if domain not in all_config:
            continue
        domain_data = all_domain_data[domain]
        domain_config = all_config[domain]
        if CONFIG_SEPARATE_KEY not in domain_config:
            continue
        for guid, record in domain_data.items():
            for separate_key, separation_rule in domain_config[CONFIG_SEPARATE_KEY].items():
                if separate_key in record:
                    moved_records += separate_data(guid, record, separate_key, separation_rule, all_domain_data)
                else:
                    moved_records += run_domain_separation_on_record(guid, record, separate_key, separation_rule, all_domain_data)
    if verbose:
        stdout.write(f"...separated {moved_records} records...\n")

#endregion



#region main

def load_en_strings(game_config: dict) -> dict:
    """Loads the english strings from the game config."""
    source = game_config["pipeline"]["strings"]["source"]
    path = game_config["pipeline"]["strings"]["path"]
    if source == "i2":
        en_strings = {}
        i2_asset = parse_yaml(ROOT_PATH / path, verbose=False)
        for entry in i2_asset["mSource"]["mTerms"]:
            term = entry["Term"]
            english = entry["Languages"][0]
            en_strings[term] = english if english else "[No English translation]"
        return en_strings
    elif source == "json":
        with open(path, "r", encoding="utf-8") as strings_file:
            return json.load(strings_file)
    else:
        raise ValueError(f"Invalid string source: {source}")

def make_ref_pattern(game_config: dict) -> Pattern:
    """Compiles a regex pattern for the reference type."""
    ref_type = game_config["pipeline"]["domain_data"]["ref_type"]
    if ref_type == "guid":
        return GUID_PATTERN
    else:
        return UNIQUE_NAME_PATTERN

def compile_domain_data(model_registry: dict, guid_index: dict, game_config: dict, verbose: bool = False, testing: bool = False) -> dict:
    """Compile domain data from the model registry and guid index."""
    domain_data = {
        META_KEY_FIELDS: {},
        META_KEY_GUID_REF_INDEX: {},
        DATA_KEY: {},
    }
    en_strings = load_en_strings(game_config)
    domain_number = 0
    for domain in model_registry[MODEL_KEY].keys():
        if verbose:
            stdout.write(f"Processing domain {domain}...\n")
        domain_number += 1
        if verbose:
            stdout.write(f"...gathering data for domain {domain} ({domain_number}/{len(model_registry[MODEL_KEY])})...\n")
        domain_config = merge_config(game_config, domain)
        domain_data[DATA_KEY][domain] = expand_domain(model_registry[MODEL_KEY][domain], guid_index, domain_config, en_strings, verbose, testing)
        if verbose:
            stdout.write(f"...finished processing domain {domain}...\n")
        if testing and domain_number > TESTING_ITERATION_LIMIT:
            break
    run_deduplication(game_config, domain_data[DATA_KEY], verbose)
    run_domain_separation(game_config, domain_data[DATA_KEY], verbose)
    for domain in list(domain_data[DATA_KEY].keys()):
        domain_data[META_KEY_FIELDS][domain] = register_domain_fields(domain_data[DATA_KEY][domain])
    ref_pattern = make_ref_pattern(game_config)
    domain_data[META_KEY_GUID_REF_INDEX] = register_references(domain_data[DATA_KEY], ref_pattern)
    stdout.write(f"...finished compiling domain data for {len(domain_data[DATA_KEY])} domains...\n")
    return domain_data

#endregion



if __name__ == "__main__":
    with open(ROOT_PATH / "guid_index.json", "r", encoding="utf-8") as file:
        main_guid_index = json.load(file)
    with open(ROOT_PATH / "model_registry.json", "r", encoding="utf-8") as file:
        main_model_registry = json.load(file)
    with open(ROOT_PATH / "unity_setup_game_config.json", "r", encoding="utf-8") as file:
        main_game_config = json.load(file)
    stdout.write("Compiling domain data...")
    result = compile_domain_data(main_model_registry, main_guid_index, main_game_config, verbose=False, testing=False)
    stdout.write("...done.\n")
    with open(WRITE_DOMAIN_DATA_PATH, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=4)
