<img width="1254" height="1254" alt="WhatsApp Image 2026-06-30 at 11 43 06" src="https://github.com/user-attachments/assets/eccec6b3-ec21-4e7a-8307-a48dbea1b438" />



HA-Phone
Full-featured SIP PBX for Home Assistant — powered by Asterisk 22.x LTS, managed entirely through a modern web UI. No command line required.

Features
Any SIP trunk — works with all standard SIP providers (Telekom, Vodafone, 1&1, Sipgate, Deutsche Glasfaser, and many more)
IP phones & softphones — any SIP-compatible device: desk phones (Grandstream, Snom, Yealink), Android/iOS softphones (Linphone, Zoiper, Acrobits)
SIP video doorbells — Akuvox and other SIP-capable intercoms
Web admin UI — dark-theme dashboard with live status, no SSH or config files needed
Extensions — internal SIP extensions with auto-generated passwords
Call routing — time-based routing, ring groups, voicemail
In-app updates — update directly from the UI via Home Assistant Supervisor
Installation
Add this repository in HA → Add-on Store → Repositories:
https://github.com/iron-exx/HA-Phone
Install HA-Phone and start it.
Open the UI via the sidebar — default password: changeme (change on first login).
Documentation
See DOCS.md for network setup, SIP trunk configuration, and softphone guides.

Support
github.com/iron-exx/HA-Phone/issues

License
HA-Phone's own code (backend, frontend, add-on config, templates) is released under the MIT License.

The container image bundles Asterisk (GPLv2, © Sangoma Technologies), built from the official source at downloads.asterisk.org. Asterisk runs as a separate process — HA-Phone talks to it only via AMI and generated config files (mere aggregation). Other bundled components (FastAPI, React, …) keep their own licenses. See LICENSE for details.


Dashboard:
<img width="1633" height="1271" alt="image" src="https://github.com/user-attachments/assets/3801f7fc-cb4c-49d4-bd36-1c823fedb6c3" />
