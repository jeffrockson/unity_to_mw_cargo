# pylint: disable=line-too-long, too-many-arguments, no-else-return
"""
Generates wiki-ready templates from domain data for storing by Cargo Mediawiki extension.

The manifest has four sections:
- analysis metadata
- #cargo_declare templates - MANIFEST_TEMPLATES_DECLARE
- #cargo_store templates - MANIFEST_TEMPLATES_STORE
- data - MANIFEST_DATA
- page index (division of data into pages) - MANIFEST_DATA_PAGES
"""
import json
import re
from sys import stdout
from pathlib import Path

from flatten_dict import flatten



ROOT_PATH = Path(__file__).parent
WRITE_CARGO_DATA_PATH = ROOT_PATH / "cargo_ready_manifest.json"

CONFIG_RENAME_KEY = "global_rename"

DOMAIN_DATA_KEY = "domains_data"

META_KEY_PREFIX = "META_MANIFEST"
META_KEY_TYPES = META_KEY_PREFIX + "_SEEN_TYPES"

MANIFEST_DATA = "domains_manifests"
MANIFEST_TEMPLATES_DECLARE = MANIFEST_DATA + "_declare_templates"
MANIFEST_TEMPLATES_ATTACH = MANIFEST_DATA + "_attach_templates"
MANIFEST_TEMPLATES_STORE = MANIFEST_DATA + "_store_templates"
MANIFEST_QUERIES = MANIFEST_DATA + "_queries"
MANIFEST_RECORDS = MANIFEST_DATA + "_data"
MANIFEST_INDEX = MANIFEST_DATA + "_index"

META_TYPE_NULL = "null"
META_TYPE_BOOL = "Boolean"
META_TYPE_INT = "Integer"
META_TYPE_FLOAT = "Float"
META_TYPE_FREEFORM_STRING = "Text"
META_TYPE_INDEXED_STRING = "String"

GUID_PATTERN = re.compile(r"([0-9a-f]{32})")
UNIQUE_NAME_PATTERN = re.compile(r"m_Name")

DISPLAY_NAME_SEARCHER = re.compile(r'\|displayName_key_en=(.*)')
UNIQUE_NAME_SEARCHER = re.compile(r'\|m_Name=(.*)')

FINAL_FIELD_TYPE = "type"

PATH_JOIN_CHARACTER = "_"

INDEX = "guid_index"
INDEX_DECLARE = INDEX + "_declare_template"
INDEX_ATTACH = INDEX + "_attach_template"
INDEX_STORE = INDEX + "_store_template"
INDEX_QUERIES = INDEX + "_queries"
INDEX_RECORDS = INDEX + "_data"
DOMAIN = "domain"
PAGE_NAME = "page_name"
GUID = "guid"

TEMPLATES_NAMESPACE = "Template"
DATA_NAMESPACE = "Data"

TESTING_ITERATION_LIMIT = 3



def generate_query_copyblock(domain: str, manifest_domain_types: dict) -> str:
    """Generates the query copyblock for a domain."""
    query = "{{#cargo_query: "
    query += "|table=" + domain
    query += "|fields=" + PAGE_NAME + ", " + GUID + ", " + ", ".join(manifest_domain_types.keys())
    query += "|limit=999999"
    query += "|named args=yes"
    query += "|order by=" + "sort_order"
    query += "|format=table"
    query += "}}"
    return query



def convert_lists_to_dicts_node(node: object) -> dict:
    """Converts lists to dictionaries in a node."""
    if not isinstance(node, dict):
        return node
    for key, value in node.items():
        if isinstance(value, list):
            new_dict = {}
            for i, item in enumerate(value):
                new_dict[str(i+1)] = convert_lists_to_dicts_node(item)
            node[key] = new_dict
        elif isinstance(value, dict):
            convert_lists_to_dicts_node(value)
    return node

def flatten_domain_data(domain_data: dict) -> dict:
    """Flattens the domain data into a non-nested dictionary."""
    flat = {}
    for guid, record in domain_data.items():
        only_dicts = convert_lists_to_dicts_node(record)
        flattened = flatten(only_dicts, reducer="underscore", keep_empty_types=(dict, list,))
        flat[guid] = flattened
    return flat



def classify_field_type(key: str, value: object) -> str:
    """Classifies the field type based on the python type of the value."""
    if value is None:
        return META_TYPE_NULL
    if isinstance(value, float):
        return META_TYPE_FLOAT
    if isinstance(value, (int, bool)):
        return META_TYPE_INT
    if isinstance(value, str):
        if GUID_PATTERN.fullmatch(value) or UNIQUE_NAME_PATTERN.fullmatch(key):
            return META_TYPE_INDEXED_STRING
    return META_TYPE_FREEFORM_STRING



def convert_field_to_template_parameter_line(field_name: str, field_value: object, manifest_domain_types: dict) -> str:
    """Converts a field to a template parameter line and saves its seen type."""
    # first save the type
    new_type = classify_field_type(field_name, field_value)
    if field_name not in manifest_domain_types:
        manifest_domain_types[field_name] = set()
    manifest_domain_types[field_name].add(new_type)
    # then convert the value
    if field_value is None or field_value == "":
        return None
    if isinstance(field_value, (dict, list)) and len(field_value) == 0:
        return None
    line = f"|{field_name}={field_value}"
    return line



def build_data_for_domain(domain: str, domain_data: dict, manifest: dict) -> dict:
    """Builds the data-storing template calls for a domain."""
    manifest_records = manifest[MANIFEST_DATA][MANIFEST_RECORDS]
    manifest_records[domain] = {}
    manifest[META_KEY_TYPES][domain] = {}
    for guid, record in domain_data.items():
        template_parameters = []
        for key, value in record.items():
            line = convert_field_to_template_parameter_line(key, value, manifest[META_KEY_TYPES][domain])
            if line is not None:
                template_parameters.append(line)
        manifest_records[domain][guid] = template_parameters



def reduce_domain_types(types: set) -> str|list:
    """Reduces the domain types to a single type."""
    if len(types) == 1:
        return list(types)[0]
    else:
        if META_TYPE_NULL in types and len(types) > 1:
            types.discard(META_TYPE_NULL)
        if META_TYPE_INT in types and META_TYPE_FLOAT in types:
            types.discard(META_TYPE_INT)
        if META_TYPE_INT in types and (META_TYPE_FREEFORM_STRING in types or META_TYPE_INDEXED_STRING in types):
            types.discard(META_TYPE_INT)
        if META_TYPE_FLOAT in types and (META_TYPE_FREEFORM_STRING in types or META_TYPE_INDEXED_STRING in types):
            types.discard(META_TYPE_FLOAT)
        if META_TYPE_INDEXED_STRING in types and META_TYPE_FREEFORM_STRING in types:
            types.discard(META_TYPE_INDEXED_STRING)
        if types:
            if len(types) == 1:
                return list(types)[0]
            else:
                return sorted(types)
        else:
            return META_TYPE_FREEFORM_STRING

def build_declare_template_for_domain(domain: str, manifest_domain_types: dict) -> str:
    """Builds the declare template for a domain."""
    template = "{{#cargo_declare: "
    template += f"_table={domain}"
    parameters = [
        PAGE_NAME + "=" + META_TYPE_INDEXED_STRING,
        GUID + "=" + META_TYPE_INDEXED_STRING,
    ]
    for field_name, field_type in manifest_domain_types.items():
        parameters.append(f"{field_name}={field_type}")
    template += "|" + "|".join(parameters)
    template += "}}"
    return template

def build_attach_template_for_domain(domain: str) -> str:
    """Creates the attach parser function for a domain."""
    return f"{{{{#cargo_attach: _table={domain}}}}}"

def build_store_template_for_domain(domain: str, manifest_domain_types: dict) -> str:
    """Builds the store template for a domain."""
    template = "{{#cargo_store: "
    template += f"_table={domain}"
    parameters = [
        PAGE_NAME + "=" + "{{{" + PAGE_NAME + "|}}}",
        GUID + "=" + "{{{" + GUID + "|}}}",
    ]
    for field_name in manifest_domain_types.keys():
        new_param = f"{field_name}="
        new_param += "{{{"
        new_param += field_name
        new_param += "|}}}"
        parameters.append(new_param)
    template += "|" + "|".join(parameters)
    template += "}}"
    return template

def finalize_record_as_template_markup(domain: str, guid: str, param_lines: list) -> str:
    """Converts the list of parameters to one template call for the record."""
    t_call = "{{" + domain
    t_call += f"|{GUID}={guid}"
    t_call += "".join(param_lines)
    t_call += "}}"
    return t_call

def finalize_domain_manifest(domain: str, manifest: dict) -> None:
    """Finalizes the domain manifest."""
    manifest_domain_types = manifest[META_KEY_TYPES][domain]
    manifest_data = manifest[MANIFEST_DATA]
    manifest_index = manifest[MANIFEST_INDEX]
    for field_name, field_types in manifest_domain_types.items():
        field_types = manifest_domain_types[field_name]
        manifest_domain_types[field_name] = reduce_domain_types(field_types)
    manifest_data[MANIFEST_TEMPLATES_DECLARE][domain] = build_declare_template_for_domain(domain, manifest_domain_types)
    manifest_data[MANIFEST_TEMPLATES_ATTACH][domain] = build_attach_template_for_domain(domain)
    manifest_data[MANIFEST_TEMPLATES_STORE][domain] = build_store_template_for_domain(domain, manifest_domain_types)
    for guid in list(manifest_data[MANIFEST_RECORDS][domain].keys()):
        param_lines = manifest_data[MANIFEST_RECORDS][domain][guid]
        display_name_match = None
        unique_name_match = None
        for line in param_lines:
            if not display_name_match:
                display_name_match = DISPLAY_NAME_SEARCHER.search(line)
            if not unique_name_match:
                unique_name_match = UNIQUE_NAME_SEARCHER.search(line)
            if display_name_match and unique_name_match:
                break
        display_name = display_name_match.group(1) if display_name_match else None
        unique_name = unique_name_match.group(1) if unique_name_match else None
        page_key = display_name if display_name else unique_name if unique_name else guid
        manifest_data[MANIFEST_RECORDS][domain][page_key] = finalize_record_as_template_markup(domain, guid, param_lines)
        if page_key != guid:
            manifest_data[MANIFEST_RECORDS][domain].pop(guid)
        manifest_index[INDEX_RECORDS][guid] = {
            DOMAIN: domain,
            PAGE_NAME: page_key,
        }
    manifest_data[MANIFEST_QUERIES][domain] = generate_query_copyblock(domain, manifest_domain_types)



def build_templates_for_guid_index(manifest: dict) -> None:
    """Builds the templates for the guid index."""
    template_dec =  "{{#cargo_declare: "
    template_dec += f"_table={INDEX}"
    parameters = [
        PAGE_NAME + "=" + META_TYPE_INDEXED_STRING,
        GUID + "=" + META_TYPE_INDEXED_STRING,
        DOMAIN + "=" + META_TYPE_INDEXED_STRING,
    ]
    template_dec += "|" + "|".join(parameters)
    template_dec += "}}"
    manifest[MANIFEST_INDEX][INDEX_DECLARE] = template_dec
    template_att = "{{#cargo_attach: "
    template_att += f"_table={INDEX}"
    template_att += "}}"
    manifest[MANIFEST_INDEX][INDEX_ATTACH] = template_att
    template_store = "{{#cargo_store: "
    template_store += f"_table={INDEX}"
    parameters = [
        PAGE_NAME + "=" + "{{{" + PAGE_NAME + "|}}}",
        GUID + "=" + "{{{" + GUID + "|}}}",
        DOMAIN + "=" + "{{{" + DOMAIN + "|}}}",
    ]
    template_store += "|" + "|".join(parameters)
    template_store += "}}"
    manifest[MANIFEST_INDEX][INDEX_STORE] = template_store
    query = "{{#cargo_query: "
    query += "|table=" + INDEX
    query += "|fields=" + GUID + ", " + PAGE_NAME + ", " + DOMAIN
    query += "|limit=999999"
    query += "|named args=yes"
    query += "|format=table"
    query += "}}"
    manifest[MANIFEST_INDEX][INDEX_QUERIES] = query

def finalize_guid_index(manifest: dict) -> None:
    """Finalizes the guid index."""
    index = manifest[MANIFEST_INDEX]
    index_records = index[INDEX_RECORDS]
    for guid in list(index_records.keys()):
        index_entry = index_records.pop(guid)
        domain = index_entry[DOMAIN]
        page_name = index_entry[PAGE_NAME]
        param_lines = [
            f"|{PAGE_NAME}={page_name}",
            f"|{DOMAIN}={domain}",
        ]
        index_records[guid] = finalize_record_as_template_markup(INDEX, guid, param_lines)



def process_global_renames_node(node: object, config_renames: dict) -> object:
    """Processes the global renames for a node."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if key in config_renames:
                configured_key = config_renames[key]
                node[configured_key] = node.pop(key)
                key = configured_key
            node[key] = process_global_renames_node(value, config_renames)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            node[i] = process_global_renames_node(item, config_renames)
    return node



def extract_cargo_manifest(standardized_domain_data: dict, game_config: dict, verbose: bool = False, testing: bool = False) -> str:
    """Converts domain data and meta data into cargo-ready manifest."""
    config_renames = game_config[CONFIG_RENAME_KEY]
    for domain in list(standardized_domain_data[DOMAIN_DATA_KEY].keys()):
        domain_data = standardized_domain_data[DOMAIN_DATA_KEY][domain]
        domain_data = process_global_renames_node(domain_data, config_renames)
        if domain in config_renames:
            standardized_domain_data[DOMAIN_DATA_KEY][config_renames[domain]] = standardized_domain_data[DOMAIN_DATA_KEY].pop(domain)
    manifest = {
        META_KEY_TYPES: {},
        MANIFEST_DATA: {
            MANIFEST_TEMPLATES_DECLARE: {},
            MANIFEST_TEMPLATES_ATTACH: {},
            MANIFEST_TEMPLATES_STORE: {},
            MANIFEST_QUERIES: {},
            MANIFEST_RECORDS: {}
        },
        MANIFEST_INDEX: {
            INDEX_RECORDS: {}
        }
    }
    domain_number = 0
    for domain, domain_data in standardized_domain_data[DOMAIN_DATA_KEY].items():
        domain_number += 1
        if testing and domain_number > TESTING_ITERATION_LIMIT:
            break
        if verbose:
            stdout.write(f"Developing manifest for domain {domain} ({domain_number}/{len(standardized_domain_data[DOMAIN_DATA_KEY])})...\n")
        flattened_domain_data = flatten_domain_data(domain_data)
        build_data_for_domain(domain, flattened_domain_data, manifest)
        finalize_domain_manifest(domain, manifest)
        if verbose:
            stdout.write(f"...done with {domain}\n")
    build_templates_for_guid_index(manifest)
    finalize_guid_index(manifest)
    stdout.write(f"...finished developing manifest for {domain_number} domains...\n")
    return manifest



if __name__ == "__main__":
    with open(ROOT_PATH / "guid_index.json", "r", encoding="utf-8") as file:
        main_guid_index = json.load(file)
    with open(ROOT_PATH / "standardized_domain_data.json", "r", encoding="utf-8") as file:
        main_domain_data = json.load(file)
    with open(ROOT_PATH / "unity_setup_game_config.json", "r", encoding="utf-8") as file:
        main_game_config = json.load(file)
    stdout.write("Developing domain data into cargo manifest...\n")
    cargo_manifest = extract_cargo_manifest(main_domain_data, main_game_config)#, verbose=True, testing=True)
    with open(WRITE_CARGO_DATA_PATH, "w", encoding="utf-8") as file:
        json.dump(cargo_manifest, file, indent=4)
    stdout.write("...done saving cargo-ready data.\n")
