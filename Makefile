BUILD_DIR = bin
SRC_DIR = insar
CC = gcc
CFLAGS = -g -Wall -std=gnu99 -O3
MKDIR_P = mkdir -p

# TARGET = $(BUILD_DIR)/upsample

#SRC = $(SRC_DIR)/upsample.c
# SRCS = $(wildcard $(SRC_DIR)/*.c)
# OBJS = $(patsubst %.c, $(BUILD_DIR)/%.o, $(wildcard $(SRC_DIR)/*.c))

# default: $(TARGET)
# all: default
all: build


$(TARGET): $(SRC)
	$(CC) $(SRC) $(CFLAGS) -o $@


.PHONY: build test clean upload

build:
	python setup.py build_ext --inplace

test:
	@echo "Running doctests and unittests: nose must be installed"
	nosetests -v --with-doctest

clean:
	rm -f *.o
	rm -f $(TARGET)

REPO?=pypi
upload:
	rm -rf dist
	python setup.py sdist
	twine upload dist/*.tar.gz -r $(REPO)
