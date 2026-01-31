# Security Policy & Implementation

## Credential Encryption

As of version 0.2.0, DBManager implements **transparent credential encryption** for all sensitive fields in the configuration.

### How it works
1. **Master Key**: A symmetric encryption key (Fernet/AES-128-CBC) is used to encrypt/decrypt sensitive data.
2. **Key Storage**: The key is stored in `~/.dbmanager/.secret.key` with strict file permissions (`600`).
3. **Transparent Usage**: The application automatically encrypts passwords when saving to `config.json` and decrypts them when loading into memory.
4. **Migration**: Existing plaintext passwords in `config.json` will be automatically encrypted the next time the configuration is saved.

### Key Management
If you need to move the configuration to another server, you **MUST** also move the `.secret.key` file, or set the `DBMANAGER_MASTER_KEY` environment variable.

#### Using Environment Variable
You can override the key file by setting:
```bash
export DBMANAGER_MASTER_KEY="your-base64-encoded-32-byte-key"
```

To generate a new key:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### Encrypted Fields
The following fields are automatically encrypted:
- `password` (database passwords)
- `smtp_password` (email)
- `aws_secret_access_key` (S3)
- `secret_key` (generic)
- `webhook_url` (Slack/Teams/Discord)
- `connection_string`

## Configuration File Security
Even with encryption, you should protect your `config.json` file.
- Ensure `~/.dbmanager` directory has restricted permissions.
- Do not commit `config.json` or `.secret.key` to version control.
