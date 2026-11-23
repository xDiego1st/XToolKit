# Historical Windows shortcuts (not the supported launcher)

These batch files are preserved only for compatibility with the original author's workflow. **Do not use them as the normal installation or checkout entrypoint.** Use [`run-all.ps1`](../../run-all.ps1) from the repository root instead.

- `00-environment-check.bat` and `01-list-offers.bat` are diagnostic/offer-listing shortcuts, although the historical offer-listing script includes `--force` and bypasses the intended account check.
- `02-*.bat` through `05-*.bat` may open **real Google Play subscription checkout** and invoke `--force` to bypass account verification. They are **not safe examples to run casually**. The historical 12+6+6 claim is unverified.
- File locations changed in the development branch. Each batch file now changes its working directory to the repository root before invoking the unchanged Python engine, so direct execution from this folder still resolves `ultra0.py`.

See [historical step mapping](../../docs/ORIGINAL-STEPS.md) and [security guidance](../../SECURITY.md). Do not publish Android credentials, OTPs, account reports, payment details or purchase tokens.
