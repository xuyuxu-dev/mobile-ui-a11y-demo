# Experiments

These scripts deliberately read from both packages: they measure one channel against the
other (PC-side `uiautomator dump` versus the on-device accessibility tree, and OCR recall
against accessibility text). They live outside `lint/` and `engine/` so the two packages keep
their one-way dependency on `adbkit`.

Each script documents the device-side prerequisite in its header. Neither changes device
settings on its own.