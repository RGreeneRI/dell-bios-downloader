
#!/usr/bin/env python3

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime
from pathlib import Path


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

INDEX_CAB_URL = (
    "https://downloads.dell.com/catalog/CatalogIndexPC.cab"
)

DOWNLOAD_BASE = "https://downloads.dell.com/"

SCRIPT_DIR = Path(__file__).resolve().parent

MODELS_FILE = SCRIPT_DIR / "models.txt"

WORK_DIR = SCRIPT_DIR / "catalog_cache"

DOWNLOAD_DIR = SCRIPT_DIR / "downloads"

USER_AGENT = "Mozilla/5.0 DellBIOSDownloader/2.0"

TIMEOUT = 120


# ------------------------------------------------------------
# General helpers
# ------------------------------------------------------------

def normalize_name(name):
    """Normalize model names for comparison."""

    return re.sub(r"[^a-z0-9]", "", name.lower())


def local_name(tag):
    """Remove XML namespace from an element name."""

    return tag.split("}")[-1]


def get_child_text(element, name):
    """
    Get text from a child element, ignoring XML namespaces.
    Also supports attributes with the requested name.
    """

    if element is None:
        return ""

    # Check attributes first.
    value = element.attrib.get(name)

    if value:
        return value.strip()

    # Check direct children.
    for child in element:
        if local_name(child.tag).lower() == name.lower():
            return (child.text or "").strip()

    return ""


def get_descendant_text(element, name):
    """Find text from a descendant element."""

    if element is None:
        return ""

    for child in element.iter():
        if local_name(child.tag).lower() == name.lower():
            value = (child.text or "").strip()

            if value:
                return value

    return ""


def load_models(filename):
    """Load model names from models.txt."""

    filename = Path(filename)

    if not filename.exists():
        raise FileNotFoundError(
            f"Model file not found: {filename}"
        )

    models = []

    with filename.open("r", encoding="utf-8-sig") as file:

        for line in file:

            line = line.strip()

            if not line or line.startswith("#"):
                continue

            models.append(line)

    if not models:
        raise ValueError("No models found in models.txt")

    return models


# ------------------------------------------------------------
# Download helpers
# ------------------------------------------------------------

def download_file(url, destination):
    """Download a file with progress information."""

    destination = Path(destination)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"\nDownloading:")
    print(url)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    temporary_file = destination.with_suffix(
        destination.suffix + ".part"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT
        ) as response:

            total = response.headers.get(
                "Content-Length"
            )

            total = int(total) if total else 0

            downloaded = 0

            with temporary_file.open("wb") as output:

                while True:

                    chunk = response.read(1024 * 1024)

                    if not chunk:
                        break

                    output.write(chunk)

                    downloaded += len(chunk)

                    if total:

                        percent = (
                            downloaded / total
                        ) * 100

                        print(
                            f"\rProgress: {percent:5.1f}%",
                            end="",
                            flush=True
                        )

        if total:
            print()

        temporary_file.replace(destination)

        print(f"Saved: {destination}")

        return destination

    except Exception:

        if temporary_file.exists():
            temporary_file.unlink()

        raise


def resolve_url(path, base_location=None):
    """Convert a Dell catalog path into a complete URL."""

    path = path.strip()

    if not path:
        raise ValueError("Empty URL path in Dell catalog")

    if path.startswith(("http://", "https://")):
        return path

    if base_location:

        base_location = base_location.strip()

        if not base_location.startswith(
            ("http://", "https://")
        ):
            base_location = "https://" + base_location

        if not base_location.endswith("/"):
            base_location += "/"

        return urllib.parse.urljoin(
            base_location,
            path.lstrip("/")
        )

    return urllib.parse.urljoin(
        DOWNLOAD_BASE,
        path.lstrip("/")
    )


# ------------------------------------------------------------
# CAB extraction
# ------------------------------------------------------------

def extract_cab_file(cab_file, output_dir, preferred_xml=None):
    """Extract a Dell CAB file using cabextract."""

    if not shutil.which("cabextract"):

        raise RuntimeError(
            "cabextract is not installed.\n"
            "Install it with:\n"
            "sudo dnf install epel-release -y\n"
            "sudo dnf install cabextract -y"
        )

    output_dir = Path(output_dir)

    if output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"\nExtracting {Path(cab_file).name}...")

    result = subprocess.run(
        [
            "cabextract",
            "-q",
            "-d",
            str(output_dir),
            str(cab_file)
        ],
        capture_output=True,
        text=True
    )

    # Dell CAB files can produce warnings about trailing bytes.
    # If the XML was successfully extracted, continue.

    xml_files = list(output_dir.rglob("*.xml"))

    if not xml_files:

        raise RuntimeError(
            f"Could not extract XML from {cab_file}\n"
            f"{result.stderr}"
        )

    if preferred_xml:

        for xml_file in xml_files:

            if xml_file.name.lower() == preferred_xml.lower():
                return xml_file

    return xml_files[0]


# ------------------------------------------------------------
# Catalog index parsing
# ------------------------------------------------------------

def get_model_details(model_element):
    """Extract model name and System ID from an index Model."""

    system_id = model_element.attrib.get(
        "systemID",
        ""
    ).strip()

    model_name = model_element.attrib.get(
        "name",
        ""
    ).strip()

    if not model_name:

        model_name = get_descendant_text(
            model_element,
            "Display"
        )

    return model_name, system_id


def parse_catalog_index(xml_file):
    """
    Parse CatalogIndexPC.xml.

    Each GroupManifest identifies supported models and
    the platform-specific catalog containing their updates.
    """

    print("\nReading Dell catalog index...")

    tree = ET.parse(xml_file)

    root = tree.getroot()

    models = []

    for group in root.iter():

        if local_name(group.tag) != "GroupManifest":
            continue

        # Find the platform catalog path.
        manifest_info = None

        for child in group.iter():

            if local_name(child.tag) == "ManifestInformation":
                manifest_info = child
                break

        if manifest_info is None:
            continue

        catalog_path = get_child_text(
            manifest_info,
            "path"
        )

        if not catalog_path:
            continue

        # Find supported model entries.
        for model_element in group.iter():

            if local_name(model_element.tag) != "Model":
                continue

            model_name, system_id = get_model_details(
                model_element
            )

            if not model_name:
                continue

            models.append({
                "name": model_name,
                "system_id": system_id,
                "catalog_path": catalog_path
            })

    # Remove duplicate combinations.
    unique = {}

    for item in models:

        key = (
            normalize_name(item["name"]),
            item["system_id"],
            item["catalog_path"]
        )

        unique[key] = item

    return list(unique.values())


# ------------------------------------------------------------
# Model listing
# ------------------------------------------------------------

def list_catalog_models(models, filter_text=None):
    """Display available models from CatalogIndexPC."""

    if filter_text:

        search = filter_text.lower()

        models = [
            model for model in models
            if search in model["name"].lower()
            or search in model["system_id"].lower()
        ]

    models.sort(
        key=lambda item: (
            item["name"].lower(),
            item["system_id"]
        )
    )

    print("\n" + "=" * 95)
    print("DELL MODELS AVAILABLE IN CATALOG")
    print("=" * 95)

    print(
        f"{'MODEL NAME':48} "
        f"{'SYSTEM ID':15} "
        f"{'CATALOG ENTRIES'}"
    )

    print("-" * 95)

    counts = {}

    for model in models:

        key = (
            model["name"],
            model["system_id"]
        )

        counts[key] = counts.get(key, 0) + 1

    for (name, system_id), count in sorted(
        counts.items(),
        key=lambda item: item[0][0].lower()
    ):

        print(
            f"{name:48} "
            f"{system_id:15} "
            f"{count}"
        )

    print("-" * 95)

    print(
        f"Total model/System ID combinations: "
        f"{len(counts)}"
    )

    print("=" * 95)


# ------------------------------------------------------------
# Version and date handling
# ------------------------------------------------------------

def version_key(version):
    """
    Convert a version string into a sortable natural key.

    Examples:
        1.10.0 sorts higher than 1.9.0
        A12 sorts higher than A9
    """

    if not version:
        return ()

    parts = re.findall(
        r"\d+|[a-zA-Z]+",
        str(version)
    )

    result = []

    for part in parts:

        if part.isdigit():
            result.append((0, int(part)))

        else:
            result.append((1, part.lower()))

    return tuple(result)


def parse_release_date(value):
    """Convert a Dell release date into a datetime."""

    if not value:
        return datetime.min

    value = value.strip()

    try:

        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).replace(tzinfo=None)

    except ValueError:
        pass

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%Y-%m-%dT%H:%M:%S"
    ]

    for date_format in formats:

        try:
            return datetime.strptime(
                value,
                date_format
            )

        except ValueError:
            continue

    return datetime.min


# ------------------------------------------------------------
# Platform catalog parsing
# ------------------------------------------------------------

def parse_platform_catalog(xml_file, catalog_path, model_names):
    """
    Parse a model-specific platform catalog.

    Returns BIOS software components.
    """

    print(
        f"\nReading platform catalog: {catalog_path}"
    )

    tree = ET.parse(xml_file)

    root = tree.getroot()

    manifest = None

    for element in root.iter():

        if local_name(element.tag) == "Manifest":
            manifest = element
            break

    if manifest is None:
        raise RuntimeError(
            f"Could not find Manifest element in {xml_file}"
        )

    # Dell catalogs generally specify their download
    # base location in the Manifest element.

    base_location = (
        manifest.attrib.get("baseLocation", "")
        or get_child_text(manifest, "baseLocation")
        or DOWNLOAD_BASE
    )

    components = []

    for component in manifest.iter():

        if local_name(component.tag) != "SoftwareComponent":
            continue

        component_type = None

        for child in component:

            if local_name(child.tag) == "ComponentType":

                component_type = child.attrib.get(
                    "value",
                    ""
                ).strip().upper()

                break

        if component_type != "BIOS":
            continue

        package_path = get_child_text(
            component,
            "path"
        )

        if not package_path:
            continue

        version = (
            get_child_text(component, "vendorVersion")
            or get_child_text(component, "dellVersion")
        )

        release_date = get_child_text(
            component,
            "releaseDate"
        )

        name = get_descendant_text(
            component,
            "Display"
        )

        package_id = (
            component.attrib.get("packageID", "")
            or get_child_text(component, "packageID")
        )

        download_url = resolve_url(
            package_path,
            base_location
        )

        components.append({
            "models": model_names,
            "name": name or "Dell BIOS Update",
            "version": version,
            "release_date": release_date,
            "date_key": parse_release_date(release_date),
            "version_key": version_key(version),
            "package_id": package_id,
            "path": package_path,
            "url": download_url,
            "catalog": catalog_path
        })

    return components


# ------------------------------------------------------------
# Find latest BIOS for each requested model
# ------------------------------------------------------------

def find_latest_bios(index_models, requested_models):
    """Download platform catalogs and select latest BIOS."""

    requested = {
        normalize_name(name): name
        for name in requested_models
    }

    matched = {}

    for model in index_models:

        normalized = normalize_name(
            model["name"]
        )

        if normalized not in requested:
            continue

        requested_name = requested[normalized]

        matched.setdefault(
            requested_name,
            []
        ).append(model)

    # Report requested models missing from Dell's index.

    for model_name in requested_models:

        if model_name not in matched:

            print(
                f"\nWARNING: Model not found in Dell index: "
                f"{model_name}"
            )

    # Associate each unique platform catalog with the
    # requested models that use it.

    catalog_map = {}

    for model_name, entries in matched.items():

        for entry in entries:

            path = entry["catalog_path"]

            catalog_map.setdefault(
                path,
                set()
            ).add(model_name)

    if not catalog_map:
        return {}

    all_components = []

    # Download and parse each unique platform catalog.

    for catalog_path, model_names in catalog_map.items():

        catalog_url = resolve_url(catalog_path)

        digest = hashlib.sha1(
            catalog_path.encode("utf-8")
        ).hexdigest()[:12]

        catalog_dir = WORK_DIR / "platform" / digest

        cab_file = WORK_DIR / "platform" / (
            digest + ".cab"
        )

        try:

            download_file(
                catalog_url,
                cab_file
            )

            xml_file = extract_cab_file(
                cab_file,
                catalog_dir,
                preferred_xml="Catalog.xml"
            )

            components = parse_platform_catalog(
                xml_file,
                catalog_path,
                sorted(model_names)
            )

            all_components.extend(components)

            print(
                f"Found {len(components)} BIOS entries."
            )

        except Exception as error:

            print(
                f"\nERROR processing platform catalog "
                f"{catalog_path}: {error}"
            )

    # Select the latest BIOS for each requested model.

    latest = {}

    for component in all_components:

        for model_name in component["models"]:

            current = latest.get(model_name)

            if current is None:

                latest[model_name] = component

                continue

            new_rank = (
                component["version_key"],
                component["date_key"]
            )

            old_rank = (
                current["version_key"],
                current["date_key"]
            )

            if new_rank > old_rank:
                latest[model_name] = component

    return latest


# ------------------------------------------------------------
# Display results
# ------------------------------------------------------------

def print_results(results, requested_models):

    print("\n" + "=" * 115)
    print("LATEST DELL BIOS VERSIONS")
    print("=" * 115)

    print(
        f"{'MODEL':30} "
        f"{'VERSION':18} "
        f"{'RELEASE DATE':16} "
        f"{'BIOS PACKAGE'}"
    )

    print("-" * 115)

    for model_name in requested_models:

        item = results.get(model_name)

        if not item:

            print(
                f"{model_name:30} "
                f"{'NOT FOUND':18}"
            )

            continue

        filename = os.path.basename(
            urllib.parse.urlparse(
                item["url"]
            ).path
        )

        print(
            f"{model_name:30} "
            f"{item['version'][:18]:18} "
            f"{item['release_date'][:16]:16} "
            f"{filename}"
        )

    print("-" * 115)

    print(
        f"Models with BIOS entries: "
        f"{len(results)} / {len(requested_models)}"
    )

    print("=" * 115)


# ------------------------------------------------------------
# BIOS downloads
# ------------------------------------------------------------

def download_bios_files(results, requested_models):

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    downloaded_urls = set()

    for model_name in requested_models:

        item = results.get(model_name)

        if not item:
            continue

        url = item["url"]

        # Skip duplicate URLs during this run.
        if url in downloaded_urls:
            print(f"\nSkipping duplicate package for {model_name}")
            continue

        downloaded_urls.add(url)

        filename = os.path.basename(
            urllib.parse.unquote(
                urllib.parse.urlparse(url).path
            )
        )

        if not filename:
            filename = "Dell_BIOS_Update.exe"

        # Original filename.
        destination = DOWNLOAD_DIR / filename

        # Hashed alternative, used if the original filename
        # is occupied by an empty file.
        digest = hashlib.sha1(
            url.encode("utf-8")
        ).hexdigest()[:8]

        hashed_destination = DOWNLOAD_DIR / (
            destination.stem
            + "_"
            + digest
            + destination.suffix
        )

        # Check BOTH possible filenames before downloading.
        existing_file = None

        if destination.exists() and destination.stat().st_size > 0:
            existing_file = destination

        elif hashed_destination.exists() and hashed_destination.stat().st_size > 0:
            existing_file = hashed_destination

        if existing_file:

            print("\n" + "=" * 75)
            print(f"Model:       {model_name}")
            print(f"BIOS:        {item['version']}")
            print(f"Release:     {item['release_date']}")
            print(f"Package ID:  {item['package_id']}")
            print(f"Existing:    {existing_file}")
            print("Status:      Already downloaded - skipping")
            print("=" * 75)

            continue

        # Use original filename unless it is occupied.
        if destination.exists():
            destination = hashed_destination

        print("\n" + "=" * 75)
        print(f"Model:       {model_name}")
        print(f"BIOS:        {item['version']}")
        print(f"Release:     {item['release_date']}")
        print(f"Package ID:  {item['package_id']}")
        print(f"Destination: {destination}")
        print("=" * 75)

        try:

            download_file(
                url,
                destination
            )

        except Exception as error:

            print(
                f"\nERROR downloading {filename}: {error}"
            )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Download the latest Dell BIOS packages "
            "using CatalogIndexPC.cab"
        )
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List models available in Dell's catalog"
    )

    parser.add_argument(
        "--filter",
        help="Filter model list by model name or System ID"
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Find BIOS versions without downloading BIOS packages"
    )

    parser.add_argument(
        "--models-file",
        default=str(MODELS_FILE),
        help="Path to models.txt"
    )

    args = parser.parse_args()

    if args.filter and not args.list_models:

        parser.error(
            "--filter can only be used with --list-models"
        )

    try:

        # Check cabextract availability.

        if not shutil.which("cabextract"):

            raise RuntimeError(
                "cabextract is not installed. "
                "Run: sudo dnf install cabextract -y"
            )

        WORK_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        # ------------------------------------------------
        # Download the index catalog.
        # ------------------------------------------------

        print("\nDownloading Dell catalog index:")
        print(INDEX_CAB_URL)

        index_cab = WORK_DIR / "CatalogIndexPC.cab"

        download_file(
            INDEX_CAB_URL,
            index_cab
        )

        # ------------------------------------------------
        # Extract index XML.
        # ------------------------------------------------

        index_dir = WORK_DIR / "index"

        index_xml = extract_cab_file(
            index_cab,
            index_dir,
            preferred_xml="CatalogIndexPC.xml"
        )

        # ------------------------------------------------
        # Parse index.
        # ------------------------------------------------

        index_models = parse_catalog_index(
            index_xml
        )

        print(
            f"\nFound {len(index_models)} "
            f"model/catalog entries in Dell's index."
        )

        if not index_models:

            raise RuntimeError(
                "No models found in CatalogIndexPC.xml. "
                "The Dell catalog format may have changed."
            )

        # ------------------------------------------------
        # List models if requested.
        # ------------------------------------------------

        if args.list_models:

            print("\nReading available Dell models...")

            list_catalog_models(
                index_models,
                args.filter
            )

            return 0

        # ------------------------------------------------
        # Load requested models.
        # ------------------------------------------------

        requested_models = load_models(
            args.models_file
        )

        print("\nModels selected for BIOS search:")

        for model in requested_models:
            print(f"  - {model}")

        # ------------------------------------------------
        # Find latest BIOS versions.
        # ------------------------------------------------

        results = find_latest_bios(
            index_models,
            requested_models
        )

        # ------------------------------------------------
        # Display results.
        # ------------------------------------------------

        print_results(
            results,
            requested_models
        )

        # ------------------------------------------------
        # Check-only mode.
        # ------------------------------------------------

        if args.check_only:

            print(
                "\nCheck-only mode: "
                "BIOS packages were not downloaded."
            )

            return 0

        # ------------------------------------------------
        # Download BIOS packages.
        # ------------------------------------------------

        print("\nStarting BIOS downloads...")

        download_bios_files(
            results,
            requested_models
        )

        print("\nBIOS download process completed.")

        return 0

    except KeyboardInterrupt:

        print("\nOperation cancelled.")

        return 130

    except Exception as error:

        print(f"\nERROR: {error}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
