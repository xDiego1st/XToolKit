# Optional Windows setup shortcuts

The current launcher is [`run-all.ps1`](../../run-all.ps1) at the repository root. It automatically detects and prepares the required dependencies when you run a check; **manual setup is optional**.

[`setup-environment.bat`](setup-environment.bat) remains available for troubleshooting an existing Windows/MuMu environment. It moves to the repository root before calling `setup_env.py`, preserving its original behavior.

Environment preparation can install or replace Frida/ADB tools and change Android emulator/network settings; it **does not guarantee zero side effects**. Do not run historical checkout shortcuts from [`legacy/windows/`](../../legacy/windows/README.md) for setup.

See [installation instructions](../../README.md) and [detailed troubleshooting](../../docs/DETAILED-GUIDE.md).
