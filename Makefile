.PHONY: test upload

test:
	@echo "Running doctests and unittests: nose must be installed"
	nosetests -v --with-doctest --where eof


REPO?=pypi
upload:
	rm -rf dist
	python setup.py sdist
	twine upload dist/*.tar.gz -r $(REPO)
