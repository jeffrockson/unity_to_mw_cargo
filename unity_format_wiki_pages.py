# pylint: disable=line-too-long
"""
Structures wiki pages out of the cargo_ready_domain_manifest
"""
import json
from sys import stdout
from pathlib import Path



ROOT_PATH = Path(__file__).parent
WRITE_PATH = ROOT_PATH / "pages_wiki_content.json"

IN_MANIFEST_KEY = "domains_manifests"
IN_MANIFEST_DECLARE_KEY = "domains_manifests_declare_templates"
IN_MANIFEST_ATTACH_KEY = "domains_manifests_attach_templates"
IN_MANIFEST_STORE_KEY = "domains_manifests_store_templates"
IN_MANIFEST_RECORDS_KEY = "domains_manifests_data"

IN_INDEX_KEY = "domains_manifests_index"
IN_INDEX_DECLARE_KEY = "guid_index_declare_template"
IN_INDEX_ATTACH_KEY = "guid_index_attach_template"
IN_INDEX_STORE_KEY = "guid_index_store_template"
IN_INDEX_RECORDS_KEY = "guid_index_data"

CONTENT_PAGES_KEY = "pages_content"
CONTENT_PAGES_NAMESPACE_KEY = "namespace"
CONTENT_PAGES_TITLE_KEY = "title"
CONTENT_PAGES_CONTENT_KEY = "contents"

GUID_INDEX = "guid_index"

TEMPLATE_NAMESPACE = "Template"
DATA_NAMESPACE = "Data"
NAMESPACE_SEPARATOR = ":"
TEMPLATE_PAGE_NAME = "Dataloader"
PAGE_NAME_SEPARATOR = "/"

MAX_PAGE_BYTES = 1_500_000

AUTO_CONTENT_NOTE = "<!-- This page was automatically generated from game data. Any manual edits will be overwritten the next time data is imported. -->"

TESTING_ITERATION_LIMIT = 4



# pylint: disable=unused-argument
def format_template_page(declare_template: str, attach_template: str, store_template: str) -> str:
    """Formats the template page."""
    page_content = AUTO_CONTENT_NOTE + "\n"
    page_content += "<noinclude>\n"
    page_content += declare_template + "\n"
    # skip attach since these are going in one page
    page_content += "</noinclude>\n"
    page_content += "<includeonly>\n"
    page_content += store_template + "\n"
    page_content += "</includeonly>\n"
    return page_content



def clarify_template_call(domain: str, key: str, record: str) -> str:
    """Splits the record and reformats the template name."""
    # pylint: disable=unused-variable
    prefix, remainder = record.split("|", 1)
    template_call = "{{" + TEMPLATE_PAGE_NAME + PAGE_NAME_SEPARATOR + domain
    template_call += "|page_name=" + key
    template_call += "|" + remainder
    return template_call

def paginate_domain_records(domain: str, records: dict) -> list:
    """Paginate the domain records."""
    pages = []
    page_number = 1
    page_title = DATA_NAMESPACE + NAMESPACE_SEPARATOR + domain + PAGE_NAME_SEPARATOR + str(page_number)
    current_page = {
        CONTENT_PAGES_NAMESPACE_KEY: DATA_NAMESPACE,
        CONTENT_PAGES_TITLE_KEY: page_title,
        CONTENT_PAGES_CONTENT_KEY: AUTO_CONTENT_NOTE + "\n"
    }
    current_page_size = 0
    for key, record in records.items():
        size_bytes = len(record.encode("utf-8")) + 11 # 11 for newlines and "Dataloader" prefix
        if current_page_size + size_bytes > MAX_PAGE_BYTES:
            pages.append(current_page)
            page_number += 1
            page_title = DATA_NAMESPACE + NAMESPACE_SEPARATOR + domain + PAGE_NAME_SEPARATOR + str(page_number)
            current_page = {
                CONTENT_PAGES_NAMESPACE_KEY: DATA_NAMESPACE,
                CONTENT_PAGES_TITLE_KEY: page_title,
                CONTENT_PAGES_CONTENT_KEY: AUTO_CONTENT_NOTE + "\n"
            }
            current_page_size = 0
        template_call = clarify_template_call(domain, key, record)
        current_page[CONTENT_PAGES_CONTENT_KEY] += template_call + "\n\n"
        current_page_size += size_bytes
    pages.append(current_page)
    return pages



def build_domain_pages(domain: str, manifest: dict) -> dict:
    """Builds the domain pages."""
    template_page_title = TEMPLATE_NAMESPACE + NAMESPACE_SEPARATOR + TEMPLATE_PAGE_NAME + PAGE_NAME_SEPARATOR + domain
    declare = manifest[IN_MANIFEST_DECLARE_KEY][domain]
    attach = manifest[IN_MANIFEST_ATTACH_KEY][domain]
    store = manifest[IN_MANIFEST_STORE_KEY][domain]
    records = manifest[IN_MANIFEST_RECORDS_KEY][domain]
    domain_pages = [
        {
            CONTENT_PAGES_NAMESPACE_KEY: TEMPLATE_NAMESPACE,
            CONTENT_PAGES_TITLE_KEY: template_page_title,
            CONTENT_PAGES_CONTENT_KEY: format_template_page(declare, attach, store)
        }
    ]
    page_records = paginate_domain_records(domain, records)
    domain_pages.extend(page_records)
    return domain_pages



def clarify_index_template_call(entry: str) -> str:
    """Splits the record and reformats the template name."""
    # pylint: disable=unused-variable
    prefix, remainder = entry.split("|", 1)
    template_call = "{{" + TEMPLATE_PAGE_NAME + PAGE_NAME_SEPARATOR + GUID_INDEX
    template_call += "|" + remainder
    return template_call



def paginate_index_entries(entries: dict) -> list:
    """Paginate the index entries."""
    pages = []
    page_number = 1
    page_title = DATA_NAMESPACE + NAMESPACE_SEPARATOR + GUID_INDEX + PAGE_NAME_SEPARATOR + str(page_number)
    current_page = {
        CONTENT_PAGES_NAMESPACE_KEY: DATA_NAMESPACE,
        CONTENT_PAGES_TITLE_KEY: page_title,
        CONTENT_PAGES_CONTENT_KEY: AUTO_CONTENT_NOTE + "\n"
    }
    current_page_size = 0
    for entry in entries.values():
        size_bytes = len(entry.encode("utf-8")) + 11 # 11 for newlines and "Dataloader" prefix
        if current_page_size + size_bytes > MAX_PAGE_BYTES:
            pages.append(current_page)
            page_number += 1
            page_title = DATA_NAMESPACE + NAMESPACE_SEPARATOR + GUID_INDEX + PAGE_NAME_SEPARATOR + str(page_number)
            current_page = {
                CONTENT_PAGES_NAMESPACE_KEY: DATA_NAMESPACE,
                CONTENT_PAGES_TITLE_KEY: page_title,
                CONTENT_PAGES_CONTENT_KEY: AUTO_CONTENT_NOTE + "\n"
            }
            current_page_size = 0
        template_call = clarify_index_template_call(entry)
        current_page[CONTENT_PAGES_CONTENT_KEY] += template_call + "\n\n"
        current_page_size += size_bytes
    pages.append(current_page)
    return pages



def build_guid_index_pages(index: dict) -> dict:
    """Builds the guid index pages."""
    template_page_title = TEMPLATE_NAMESPACE + NAMESPACE_SEPARATOR + TEMPLATE_PAGE_NAME + PAGE_NAME_SEPARATOR + GUID_INDEX
    declare = index[IN_INDEX_DECLARE_KEY]
    attach = index[IN_INDEX_ATTACH_KEY]
    store = index[IN_INDEX_STORE_KEY]
    entries = index[IN_INDEX_RECORDS_KEY]
    index_pages = [
        {
            CONTENT_PAGES_NAMESPACE_KEY: TEMPLATE_NAMESPACE,
            CONTENT_PAGES_TITLE_KEY: template_page_title,
            CONTENT_PAGES_CONTENT_KEY: format_template_page(declare, attach, store)
        }
    ]
    index_records = paginate_index_entries(entries)
    index_pages.extend(index_records)
    return index_pages



def format_wiki_pages(cargo_manifest: dict, verbose: bool = False, testing: bool = False) -> dict:
    """Forms the wiki pages out of the cargo manifest."""
    pages_content = {
        CONTENT_PAGES_KEY: []
    }
    manifest = cargo_manifest[IN_MANIFEST_KEY]
    domain_list = list(manifest[IN_MANIFEST_DECLARE_KEY].keys())
    domain_number = 0
    for domain in domain_list:
        domain_number += 1
        if testing and domain_number > TESTING_ITERATION_LIMIT:
            break
        if verbose:
            stdout.write(f"Formatting pages for domain {domain} ({domain_number}/{len(domain_list)})...\n")
        domain_pages = build_domain_pages(domain, manifest)
        pages_content[CONTENT_PAGES_KEY].extend(domain_pages)
        if verbose:
            stdout.write("...done\n")
    index = cargo_manifest[IN_INDEX_KEY]
    pages_content[CONTENT_PAGES_KEY].extend(build_guid_index_pages(index))
    stdout.write(f"...finished formatting pages for {domain_number} domains...\n")
    return pages_content



if __name__ == "__main__":
    with open(ROOT_PATH / "cargo_ready_manifest.json", "r", encoding="utf-8") as file:
        loaded_cargo_manifest = json.load(file)
    all_pages = format_wiki_pages(loaded_cargo_manifest)#, verbose=True, testing=True)
    with open(WRITE_PATH, "w", encoding="utf-8") as file:
        json.dump(all_pages, file, indent=4)
