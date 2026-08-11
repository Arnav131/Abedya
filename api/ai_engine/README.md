# AI Engine Model Weights

This directory contains the password-strength model code used by Abhedya's AI engine.

## Current production model

The default model weights file is:

- `api/ai_engine/weights/password_rnn.pt`

This is the current production checkpoint for the password predictability engine.
The code loads this file by default when no explicit weight path is supplied and the legacy BiLSTM checkpoint is not being preferred.

## Legacy compatibility checkpoint

A legacy BiLSTM checkpoint is also included at the repo root:

- `bilstm_password_weights.pth`

This checkpoint is kept for backward-compatibility inference only. The `pytorch_model.py` loader detects it and will load it using the compatibility wrapper `PasswordBiLSTMCompat` when:

1. the environment variable `ABHEDYA_PASSWORD_MODEL_WEIGHTS` is not set, or
2. the environment variable is explicitly set to the default `api/ai_engine/weights/password_rnn.pt` path.

That means if `bilstm_password_weights.pth` exists in the repo root, it may become the active model even without an explicit custom weights path.

## Weight path resolution behavior

The code determines which weights file to use in `_resolve_weights_path()`:

- If a `weights_path` argument is passed directly, it is used.
- Otherwise, if `ABHEDYA_PASSWORD_MODEL_WEIGHTS` is set, that path is used.
- If the legacy file `bilstm_password_weights.pth` exists and no custom path is provided, the legacy file is preferred over the default `password_rnn.pt` file.
- If the env var points exactly to the default `password_rnn.pt` path and the legacy file exists, the legacy file is also preferred.
- If neither the legacy file nor an env override is used, the loader falls back to `api/ai_engine/weights/password_rnn.pt`.

## Recommendation

For production, the intended current model is `api/ai_engine/weights/password_rnn.pt`.
If you want to force the current model regardless of the legacy checkpoint, set `ABHEDYA_PASSWORD_MODEL_WEIGHTS` to the current `password_rnn.pt` path explicitly, or remove the legacy root checkpoint from the deployment environment.
