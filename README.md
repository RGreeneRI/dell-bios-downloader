# dell-bios-downloader
The Dell BIOS Downloader is a Python-based utility that automatically retrieves the latest BIOS updates for a user-defined list (models.txt) of Dell computer models using Dell's regularly updated online catalogs. It identifies the appropriate BIOS version and release date for each model, displays the available updates, and can download the corresponding BIOS installer packages into a centralized directory. It supports multiple Dell product families, allows users to check BIOS versions without downloading installers, and can search the catalog for available models. The script also avoids redundant downloads by recognizing previously downloaded files, prevents duplicate downloads when multiple models share the same BIOS package, and maintains existing downloads rather than overwriting them. By automating the process of locating, comparing, and collecting BIOS updates, it makes maintaining a collection of current Dell BIOS installers faster, easier, and more consistent. 

Requires the "cabextract" package.
```
usage: dell-bios-downloader.py [-h] [--list-models] [--filter FILTER] [--check-only] [--models-file MODELS_FILE]
Download the latest Dell BIOS packages using CatalogIndexPC.cab
options:
  -h, --help                 show this help message and exit
  --list-models              List models available in Dell's catalog
  --filter FILTER            Filter model list by model name or System ID
  --check-only               Find BIOS versions without downloading BIOS packages
  --models-file MODELS_FILE  Path to models.txt
```

Usage example:
```
$ python dell-bios-downloader.py --list-models --filter 7440

Downloading Dell catalog index:
https://downloads.dell.com/catalog/CatalogIndexPC.cab

Downloading:
https://downloads.dell.com/catalog/CatalogIndexPC.cab
Progress: 100.0%
Saved: /home/redacted/dell_bios_downloader/catalog_cache/CatalogIndexPC.cab

Extracting CatalogIndexPC.cab...

Reading Dell catalog index...

Found 1774 model/catalog entries in Dell's index.

Reading available Dell models...

===============================================================================================
DELL MODELS AVAILABLE IN CATALOG
===============================================================================================
MODEL NAME                                       SYSTEM ID       CATALOG ENTRIES
-----------------------------------------------------------------------------------------------
7440 AIO                                         06C5            1
E7440                                            05CB            1
Inspiron 14 7440 2-in-1                          0CA7            1
Inspiron 14 Plus 7440                            0C93            1
Inspiron 14 Plus 7440                            0CCA            1
Inspiron 14 Plus 7440                            0CCE            1
Latitude 7440                                    0C0B            1
Latitude 7440                                    0C0C            1
Latitude 7440                                    0C0D            1
-----------------------------------------------------------------------------------------------
Total model/System ID combinations: 9
===============================================================================================

```
