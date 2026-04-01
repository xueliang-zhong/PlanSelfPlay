root := justfile_directory()

default: install

install:
  {{root}}/psp --install

test: lint
  python3 -m unittest {{root}}/tests/test_psp.py -v

lint:
  python3 -m py_compile {{root}}/psp && echo "psp: OK"
