.PHONY: all build install test test-unit test-integration test-smoke test-terminal run clean help

ZIG ?= zig
PYTHON ?= python3
OPTIMIZE ?= ReleaseFast
PREFIX ?= $(HOME)/.local
BINDIR ?= $(PREFIX)/bin
BIN := zig-out/bin/gitdlg

all: build

build:
	$(ZIG) build -Doptimize=$(OPTIMIZE)

install: build
	mkdir -p $(BINDIR)
	cp $(BIN) $(BINDIR)/gitdlg
	chmod 755 $(BINDIR)/gitdlg

test: test-unit test-integration test-smoke test-terminal

test-unit:
	$(ZIG) build test

test-integration:
	./scripts/integration-test.sh

test-smoke:
	$(PYTHON) scripts/tui-smoke-test.py

test-terminal:
	$(PYTHON) scripts/terminal-app-compat-test.py

run: build
	$(ZIG) build run --

clean:
	rm -rf zig-out .zig-cache

help:
	@echo "Targets:"
	@echo "  make build             Build release binary"
	@echo "  make install           Install to $(BINDIR)"
	@echo "  make test              Run all tests"
	@echo "  make test-unit         Run Zig unit tests"
	@echo "  make test-integration  Run integration test"
	@echo "  make test-smoke        Run TUI smoke test"
	@echo "  make test-terminal     Run Terminal.app compatibility test"
	@echo "  make run               Build and run gitdlg"
	@echo "  make clean             Remove build output"
