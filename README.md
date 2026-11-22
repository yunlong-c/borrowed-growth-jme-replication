# Borrowed Growth — Replication Code

Empirical replication code for *Borrowed Growth: Employer-to-Employer Mobility,
Corporate Cash Flows, and Stock Returns*, covering 22 empirical tables and three figures.

## Run

Use Python 3.12. Obtain the inputs listed in the [data acquisition register](documentation/data_acquisition.csv),
place them at the specified paths, and run from the repository root:

```bash
python -m pip install -r requirements.txt
python run_all.py
```

## Data and documentation

Input datasets are obtained from their original providers under their applicable terms;
this repository distributes code and documentation only.

- [Replication guide](documentation/REPLICATION_GUIDE.md): setup, data versions, outputs and exhibit mapping.
- [Data availability](documentation/data_availability.md): source access and redistribution terms.

Section 5 calibration and simulation code will be deposited before publication.

Code: [MIT](LICENSE). Documentation: [CC BY 4.0](LICENSE-docs.md).
