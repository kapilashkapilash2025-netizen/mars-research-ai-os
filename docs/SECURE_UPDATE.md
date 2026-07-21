# Secure Update Foundation

Updates validate a deterministic manifest digest placeholder, stage only the inactive A/B slot, then require
post-boot health confirmation. Failed confirmation rolls back without changing the active slot. Real signing,
key management, bootloader integration and flashing remain future hardware-specific work.
