# Third-party notices

The root LICENSE covers original contributions by XuYangzitai. Vendored code retains its original authorship and licenses.

## STARQUERY / starcatalogquery

- Source: https://github.com/lcx366/STARQUERY
- Copyright (c) 2023-2025 Chunxiao Li
- License: [MIT](licenses/STARQUERY-MIT.txt)
- Location: `starlib/starcatalogquery/`

This repository retains a locally adapted, legacy rectangular CSV-tile implementation. Its exact original upstream revision is unknown; it is not a copy of the current upstream release. Local changes include Windows path handling, simplified CSV loading, catalog filename-prefix detection, magnitude/epoch parsing, local 2MASS H-band metadata, optional HEALPix imports, synthetic demo metadata and empty-tile handling. Do not replace this directory with the latest PyPI package without checking format compatibility.

## Astroalign-derived routines

- Source: https://github.com/toros-astro/astroalign
- Copyright (c) 2016 Martin Beroiz
- License: [MIT](licenses/ASTROALIGN-MIT.txt)
- Location: `starlib/starcatalogquery/invariantfeatures.py`, which identifies its routines as modified Astroalign code.

The notice is preserved from the locally supplied Astroalign implementation. This repository does not include the separate star-matching or source-extraction packages.

## Catalog data

No real catalogs or experimental images are distributed. The demo generator creates synthetic coordinates and magnitudes, not an astronomical catalog. Users obtain real catalogs separately and retain their source acknowledgements and applicable terms.
