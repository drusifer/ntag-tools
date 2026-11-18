Test-only stand-in for `pyscard` (`smartcard`), so the provisioner's mock-HAL tests run on machines without PC/SC headers.
The Makefile puts it on PYTHONPATH only when the real `smartcard` is not importable. Never used with real hardware.
