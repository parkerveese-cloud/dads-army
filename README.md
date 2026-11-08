# Dads Army: home front stores

A stores tracker for food, water and emergency kit. It runs on a Raspberry Pi or a Home Assistant box on your home network, and it's built to be used from your phone.

- **Sitrep:** how many days the household could hold out, whether food or water runs out first, what's expired or expiring soon, and what to use first.
- **Stores:** everything you hold, grouped by category, with search and filters. Tap **−** to use one or **+** to add stock.
- **Batches and rotation:** the same item can have several batches with different best-before dates and locations. Using stock always takes the oldest first.
- **Supply run:** an automatic shopping list of everything below target, plus your own extras. **Got it** puts the shopping straight into the stores.
- **HQ:** household size, calorie and water needs, readiness target (3 days to a year), backups, a printed hard copy, a starter list of about 95 essentials, light/dark mode, and the activity log.
- **Undo** on anything you use or delete. Several phones can use it at once.

It needs no internet to run. Nothing leaves your network.

---

## Install on Home Assistant (recommended)

[![Add the repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fparkerveese-cloud%2Fdads-army)

Or add it by hand:

1. Go to **Settings → Apps** (called Add-ons in older versions) and open the store.
2. Open the **⋮** menu → **Repositories**, add `https://github.com/parkerveese-cloud/dads-army`, then close the dialog.
3. Find **Dads Army** in the store and click **Install**. The first install takes a few minutes, because Home Assistant builds it on your machine.
4. On the app's Info page, turn on **Show in sidebar** and click **Start**.

You can then open it in two ways:

- **Dads Army** in the Home Assistant sidebar. This also works in the Companion app.
- `http://<home-assistant-address>:8080` in your phone's browser. Use **Add to Home Screen** to give it its own app icon.

**Updates** appear in **Settings → Updates**, like any other app. Home Assistant shows what's changed and can take a backup before updating. Your data is kept, and it's included in your Home Assistant backups.

## Install on Raspberry Pi OS

You need Raspberry Pi OS (Bookworm or Bullseye) with Python 3.7 or newer, which is already installed.

```bash
git clone https://github.com/parkerveese-cloud/dads-army.git
cd dads-army
bash install.sh
```

The installer:

- puts the app in `~/dadsarmy`
- starts it on every boot
- prints the address to open on your phone, such as `http://raspberrypi.local:8080`

To update, run `git pull` and then `bash install.sh` again. Your data is kept.

> **Tip:** the `.local` name doesn't work on every Android phone. Reserve a fixed IP address for the Pi in your router (look for "DHCP reservation") and bookmark `http://<that-ip>:8080`.

| What | Command |
|---|---|
| Is it running? | `systemctl status dadsarmy` |
| Restart it | `sudo systemctl restart dadsarmy` |
| Watch the log | `sudo journalctl -u dadsarmy -f` |
| Use a different port | `DADSARMY_PORT=8081 bash install.sh` |
| Uninstall | `sudo systemctl disable --now dadsarmy && sudo rm /etc/systemd/system/dadsarmy.service` |

## First steps

1. **HQ:** set how many adults and children you're feeding, and your readiness target.
2. **Load the starter list.** Targets are sized for your household when you load it, so do step 1 first.
3. Do a stock-take, cupboard by cupboard. In **Stores**, tap **+** on each item and enter how many, the best-before date and where it's kept.
4. Add **calories per unit** to food items so the Sitrep can work out how many days you'd last. **Work it out from the label** does the sum from kcal per 100g × weight.
5. Use the **Supply run** tab as your shopping list.

## Backups and the paper copy

- **Automatic:** once a day, Dads Army saves a copy of its database and keeps the last 14.
- **Download a backup:** HQ → **Download backup** saves a `.json` file to your phone. HQ → **Restore from a backup…** brings it back.
- **Spreadsheet:** HQ → **Export spreadsheet (CSV)**.
- **Print it:** HQ → **Print full inventory** gives a paper list with a tick column. Keep it with the stores, in case the power or the Pi goes down.

## Security

Dads Army has no login of its own. Anyone on your home network who can reach port 8080 can open it. Through the Home Assistant sidebar, only signed-in Home Assistant users can open it. **Don't** port-forward 8080 on your router. To reach it while you're out, use Home Assistant Cloud, Tailscale or WireGuard.

---

## Releasing an update

1. Make the changes in `dadsarmy/`.
2. Raise the version number in both `dadsarmy/config.yaml` and `VERSION` in `dadsarmy/server.py`.
3. Add an entry at the top of `dadsarmy/CHANGELOG.md`. Home Assistant shows it in the update dialog.
4. Commit, tag (`git tag v1.2.0`) and push, including the tag.

Home Assistant checks for updates on its own. To check straight away, use **Settings → Updates → ⋮ → Check for updates**.

## How it's built

- `dadsarmy/server.py`: one Python file using only the standard library (`http.server` and `sqlite3`), so there's nothing to `pip install`.
- `dadsarmy/static/`: the phone app, in plain HTML, CSS and JavaScript. There's no build step, and nothing is loaded from the internet.
- `dadsarmy/config.yaml` and `Dockerfile`: the Home Assistant app definition.
- Your data lives in a single SQLite file, `dadsarmy.db`. On Raspberry Pi OS it's in `~/dadsarmy/data`; on Home Assistant it's in the app's own storage.

*Don't panic.*
