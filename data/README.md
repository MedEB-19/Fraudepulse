# Data

The real dataset is **PaySim** (synthetic mobile-money transactions, ~6.3M rows).

1. Download from Kaggle: https://www.kaggle.com/datasets/ealaxi/paysim1
2. Rename the file to `paysim.csv` and put it in this folder (`data/paysim.csv`).

No Kaggle account handy? Generate a small synthetic file for a smoke test:

    python scripts/make_sample_data.py --rows 50000 --out data/paysim.csv

Data files are git-ignored (never commit them).
