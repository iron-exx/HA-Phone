# HA-Phone

**Full-featured SIP PBX for Home Assistant** — powered by Asterisk 22.x LTS, managed entirely through a modern web UI. No command line required.

## Features

- **Any SIP trunk** — works with all standard SIP providers (Telekom, Vodafone, 1&1, Sipgate, Deutsche Glasfaser, and many more)
- **IP phones & softphones** — any SIP-compatible device: desk phones (Grandstream, Snom, Yealink), Android/iOS softphones (Linphone, Zoiper, Acrobits)
- **SIP video doorbells** — Akuvox and other SIP-capable intercoms
- **Web admin UI** — dark-theme dashboard with live status, no SSH or config files needed
- **Extensions** — internal SIP extensions with auto-generated passwords
- **Call routing** — time-based routing, ring groups, voicemail
- **In-app updates** — update directly from the UI via Home Assistant Supervisor

## Installation

1. Add this repository in HA → Add-on Store → Repositories:
   ```
   https://github.com/iron-exx/HA-Phone
   ```
2. Install **HA-Phone** and start it.
3. Open the UI via the sidebar — default password: `changeme` (change on first login).

## Documentation

See [DOCS.md](DOCS.md) for network setup, SIP trunk configuration, and softphone guides.

## Support

[github.com/iron-exx/HA-Phone/issues](https://github.com/iron-exx/HA-Phone/issues)

## License

Copyright (C) 2026 Sandro Ahrens. All Rights Reserved. HA-Phone's own code
(backend, frontend, add-on config, templates) is source-available for viewing
only — no license to use, copy, modify, or distribute it, commercially or
otherwise, is granted. See [LICENSE](LICENSE) for details.

The container image bundles **Asterisk** (GPLv2, © Sangoma Technologies), built
from the official source at downloads.asterisk.org. Asterisk runs as a separate
process — HA-Phone talks to it only via AMI and generated config files (mere
aggregation), and remains under its own GPLv2 terms regardless of the above.
Other bundled components (FastAPI, React, …) keep their own licenses. See
[LICENSE](LICENSE) for details.
