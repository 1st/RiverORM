# Initial full setup
.PHONY: setup
setup: install-sys-deps install-python install-python-deps

.PHONY: install-sys-deps
install-sys-deps:
	curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment using uv (if not exists)
.PHONY: install-python
install-python:
	@if [ -d ".venv" ]; then \
		echo "Virtual environment already exists. If you want to recreate it, delete .venv first."; \
		read -p "Do you want to delete the existing .venv directory? (Y/n): " answer; \
		if [ "$$answer" = "Y" ] || [ "$$answer" = "y" ]; then \
			rm -rf .venv; \
			echo "Deleted .venv directory."; \
			uv venv .venv; \
		fi \
	else \
		uv venv .venv; \
	fi


# Install all dependencies using uv
.PHONY: install-python-deps
install-python-deps:
	uv sync

# Run tests using pytest
.PHONY: test
test:
	.venv/bin/pytest

# Run code checks (linting and formatting)
.PHONY: lint
lint:
	.venv/bin/ruff check
	.venv/bin/ruff format --check
