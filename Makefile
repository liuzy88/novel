VENV := .venv
PYTHON := python3

all:
	@if [ ! -d "$(VENV)" ]; then \
		$(PYTHON) -m venv $(VENV); \
		. $(VENV)/bin/activate && pip install --upgrade pip && pip install edge-tts pydub simpleaudio; \
	fi; \
	. $(VENV)/bin/activate && python main.py 长夜难明.txt
