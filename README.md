# Utilities Receipt Importer

```
python -m venv ./venv
. ./venv/bin/activate
find . -name requirements.txt | while read file; do \
    pip install -r $file && \
    export PYTHONPATH=$PYTHONPATH:${file%/*}; \
done
```
