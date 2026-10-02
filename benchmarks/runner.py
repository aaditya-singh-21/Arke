"""Installed CLI wrapper; all runs remain explicit."""
from voice_translator.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["benchmark", *__import__("sys").argv[1:]]))

