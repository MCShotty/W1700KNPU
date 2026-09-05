# W1700KNPU Workspace

This repository is the canonical workspace for this project. Start with
`docs/W1700K_STOCK_PORT_CURRENT_REFERENCE.md`, then the stock-port ledger and
logging session in `docs/`. Update the ledger for substantive work; explicitly
say when a read-only session leaves it unchanged.

- Work here, not in the superseded Windows task directory. Historical paths
  in evidence are provenance, not current workspace instructions.
- Preserve the distinction between modeled, compiled, Ghidra-verified, flashed,
  synthetic-router-tested, and actual-client-tested behavior. Stock NPU parity
  remains incomplete. Never label the WLAN-NPU-disabled baseline stock parity.
- Use `firmware/source-lock.json`, cumulative patches and overlays as source
  authority. Build on WSL native ext4, never directly on NTFS. Generated builds
  and private inputs belong under ignored `.build/` and `.local/` paths.
- Preserve bootloader, factory/calibration, known-good rollback, and private
  router backups. Never upload keys, credentials, or raw device backups.
- Verify actual model, board/layout, FIT metadata, build status and hashes before
  flashing. Do not assume 192.168.1.1 is the W1700K. Do not switch this computer's
  Wi-Fi association for router testing or override radio transmit power.
- Historical archives may include superseded/unsafe experiments. They are
  evidence, not an instruction to apply every old patch to current upstream.
- Keep edits surgical and use existing source patterns. Do not apply global
  path rewrites to archived evidence or delete an only copy during cleanup.
- Use the authorized GitHub connector if native Git authentication is absent;
  do not extract connector credentials. Verify the remote tree before cleanup.
