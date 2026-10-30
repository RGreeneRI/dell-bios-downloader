# dell-bios-downloader
The Dell BIOS Downloader is a Python-based utility that automatically retrieves the latest BIOS updates for a user-defined list (models.txt) of Dell computer models using Dell's regularly updated online catalogs. It identifies the appropriate BIOS version and release date for each model, displays the available updates, and can download the corresponding BIOS installer packages into a centralized directory. It supports multiple Dell product families, allows users to check BIOS versions without downloading installers, and can search the catalog for available models. The script also avoids redundant downloads by recognizing previously downloaded files, prevents duplicate downloads when multiple models share the same BIOS package, and maintains existing downloads rather than overwriting them. By automating the process of locating, comparing, and collecting BIOS updates, it makes maintaining a collection of current Dell BIOS installers faster, easier, and more consistent. 

Requires the "cabextract" package.

<code>usage: dell-bios-downloader.py [-h] [--list-models] [--filter FILTER] [--check-only] [--models-file MODELS_FILE]
Download the latest Dell BIOS packages using CatalogIndexPC.cab
options:
  -h, --help                 show this help message and exit
  --list-models              List models available in Dell's catalog
  --filter FILTER            Filter model list by model name or System ID
  --check-only               Find BIOS versions without downloading BIOS packages
  --models-file MODELS_FILE  Path to models.txt
</code>
