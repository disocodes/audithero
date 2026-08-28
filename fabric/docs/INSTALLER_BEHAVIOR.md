# Installer behavior

The Fabric installer is idempotent: it looks up existing items by type/display name, creates missing items, and updates definitions of existing managed items. Long-running REST operations are polled to completion. The Environment is published before notebooks run, and the monthly schedule is created/updated disabled unless explicitly enabled in configuration.