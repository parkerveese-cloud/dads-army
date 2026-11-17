# Dads Army: home front stores

A stores tracker for food, water and emergency kit. It runs on a Raspberry Pi or a Home Assistant box on your home network, and it's built to be used from your phone.

- **Sitrep:** how many days the household could hold out, whether food or water runs out first, what's expired or expiring soon, and what to use first.
- **Stores:** everything you hold, grouped by category, with search and filters. Tap **−** to use one or **+** to add stock. **Select to delete** clears out things you don't want to keep, several at a time.
- **Batches and rotation:** the same item can have several batches with different best-before dates and locations. Using stock always takes the oldest first.
- **Daily use:** say how many tablets, nappies or toilet rolls you get through a day, and Dads Army shows how long each will last and what runs out first. It also notices how fast you really use things: "about 2 tins a week, lasts 6 weeks".
- **Pets:** dogs, cats and other pets, with their water counted in the household's and their food's own days.
- **Supply run:** an automatic shopping list of everything below target, plus your own extras. **Got it** puts the shopping straight into the stores. Set prices to see what it'll cost and what the stores are worth.
- **Resilience:** ten areas, of which food and water are two. Power and light, communications, warmth, health, safety and more each have a score, and there are about 65 recommendations (a UPS for the router, a battery or wind-up radio, numbers on paper, smoke and CO alarms…). Most come from the UK Government's Be Ready checklist, Ofcom and Fire Kills. Dads Army ticks off what it can see in your stores and plan, and you tick the rest.
- **Places to go:** if staying at home isn't safe, where to go for each kind of emergency (flooding, storms, a wildfire, an earthquake, civil unrest, heat, cold, having to leave), from a list of about 58,000 UK places that comes with the app: high ground, leisure centres, community halls, libraries, hospitals. Add your own places too, like family and friends. Shown on a map on the Home front dashboard.
- **Household alert level:** LOW to CRITICAL, using the UK's own threat-level names. It's worked out from warnings, your stores and your home's sensors (temperatures, power, gas, CO and smoke alarms, leaks and more), with plain, labelled advice on what to do. That advice comes from UK Government sources and the SAS Survival Handbook's PLAN priorities. Missing essentials keep it at MODERATE.
- **Warnings (optional):** Met Office weather warnings, flood warnings near you, UK Emergency Alerts and major disasters near the UK. Optionally, possible fires near you seen by NASA satellites, and UK Health Security Agency and WHO news. Each comes with what to do, and the parts of your emergency plan that matter.
- **The wider picture (with warnings):** river levels near you against their normal range, power cuts nearby, electricity grid notices, gas storage, air quality, space weather and the pound, with warnings when something's up and two-week trends ("gas storage emptying faster than last year").
- **Trends:** charts of how many days the food and water would last, and of resilience, day by day.
- **Wall tablets:** on a wide screen the tabs move to the side, the cards flow into columns, and the stores become a sortable table.
- **Plan:**
  - **Routine checks:** test the smoke alarms, charge the power banks, rotate the water. Dads Army tells you when each is due.
  - **Household emergency plan:** contacts, meeting places, how to turn off the water, gas and electricity, and medical needs. It's ready to print for the grab bag.
- **HQ:** household size and pets, calorie and water needs, readiness target (3 days to a year), expiry warnings (earlier for medicines, if you like), backups, a printed hard copy, a starter list of about 95 essentials whose targets follow the household, light/dark mode, and the activity log.
- **Undo** on anything you use or delete. Several phones can use it at once, and an undo never overwrites a newer change made on another one.

It needs no internet to run, and nothing about you leaves your network. Place data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (see [dadsarmy/places](dadsarmy/places/README.md)). It uses the internet if you switch on warnings, and then it just downloads the public feeds: each is the whole country in one go, and Dads Army works out what's near you itself. If you scan, a new barcode is looked up in Open Food Facts (only the barcode is sent; or switch on the offline UK list, downloaded once a month), and a photo of a best before date or label goes to the AI you choose (Home Assistant's own, or one with your key). If you ask for a stores review, your item names and amounts go to that AI too.

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

**Working with Home Assistant:**

- **Dashboard.** Dads Army publishes `sensor.dads_army_*` entities to Home Assistant, covering:
  - readiness against your target
  - hold-out days
  - out of stock and running low
  - expired and expiring soon
  - the supply run
  - checks due
  - daily supplies
  - what the stores are worth
  - warnings in force
  - the household alert level
  - resilience, area by area
  - places to go, for the map
  - the wider picture: rivers, power cuts, the grid, gas, air, space weather and the pound

  You can use them on dashboards, in automations and in Companion app widgets.
- **Home front dashboard.** One tap in **HQ → Home Assistant** adds a ready-made dashboard to the Home Assistant sidebar, made of tiles. It covers the alert level, warnings, the wider picture, today's checklist, resilience, the stores, the supply run and a map of places to go. A card for your own dashboards is on the app's **Documentation** tab.
- **Today's checklist.** Routine checks that are due go on a Home Assistant to-do list. Tick them off there and Dads Army marks them done.
- **Phone alerts.** Two blueprints in [blueprints/automation](blueprints/automation) send notifications to your phone:
  - new warnings for where you live
  - when something runs out
  - each morning, anything that went out of date overnight and any check that's due
  - a weekly round-up of what to use first
- **To-do list.** The supply run can stay in step with a Home Assistant to-do list. You can tick things off there and add to it by voice. Turn it on in **HQ → Home Assistant**.

The details are in [DOCS.md](dadsarmy/DOCS.md). Outside Home Assistant, `GET /api/summary` returns the same figures as JSON.

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
- **Print it:** HQ → **Print full inventory** gives a paper list with a tick column. Keep it with the stores, in case the power or the Pi goes down. **Print emergency plan & checks** does the same for the plan.

## Security

Dads Army has no login of its own. Anyone on your home network who can reach port 8080 can open it. Through the Home Assistant sidebar, only signed-in Home Assistant users can open it. **Don't** port-forward 8080 on your router. To reach it while you're out, use Home Assistant Cloud, Tailscale or WireGuard.

## Credits

Dads Army is built by people who want households across the UK to be ready for whatever comes. Their names are in [`dadsarmy/CREDITS.md`](dadsarmy/CREDITS.md), and the app shows them under Help → **Credits**.

To add a name, or change the thank-you message, edit `CREDITS.md` on GitHub. Notes at the top of the file explain the layout. The app picks up the change with its next update, or straight away when someone taps **Check GitHub for new names**.

**New contributors are added for you.** After every push to `main`, a GitHub Action (`.github/workflows/credits.yml`) runs `tools/update_credits.py`:

- **Who it finds:** everyone in the history, as an author or a `Co-authored-by`.
- **What it adds:** anyone not yet named, under **Built by**, as "Name (@github-name): contributed code". It then commits the file.
- **What it leaves alone:**
  - anyone already named, by GitHub name or by name
  - commits that only change `CREDITS.md`
  - bots and AI coding assistants
  - email addresses, which are never written

You can change the words after a name; nobody is added twice. If one person shows up under two names, join them up with a [`.mailmap`](https://git-scm.com/docs/gitmailmap) file. To see who it would add, run `python3 tools/update_credits.py --check`.

---

## Releasing an update

Home Assistant offers an update as soon as the version in `dadsarmy/config.yaml` changes on `main`. So any change that raises the version is a release, whether it's pushed or merged from a pull request.

1. Pull first (`git pull --rebase`): the credits workflow may have added names on GitHub. Then make the changes in `dadsarmy/`.
2. Raise the version number in both `dadsarmy/config.yaml` and `VERSION` in `dadsarmy/server.py`.
3. Add an entry at the top of `dadsarmy/CHANGELOG.md`. Home Assistant shows it in the update dialog.
4. Commit and push, or merge the pull request.

There's no need to tag it. A GitHub Action (`.github/workflows/release.yml`) checks that the three versions agree and tags the release on `main` as `v1.2.0`, with its changelog entry as the message. It checks every pull request too, so a mismatch shows before it's merged. To check by hand, run `python3 tools/release_check.py`.

**Pull requests:** the template asks contributors to raise the version and add a changelog entry, so merging their pull request is the release. If one changes the app without raising the version, merging it releases nothing until someone does.

Home Assistant checks for updates on its own. To check straight away, use **Settings → Updates → ⋮ → Check for updates**.

## How it's built

- `dadsarmy/server.py`: one Python file using only the standard library (`http.server` and `sqlite3`), so there's nothing to `pip install`.
- `dadsarmy/static/`: the phone app, in plain HTML, CSS and JavaScript. There's no build step, and nothing is loaded from the internet. `zxing.min.js` is the [ZXing](https://github.com/zxing-js/library) barcode reader (0.21.3, MIT licence), loaded only when you scan.
- `dadsarmy/places/uk.tsv.gz`: the list of UK places for **Places to go**. It's built from an OpenStreetMap extract by `tools/build_places.py`, which needs [pyosmium](https://osmcode.org/pyosmium/). The app itself only reads the finished file.
- `dadsarmy/config.yaml` and `Dockerfile`: the Home Assistant app definition.
- `dadsarmy/CREDITS.md`: the thank-you and the names shown under Help → Credits, kept up to date by `tools/update_credits.py` and `.github/workflows/credits.yml`.
- `.github/workflows/release.yml` and `tools/release_check.py`: check the version on every pull request and push, and tag each release.
- `tests/`: about 130 tests of the server, backups, undo, Home Assistant sync and the feeds, using stand-ins for Home Assistant and the feeds, so they never touch the internet. Run them from the repository folder with `python3 -m unittest discover -s tests`.
- Your data lives in a single SQLite file, `dadsarmy.db`. On Raspberry Pi OS it's in `~/dadsarmy/data`; on Home Assistant it's in the app's own storage.

*Don't panic.*
