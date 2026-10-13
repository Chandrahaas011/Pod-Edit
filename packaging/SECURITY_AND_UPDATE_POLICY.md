# PodEdit Windows security and update policy

## Installation boundary

PodEdit uses a per-user install under `%LOCALAPPDATA%\Programs\PodEdit`; it does
not require elevation. Mutable settings live under
`%LOCALAPPDATA%\PodEdit\settings`, and a provisioned model may live under
`%LOCALAPPDATA%\PodEdit\models`. User-selected jobs can be anywhere writable.
Uninstall must preserve settings, models, and user jobs unless a separate,
explicit cleanup action identifies exact paths and reports what will be lost.

## Model distribution boundary

The internal prototype contains the gated Community-1 weights only to validate
offline operation. The repository snapshot does not contain affirmative model
redistribution permission. Public installers therefore exclude `.model_cache`
by default. `INTERNAL_OFFLINE_BUILD` in `PodEdit.iss` must not be enabled until
redistribution rights and required notices are documented. A public build also
needs a supported first-run provisioning/import flow before it is usable.

## Signing and integrity

Release executables and the installer must be Authenticode-signed with a
trusted organization certificate and timestamped. Signing occurs after bundle
audit and before publishing. The signed folder is rehashed; signatures and
hashes are checked on a clean VM. Unsigned local prototypes must say so and are
never promoted through the stable update channel.

## Updates and rollback

- Stable and beta are separate opt-in channels.
- Update metadata is HTTPS-delivered, signed, and contains version, minimum
  compatible schema, SHA-256, size, and release-notes URL.
- Downloads go to a staging folder and are hash/signature verified before run.
- Jobs are never migrated destructively. Settings migrations are atomic and
  retain a prior-version backup.
- Downgrade remains possible while the stored settings schema is compatible;
  otherwise the application explains the conflict and preserves both copies.
- PodEdit does not self-update during an active processing job.

No updater or network model provisioner is implemented in 1.4. These rules are
acceptance criteria, not claims that the unsigned prototype already satisfies
public-release security.
