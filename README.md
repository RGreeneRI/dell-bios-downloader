# dell-bios-downloader
Python script to download the latest BIOS update for models listed in "models.txt".  Requires the "cabextract" package.

<code>
usage: dell-bios-downloader.py [-h] [--list-models] [--filter FILTER] [--check-only] [--models-file MODELS_FILE]
Download the latest Dell BIOS packages using CatalogIndexPC.cab
options:
  -h, --help            show this help message and exit
  --list-models         List models available in Dell's catalog
  --filter FILTER       Filter model list by model name or System ID
  --check-only          Find BIOS versions without downloading BIOS packages
  --models-file MODELS_FILE  Path to models.txt
</code>
