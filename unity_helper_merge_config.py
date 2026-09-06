# pylint: disable=line-too-long, no-else-return
"""
Merge configurations for all domains with the selected domain from the unity domain config.
"""
import json
from sys import stdout
from pathlib import Path



ROOT_PATH = Path(__file__).parent

ALL_DOMAINS_KEY = "all_domains"

PIPELINE_KEY = "pipeline"
PIPELINE_DATA_KEY = "domain_data"
PIPELINE_REF_TYPE_KEY = "ref_type"


DOMAIN_NAME_KEY = "_domain_name"
STRINGS_KEY = "strings"

EXCLUDE_KEY = "exclude"
EXPAND_KEY = "expand"
SEPARATE_KEY = "separate"



def merge_lists(domain_list: list, all_list: list) -> list:
    """Merges the domain list into the all list."""
    merged_list = []
    for item in all_list:
        merged_list.append(item)
    for item in domain_list:
        if item not in merged_list:
            merged_list.append(item)
    return merged_list

def merge_exclude_list(domain_exclude: list, all_exclude: list) -> list:
    """Defers to merge_lists; named to make intent clear at caller."""
    return merge_lists(domain_exclude, all_exclude)

def merge_expand_dict(domain_expand: dict, all_expand: dict) -> dict:
    """Merges the domain dict into the all dict by merging their lists."""
    merged_expand_dict = {}
    for key in all_expand:
        merged_expand_dict[key] = list(all_expand[key])
    for key in domain_expand:
        if key not in merged_expand_dict:
            merged_expand_dict[key] = domain_expand[key]
        else:
            merged_expand_dict[key] = merge_lists(domain_expand[key], all_expand[key])
    return merged_expand_dict



def merge_domain(domain_config: dict, all_domains_config: dict) -> dict:
    """Merges one domain configuration into the all-domains configuration."""
    merged_domain_config = {
        DOMAIN_NAME_KEY: all_domains_config.get(DOMAIN_NAME_KEY, ""),
        STRINGS_KEY: all_domains_config.get(STRINGS_KEY, {}),
        PIPELINE_REF_TYPE_KEY: all_domains_config.get(PIPELINE_REF_TYPE_KEY, "guid"),
    }
    merged_domain_config[EXCLUDE_KEY] = merge_exclude_list(domain_config.get(EXCLUDE_KEY, []), all_domains_config.get(EXCLUDE_KEY, []))
    merged_domain_config[EXPAND_KEY] = merge_expand_dict(domain_config.get(EXPAND_KEY, {}), all_domains_config.get(EXPAND_KEY, {}))
    if SEPARATE_KEY in domain_config:
        merged_domain_config[SEPARATE_KEY] = domain_config[SEPARATE_KEY]
    return merged_domain_config



def merge_config(all_config: dict|None, domain: str) -> dict:
    """Returns one configuration set for the specified domain."""
    aug_config = {
        DOMAIN_NAME_KEY: domain,
        PIPELINE_REF_TYPE_KEY: all_config[PIPELINE_KEY][PIPELINE_DATA_KEY][PIPELINE_REF_TYPE_KEY]
    }
    aug_config.update(all_config[ALL_DOMAINS_KEY])
    if domain in all_config:
        return merge_domain(all_config[domain], aug_config)
    else:
        return aug_config



if __name__ == "__main__":
    with open(ROOT_PATH / "unity_setup_game_config.json", "r", encoding="utf-8") as file:
        main_game_config = json.load(file)
    result = merge_config(main_game_config, "goals")
    stdout.write(json.dumps(result, indent=4) + "\n")
