# Changelog

## 1.19.0

**A map of the live alerts**

- **Off until you ask for it.** Tick **Show a map** in the warnings settings, under Map. Until then nothing changes: the map's code isn't loaded and no map pictures are asked for. The map pictures come from OpenStreetMap, loaded by your phone or browser: OpenStreetMap sees your IP address and the area you look at (the map opens on the area round home), and nothing else. The Pi fetches nothing new for it.
- **Home and your near you distance.** Home in the middle, with your near you distance as a dashed ring round it.
- **Each warning with a place** is a badge showing what it is (🔌 🚰 🌊 🏞️ 🔥), ringed in its colour: yellow, amber or red, as in the lists. Power cuts and water supply reports further out, the ones under *Nearby, not in your area*, are smaller and grey. Tap a badge for its details.
- **Routine things stay off** until you tap **Show routine** at the top left: planned power cuts and water company work, leaks, and river gauges at their usual level. Each phone or browser remembers which you chose.
- **The key under the map** only lists what's on it, and the routine entries only while they're shown. **🏠** goes back to home; **UK** appears when a warning is well outside the ring (**All**, if one is abroad).
- **Small credits** in the corner (OpenStreetMap contributors, and the sources on the map), so they never cover a button on a phone.
- The map is drawn by [Leaflet](https://leafletjs.com) 1.9.4 (BSD 2-Clause licence), which comes with the app: nothing is loaded from elsewhere.
- In `GET /api/state`, the warnings have `map` (`on`, `home`, `near_km` and `points`), and `map` in `config`. Power cut, water supply, high river and disaster warnings now carry the `lat` and `lon` the feeds gave, as flood warnings and fires already did. The web server's security policy lets OpenStreetMap's pictures in only while the map is on.

## 1.18.0

**Affecting you**

- **What's touching home comes first.** At the top of the wider picture on the Sitrep, each thing affecting your own area gets its own line: water off, a power cut, a flood warning, severe weather, a high river. Each says how serious it is, how far away, the postcodes a power cut covers, when it started or when power's expected back, and the first sentence of the details. The colour down its left side is how serious it is. Tap it for that source's details.
- **The same "yours" as the lines.** Affecting you is exactly the warnings behind a line turning amber or red, so a line never says all's well while Affecting you lists something from it. A power cut 6 km away, or another street's burst main, isn't a warning: it's listed underneath, more quietly, as **Nearby, not in your area** (the nearest three, and how many more).
- **When nothing is**, one calm line says so: *Nothing affecting you*.

**The wider picture, grouped**

- **Lines that need attention come first**, worst first. When none do, one line says *Nothing needs attention*.
- **The rest are under headings:** Water and weather, Power and energy, Home, and The wider world. The lines themselves are as before.

**Near you**

- **A "near you" distance** in the warnings settings, 5 to 40 km (10 km, as before, until you change it): how far power cuts and water supply reports are listed. It doesn't change what's a warning: a power cut within 2 km, or a supply problem the water company says is yours. Floods and fires keep their own distances. Changing it checks again straight away.
- The app's warnings (in `GET /api/state`) have `affecting` (`yours`, `near` and `near_count`), `live_layout` (`attention` and `groups`), and `near_km` in `config`.

## 1.17.0

**Trends in the wider picture**

- **A rise against the usual.** Each warnings check now keeps a few counts, one a day (the day's highest) for two weeks: power cuts near you and across the networks, flood warnings and alerts near you and across England, rivers above their usual range near you, possible fires near you and grid notices. When today's is twice the usual over the last fortnight or more, and big enough to matter, it's a trend: "Power cuts across the networks: 3× the usual". It needs four days of counts first, so it says nothing for the first few days. Nothing new is fetched: the counts come from the feeds the warnings already read.
- **Things to watch**, at the top of the Sitrep when there's a trend. Tap one to open the wider picture at its source. A source with a trend shows amber there, and says why.
- **A chart for each count** in the source's details, a day at a time, with the usual as a dashed line. Point at it (or touch it) for a day's figure. Flood warnings and fires, which aren't live lines, have theirs at the end. `GET /api/live/history`.
- **The daily briefing** is told about any trend, as counts only.

**Home Assistant**

- `sensor.dads_army_trends`: how many trends there are, with each one's `title`, `text`, `source`, `value` and `usual` as attributes.
- `sensor.dads_army_reservoirs`: how full England's reservoirs are, in %, from the drought report, with `vs_average`, `week_to`, your area's `drought_stage` and `hosepipe_ban`.
- `sensor.dads_army_uk_threat_level`: the national threat level (Low to Critical), with `northern_ireland`, `raised_on` and what it `means`.
- `sensor.dads_army_pet_food_days`: how many days the pet food lasts, with what `runs_out_first`. Each of these three appears once there's something to show.

## 1.16.0

**Supply run**

- **Change an extra.** Tap ✏️ beside anything on the "Also get" list to change what it says. Blank isn't allowed: remove it instead.
- **Got it for extras too.** It opens a new item with the extra's words as the name. Add the amount and best-before date, and once it's saved the extra comes off the list.

**Restore an automatic copy**

- **HQ → Restore an automatic copy** lists the daily copies the Pi keeps, and the ones saved just before a restore, newest first, with the date and how many items each has. Pick one to put the stores back as they were. It goes through the same checks as restoring a file: a copy of what you have is saved first, and it asks before restoring one with nothing in it. A damaged copy is listed so you know it's there, but can't be picked. `GET /api/backups`, `POST /api/backups/restore`.

**Expiry timeline**

- **On the Sitrep**, the batches in stock by the month they go out of date, for the next twelve months, after a column for what already has. Red is out of date, amber expiring soon, green fine. Tap a month to see the stores soonest first.

**Home Assistant**

- `sensor.dads_army_expiring_soon` has a new attribute, `expires_in_7_days`: what goes out of date in exactly a week, beside `expires_today`, for a reminder with time to use it up. Every batch a week away counts, not only each item's soonest.

## 1.15.0

**The daily briefing**

- **Every morning at 6am**, Claude reads what Dads Army already knows (the warnings, the wider picture, health news and how long your stores last), searches the news, and writes **one paragraph** on the threats and risks to be aware of: locally, across the UK and in the world (weather, conflict, cyber, health, power, supply and more), compared with what's been usual over the last fortnight. It's at the top of the Sitrep, with Local, UK and World ratings ("↑ above usual" when something's up), the sources it relied on and what it searched for.
- **Off until you switch it on**, in HQ under Scanning. It needs your own Anthropic API key, as the news search runs on Anthropic's side; without one, the card explains that and the switch isn't shown. **Standard** (Claude Haiku 5.5) is about 7p a day, **Thorough** (Claude Sonnet 5.5) about 25p. It counts towards the monthly AI limit and the spending stats, and a key Anthropic refuses switches it off rather than trying every day.
- **Local news for** a town or county you type, or your Met Office region. That name, the day's warnings and wider picture and how long your stores last are sent to Anthropic; nothing else about you.
- **Write one now** in HQ, a history of 60 days for the baseline, and `sensor.dads_army_briefing` in Home Assistant (the headline, with the paragraph, ratings and sources as attributes). `GET/PUT /api/briefing`, `POST /api/briefing/now`.

**More of the wider picture**

Ten more live sources, under **More of the wider picture** in the warnings settings. The briefing reads them too.

- **UK threat level** (set by the Joint Terrorism Analysis Centre and MI5, read from GOV.UK): a warning for a week after it goes up, and at critical.
- **Cyber security** (NCSC): a warning for a critical flaw or live attack in the last three days.
- **Travel advice** (FCDO): which countries' advice changed in the last three days, and any against travel.
- **Drought, reservoirs and hosepipe bans** (the Environment Agency's weekly report, England): reservoir storage, your area's drought status and your water company's hosepipe ban. Choose your Environment Agency area and water company in the warnings settings.
- **Water supply problems near you**: reports within 10 km from your water company's public "in your area" map or page, for Cambridge Water, South Staffs Water, Yorkshire Water, South West Water, Bournemouth Water and NI Water. Choose your company in the warnings settings (it isn't guessed from where you live, except NI Water in Northern Ireland). For any other company it **switches itself off**, and the settings say why.
- **Flood risk forecast**: five days for England from the Flood Forecasting Centre's outlook (Environment Agency and Met Office) as GOV.UK's Check for flooding publishes it, three for Scotland from the Scottish Flood Forecast (SEPA and the Met Office). The areas at risk are fetched whole and home is checked against them on the Pi, so it gives the risk *where you live* and which day, and home's location isn't sent. A warning at medium or high. (The Flood Forecasting Centre's own open API closed in June 2026; its new one needs a key. Wales has no open forecast just now, so it shows *Not for your area* there.)
- **Rainfall near you**: the nearest rain gauges within 25 km (the Environment Agency's, SEPA's or Natural Resources Wales'): a warning at 30 mm in a day, serious at 50.
- **Groundwater near you** (Environment Agency boreholes within 30 km), against the same time of year. Off to begin with.
- **The grid now**: carbon intensity and the mix (NESO), and the frequency (Elexon), with a warning if it dips. Off to begin with.
- **Electricity margin** (Elexon) for the next 14 hours and two weeks, and NESO's Demand Flexibility Service events: a warning when the margin is tight.

**Only what can reach you raises the alert level**

- An **Emergency Alert** raises it only if its area takes in home: your district, county, region, constituency or police force area, or the whole UK, Great Britain or your nation. The alert's areas are compared as whole names ("North East Lincolnshire" isn't the North East, and a ward called "Central" isn't Central Bedfordshire), "Wales and South West England" counts for both, and "Glasgow" is ONS's "Glasgow City". One for another county still shows in the live panel. To know home's area, its location rounded to about 100 m is looked up once at postcodes.io (ONS data); until then every alert counts, to be safe.
- A **GDACS disaster** raises it only if it's in the UK or Ireland, within 300 km, or a volcano within 2,000 km (ash closes airports), whatever the disaster distance is set to. An earthquake in Norway shows in the panel but no longer raises the level, and neither does a drought across Europe that lists Ireland among many countries.

**The rest of the UK**

Where England's feeds don't reach, Scotland's, Wales' and Northern Ireland's own take over. Each is asked only for homes it covers (in its nation or network, or near enough to the border to matter), and each is the provider's whole list, picked through on your own machine.

- **Flood warnings** in Scotland from SEPA (the flood warning and flood alert areas behind its Floodline map: a warning counts if home is inside the area or within your flood distance) and in Wales from Natural Resources Wales (its flood warning page), beside the Environment Agency's for England. They raise the alert level as England's do, and say who they're from.
- **River levels** in Scotland from SEPA's gauges, against SEPA's own usual range (its median yearly low and high). Natural Resources Wales publishes levels but no usual range, so Wales has only the Environment Agency's border gauges for now.
- **Rainfall** from SEPA's and Natural Resources Wales' rain gauges, and **the flood risk forecast** from the Scottish Flood Forecast, as above.
- **Power cuts** from Electricity North West and NIE Networks (the lists behind their power cut maps) for homes on or near their networks, as well as the four networks before. SP Energy Networks only publishes its live power cuts to registered users, so a home on its network gets a note saying so, with its power cut map. If one network's feed fails or changes shape, the others still show, and the live line says which couldn't be checked.
- **Water supply** from four more companies, as above.
- **Which nation, and which network:** rough borders for the nations (Kintyre is Scotland), and the outlines of Great Britain's 14 electricity licence areas from NESO's open data, bundled as `places/dno_areas.json.gz` (built by `tools/build_dno_areas.py`, about 40 KB).
- **Not for your area:** a source that can't cover home isn't fetched and says so in the warnings settings, rather than failing. In Northern Ireland: flood warnings, river levels, rainfall, the flood risk forecast and the grid sources (its grid is run with Ireland's). In Wales: the flood risk forecast. Outside England: groundwater and the drought report.

**Fixes from a regression run against the real feeds**

A run of every source against the real feeds on 17 November 2026, and a review of the code, turned these up.

- **The threat level** is read from GOV.UK: MI5's own feed now answers automated requests with a bot check (403).
- **Grid notices:** levelled by their type, and the system operators' own business (IT outages, trades between operators, emergency help between them) is left out, whatever words it uses.
- **Met Office region:** the Dumfries, Galloway, Lothian & Borders region had a different name from the feed's, so its warnings never matched; and the region guessed from your location is now within your own nation (Cardiff is Wales, not the South West).
- **Groundwater:** a borehole's logger is read for the last 60 days and the same weeks in earlier years (asked for in one go, its 20,000 readings ended years ago, so it always looked out of date), falling back to the readings by hand. A deep borehole below sea level is shown but never "worth watching", and "below sea level" is said as such. No borehole near home is a note, not a failure.
- **Water supply:** your water company is chosen, not guessed (much of Birmingham is Severn Trent, not South Staffs Water). A supply problem counts as yours when the company says your area is affected, or two are reported within 3 km, or one within 1 km. One a little further off is listed, but isn't a warning.
- **Links:** the rainfall line opens the nearest gauge's page (the Environment Agency's old rainfall page is gone), and NCSC news falls back to its news page.
- **Slow feeds** (the Environment Agency's rain readings and NESO's Demand Flexibility list, which can take a minute) are given 60 seconds.
- **The drought report** finds South Staffs Water under its full name, South Staffordshire Water.
- **Northern Powergrid:** a cut covering several postcodes is placed at the one nearest home, not the first listed.
- **📷 Add another photo** keeps the date, size and calories the first photo read, and what the AI only estimated stays marked as an estimate unless the new photo reads it off the pack.
- **Open Food Facts drinks:** categories are matched whole, so rice ("plant-based foods and beverages") isn't drinking water, and coffee, tea and alcohol aren't either. Litres only for a drink sold by volume (and a label's drink sold by weight gets none).
- **Cupboard, fridge or freezer** is only kept for food, drinks and pet food (a torch isn't "ambient"), and the item page says **stored in the cupboard**.
- **The stores review:** an answer of the wrong shape leaves out the odd part rather than failing, opened packs are sent by their "use within" date, and it counts what it sent. A suggestion already on the supply run says so, and can't be added twice.
- **Restore and undo** keep what the AI estimated marked as an estimate.
- **Kit** leaves out drinks on the Pi as well as in the app, and out-of-date juice no longer counts as water past its date.
- **Water is worked out in runs** (a lot going off, the drinks running low, the water running out) rather than a day at a time: ten years of water is a few steps, not 3,660. The app and the Pi still agree, checked on thousands of made-up stores.
- **A barcode photo** is first read at 1,600 pixels (quicker when there's no barcode in it), and "Looking for the barcode…" stays up until it's done.
- **Home Assistant's AI Task** is checked in the background, so the app never waits for it, and a failed check keeps the last answer.
- **The daily briefing** isn't told streets, postcodes, gauge or borehole names, or how far things are from home: "Power cut near home", "River Esk near home".

## 1.14.0

**Stores review**

- **Would your food feed you with no mains water, power, gas or fridge?** A new card on the Sitrep asks the AI to look at what's in the stores and who it's for: can it be eaten cold or with a little heat from what's stored, does it need water to cook, will it keep once opened without a fridge (or is a tin too big for one meal), is it a balanced diet (not 100 tins of tuna), and will it keep. Then a line on the rest of the stores. It suggests up to six things to add, food first, each one tap onto the supply run. Only item names and amounts are sent, and only when you tap **Review my stores**. About 0.3p a go.

**Cupboard, fridge or freezer**

- **Kept before opening:** food, drinks and pet food say whether they're kept in the cupboard, the fridge or the freezer. Scans fill it in from Open Food Facts' storage instructions and categories, the label reader from the pack, and **Fill in missing details** estimates it for what you already have (marked "AI estimate"). Fridge and freezer items show ❄️ or 🧊 in **Stores**. New food, drinks and pet food (the starter list too) are cupboard food unless the barcode, the label photo or you say fridge or freezer.
- **The Sitrep** says how many days of the food needs a fridge or freezer, to eat first in a power cut (`cold_food_days` in `/api/summary`).
- **The stores review trusts it:** a tinned curry kept in the cupboard isn't said to need chilling, and fridge and freezer food counts as the first meals of a power cut, not as stores. Where it isn't recorded, the review goes by the name and unit (a tin is ambient).

**Photos fill in everything they show**

- **Reading a label** now gives what the pack is (jar, carton, box, tin...), its size, calories, best before date and "once opened" days, not just the name. **📷 Add another photo** (the back, the nutrition panel, the date) adds to what's already been read.
- Where no calories or "once opened" days are printed, the AI estimates them for that kind of product, marked **AI estimate** until you change them.
- Open Food Facts results say what the pack is too, where it knows.

**Barcodes that won't scan**

- **Each barcode photo is read six ways** (whole, the middle, smaller, turned), using the phone's own barcode reader first where it has one (Android).
- If Open Food Facts doesn't know the product, or is missing its calories or size, **the same photo is read by the AI** for the rest.
- **The other ways to add something** under the live camera (take a photo, read the label, type the number, pick from the stores) are a tidy grid of buttons, rather than a row that ran off a phone's screen.
- **No barcode found** now lists the usual causes (too far away or blurred, glare, creased) and what to do. The live camera says so after a few seconds if it isn't picking anything up.
- How each scan went (found, not in Open Food Facts, no barcode in the photo, camera not allowed) is written to the add-on's log, to help work out why one didn't work.

**Water**

- **Litres come from the pack size** when "litres in one" isn't set: a 5000 ml (or 5000 g) bottle of water is 5 litres.
- **Juice, milk and other drinks stand in for drinking water only:** up to 1.5 litres a person a day, but cooking, washing and the pets' water have to come from plain water. Water days are worked out a day at a time on that basis, so drinks stretch the water without ever replacing it. Drinks have a "litres in one" field, and the Sitrep's water note says how much there is. `/api/summary` has `water_litres` (plain water), `drink_litres` and `drink_cap_litres`.

**No AI, no AI buttons**

- Without an AI (an API key, or a Home Assistant AI Task), the buttons that need one (read the label, the nutrition label or the date, add another photo, match the date, fill in, stores review) are hidden, and adding an item shows a hint saying what an AI would add.

**Also**

- Item names in **Stores** are shown in full, wrapping onto a second line, not cut off.

## 1.13.0

**How long the food lasts**

- **Food that goes off before you'd get to it doesn't count.** Food and water days are worked out by eating whatever goes off first, a day at a time: 10 days of bread that goes off on Tuesday counts only until Tuesday. The Sitrep says how many days' worth goes off first, and `sensor.dads_army_food_days` has it as `goes_off_first_days`.
- **Drinks** is a new category: juice, milk, squash and fizzy drinks. Their calories count towards food; they don't count as drinking water. Scans put juices and soft drinks there.
- **Calories are for one whole tin or pack, never a serving**, and the form says so ("Calories in one whole tin (not per serving)"), with what that is in an adult's day underneath, so a per-serving figure stands out.
- **Multipacks count the whole pack:** "6 x 330 ml" gives the calories for all six, even when Open Food Facts lists one can's size.
- **📷 Read the nutrition label**, next to the calories and on a scan result with no calories: the AI reads the kcal per 100 g (and the weight) from a photo of the nutrition table and works out the whole pack, showing the sum for you to check. A per-serving figure is noted, not used.
- **Fill in missing details** (HQ → Scanning, or **Fill in with AI** on the Sitrep): the AI estimates calories, what one holds and how long it keeps once opened, from the names alone, for the food and drinks missing them. You see each one and untick any that look wrong; nothing is saved until you do, and saved figures show **AI estimate** until you change them.

**Scan to add and use stock**

- **Scan a barcode** from **Stores**, or from an empty store. On a phone with the Home Assistant app over https, the camera reads it as soon as it's in the box, with a torch button for dark cupboards. Anywhere the live camera isn't allowed, it takes a photo instead. Or type the numbers.
- **Something you've scanned before** goes straight to its item: **Putting it in the stores** or **Taking it out to use**.
- **Something new** is looked up in Open Food Facts: the name (in English), size and calories. Add it as a new item, or **add it to something you already keep**, so another brand of baked beans goes on the same line with its own batches. The barcode is remembered either way, and it's in backups.
- **No barcode, or not in Open Food Facts?** The AI reads the label from a photo: the name, size, calories and best before date, for you to check.
- **Nothing to scan at all** (a can from a multipack)? **Choose from your stores** picks the item, then put one in or take one out.
- Reads GS1 DataBar (the wide, stretched barcodes on some own-brand packs), Code 128 and ITF as well as the usual ones. A 12-digit UPC code and the same code with a 0 in front are one barcode.
- **Read the best before date from a photo** when adding stock or a new item, or type it as before.
- **Which AI:** Home Assistant's own AI Task (whatever you've set up there: Google Gemini, Anthropic Claude or OpenAI), or one of those directly with your own key, in **HQ → Scanning**. Keys stay on the Pi, are never shown back, and are left out of backup files and the automatic database copies. A photo is deleted as soon as it's been read (and one left by a restart is tidied up). About 0.1p a photo.
- **AI use and spending** in **HQ → Scanning**: this month's cost, answers, today's, and what's left of a **monthly limit** you set, with the last 15 calls. Once the limit is reached, nothing more goes to Claude, Gemini or OpenAI with your key until the 1st. Also in `sensor.dads_army_ai_spend`.
- **Plain-words AI errors:** busy on the provider's side (it tries once more), allowance used up, no credit, or the key not accepted.
- Closing one sheet and opening the next straight away (a scan result replacing **Type the numbers**, say) no longer loses the new one; Back still goes step by step. The **−** button is easier to see, and dashed when there's nothing to take away.
- The barcode reader is the open-source ZXing library, included with the app (MIT licence), so it works without the internet.
- **Offline barcode list.** In **HQ → Scanning**, keep a list of the products Open Food Facts lists as sold in the UK (about 180,000) on the Pi, so scanning a new barcode works with the internet down. It's built from Open Food Facts' public export (a 1.5 GB download, read as it arrives, about 25 MB on the Pi): the first time when it's switched on, then once a month overnight, or with **Update now**. Barcodes are looked up there first, then online. It's left out of Home Assistant backups, as it can always be downloaded again.

**One line per product, many batches**

- **Add stock** has **Same as …** for each best before date you already have, and each batch on an item's page has **More like this** (the same date and place).
- Typing a new item that's already in the stores offers to add stock to it instead.

**Part of a pack**

- **Each one holds:** say what one holds (a 500 g bag, a 1 kg bag, 6 cans in a pack). Scans fill it in.
- **Use** then offers whole ones, **an amount** (200 g, or single cans from a pack), or **What's left** in the open one (300 g). The item shows "1 bag + 300 g in the open one".
- **Once opened, use within:** an open tin of beans keeps about 3 days. Using part of one makes the rest its own batch, dated when it was opened. It goes off then, even if its best before is later (in the app and in Home Assistant's sensors), and it's used first. New stock never joins an opened pack. Undo, backups and restores keep it opened.
- Single cans from a multipack add up: one at a time, six times, leaves whole packs.
- **Which batch is it from?** When there's more than one, **Use** asks, with the oldest ticked. **Match the date on it** reads the date from a photo and ticks that batch, so the right one goes down.

## 1.12.0

**New**

- **Credits.** Help → **Credits**, or the link at the foot of HQ, thanks everyone who has built Dads Army and lists them, with the open data it uses.
  - The words and names come from `CREDITS.md` in the GitHub repository, so they can be changed there.
  - The app carries its own copy, so the page works with no internet.
  - **Check GitHub for new names** gets the latest list, and adds anyone who has changed the code on GitHub. GitHub is only asked when you tap it, and nothing about you is sent.

## 1.11.0

**Fixes**

- **Out-of-date stock no longer counts towards targets.** Out-of-date tins show on the supply run as needing replacing, and an item with only out-of-date stock counts as out of stock.
- **The spreadsheet export can't be made to run formulas.** A cell starting with = + − or @ is saved as plain text.
- **Backups:**
  - each daily copy is checked before it's kept, and copies never overwrite each other
  - restoring a backup with nothing in it asks first
  - a restore stops if it can't save a copy of what you have first
- **Undo won't overwrite a newer change** to the same item or check, made on another phone or by Home Assistant. It says what it left alone.
- **"Ran out" alerts aren't lost** while Home Assistant can't be reached. They're sent when it's back, unless the thing has been restocked by then.
- **Stricter checks on what's typed in.** Dates, numbers and ids are checked strictly, and an out-of-range number is refused rather than quietly changed.

**New**

- **Pets.** Say how many dogs, cats and other pets you have in HQ. Their water counts towards the household's. The Sitrep shows how long their food lasts. The starter list adds pet food, medicines and a carrier.
- **Starter list targets follow the household.** Change the household or the readiness target, and targets from the starter list change to suit, unless you've set them yourself.
- **Expiry warnings by category:** warn earlier for medicines (90 days, say) than for tins.
- **How fast you use things:** "You use about 2 tins a week, lasts 6 weeks", from the last three months.
- **The wider picture.** These come with warnings, and each can be switched off. Like the warnings, each is a public feed for the whole country, so nothing about you is sent.
  - **River levels** near you, against their normal range, rising or falling (England).
  - **Power cuts** within 10 km, from UK Power Networks, National Grid, SSEN and Northern Powergrid.
  - **Electricity grid notices** from NESO.
  - **Gas storage**, against a year ago.
  - **Air quality** now and forecast.
  - **Space weather.**
  - **The pound and Bank Rate.**
  - Warnings when something's up, including two-week trends such as "gas storage is emptying faster than this time last year".
  - A nearby power cut, a high river, high air pollution or a severe solar storm raises the household alert level.
  - On the Sitrep, on the Home front dashboard (**Update the dashboard** to add it), and in `sensor.dads_army_live`.
- **Trends:** charts of how many days the food and water would last, and of resilience, day by day. Dads Army now keeps a line a day, and fills in the first days from what Home Assistant remembers.
- **Wall tablets and wider screens:** the tabs move to a rail down the side, the cards flow into two or three columns, details open in the middle, and **Stores** becomes a table you can sort.
- **Tests:** a `tests` folder with about 100 tests of the server, backups, undo, Home Assistant sync and the feeds.

## 1.10.0

- **Places to go.** If staying at home isn't safe, where could you go? Dads Army suggests places near home for each kind of emergency: flooding, storms, a wildfire, an earthquake, civil unrest, a heatwave, cold or a long power cut, having to leave home, and a medical emergency. Each comes with a line of advice.
  - The suggestions are high ground, community halls, leisure centres, libraries, parks and assembly points, plus the nearest fire station, police station and hospital.
  - What's happening now comes first. During a flood warning or a fire nearby, it leaves out places nearer to it than you are.
  - **Your own places:** add family, friends and meeting places on the Plan tab, by pasting a map link or typing coordinates. Say what each one is for, and it comes first.
- **A map on the Home front dashboard**, in Home Assistant's own map card, with home and the places around it. Underneath, where you could go for each kind of emergency. Dads Army offers to update the dashboard.
- **In the app**, the Plan tab has a sketch of home and the places nearby, and the alert level's **What to do now** includes where to go.
- **Nothing is looked up online.** The app comes with a list of about 58,000 places across the UK, built from OpenStreetMap, and picks the ones near home itself. They're possibilities, not official refuges: councils announce rest centres at the time. Place data © OpenStreetMap contributors (ODbL).
- Flood warnings now remember where the flood area is.

## 1.9.0

- **Resilience, in ten areas.** Being ready isn't just food and water. Dads Army now looks at:
  - water
  - food and cooking
  - power and light
  - warmth
  - communications
  - health
  - hygiene
  - fire and home safety
  - money and documents
  - your plan for getting out

  Each area has a score, and the Sitrep shows them all just under the alert level.
- **About 65 recommendations**, each marked essential, recommended or extra, and labelled with its source: mostly the UK Government's **Be Ready** checklist, **Ofcom** and **Fire Kills**. They include:
  - a UPS for the router and Home Assistant
  - a battery or wind-up radio
  - a battery backup for a digital landline
  - walkie-talkies
  - power banks and spare batteries
  - smoke and carbon monoxide alarms
  - the Priority Services Register
- **Ticked off for you** where Dads Army can see it, in your stores, plan, checks, warnings and home sensors. Tick the rest off yourself, or say they're not for you.
  - **Add to stores** puts anything missing on the supply run.
  - **Next steps** shows what to do first.
- **The alert level** now takes resilience into account. An area missing an essential keeps it at MODERATE or higher, in place of the old "kit under half stocked" rule. In a power cut with no torches or power bank, or a cold home with no blankets or warm clothes, SUBSTANTIAL goes up to SEVERE.
- **Home Assistant.**
  - New `sensor.dads_army_resilience`.
  - The Home front dashboard has a **Resilience** section, in place of the food-and-water gauge, and an **All recommendations** page. Dads Army offers to update the dashboard.
  - The weekly round-up ends with your resilience and what to do next. Re-import the blueprint.
- The UK Government's Prepare campaign is now called **Be Ready**, and the advice is labelled to match.

## 1.8.1

- **A smaller alert level on the Home front dashboard**, so everything else fits on a tablet without scrolling far.
  - The level now has a compact card: its name and colour, the main reason, and the whole scale on one line. It takes one column, so the warnings and today's checklist sit beside it.
  - **Why, and what to do now** opens on its own page, with the big scale, every reason and all the labelled advice. The **Alert level** badge at the top opens it too.
  - The **i** next to the heading opens **What the levels mean**.
  - Dads Army offers to update a dashboard you've already made. Tap **Update the dashboard**.

## 1.8.0

- **Household alert level.** A five-step scale for the household, from LOW (green) through MODERATE, SUBSTANTIAL and SEVERE to CRITICAL (black). It uses the names of the UK's national threat levels, the British equivalent of DEFCON, but it's the household's own level, not the official one.
  - It shows big at the top of the Sitrep, with the full scale and why it's at that level.
  - Tap **i** for what each level means, how it's worked out, and where the advice comes from.
  - It's worked out from warnings in force, your stores, and your home's own sensors. Stores too low to last 3 days make a SUBSTANTIAL situation SEVERE.
- **What to do now.** Every level comes with plain advice for the situation, worst problem first. Each piece is labelled with its source: **UK Government** (Prepare, the NHS, UKHSA, the Met Office, the Environment Agency and others), the **SAS Survival Handbook**'s PLAN priorities applied to a household, fire and rescue services, or the 105 power cut line.
- **Home sensors.** Dads Army can watch your Home Assistant sensors for:
  - indoor and outdoor temperature
  - humidity
  - mains power or UPS, and a backup battery
  - gas, carbon monoxide and smoke alarms
  - water leaks
  - the internet
  - outdoor air quality

  For example, a cold bedroom, a power cut, a leak or a carbon monoxide alarm raises the level and brings the right advice. **Suggest sensors for me** picks likely ones.
- **Home front dashboard.** The alert level now leads the dashboard, big and colour-coded with the full scale. Underneath are the reasons and labelled advice, and a **What the levels mean** page. Dads Army offers to update a dashboard you've already made.
- **Home Assistant.**
  - New `sensor.dads_army_alert_level`, and a `dads_army_alert_level` event when the level changes.
  - The phone alerts blueprint tells you when it goes up (to SUBSTANTIAL or higher unless you choose otherwise).
  - The weekly round-up starts with the level.
  - Re-import both blueprints.

## 1.7.2

- **A quieter Activity log in Home Assistant.** **Dads Army needs attention** no longer turns "Unavailable" and back again every time Dads Army restarts, which happens for each update and for Home Assistant's nightly backup. That added two lines to the Activity log each time. The number sensors still show "Unavailable" while Dads Army is stopped, so dashboards can still tell.
- **Needs attention now means "needs doing now".** It comes on for stock past its best-before date, checks that are overdue, and serious warnings (amber or worse). It no longer counts things you haven't bought yet (they're on the supply run), or checks you haven't done for the first time yet. Before, it stayed on for weeks while you built up your stores.

## 1.7.1

- **Easier to set up the Home front dashboard.** When you open Dads Army in Home Assistant, it offers to make the dashboard for you. It shows a preview with your own numbers and can set up today's checklist and the supply run list at the same time. One tap does the lot, with each step ticked off as it goes.
  - **Not now** asks again in two weeks, and **Don't ask again** stops it.
- **Help.** A new **?** button at the top of every screen leads to the dashboard set-up, warnings, routine checks and the emergency plan, the supply run, and how to get phone alerts.

## 1.7.0

- **Home front dashboard.** In **HQ → Home Assistant**, tap **Make the dashboard**. A new **Home front** dashboard appears in the Home Assistant sidebar and the Companion app, built from Home Assistant's own cards. It shows:
  - warnings in force
  - today's checklist
  - the readiness gauge, hold-out, food, water and daily supplies
  - the stores: expired, expiring soon, out of stock, running low, kit and value, plus what to use first
  - the supply run, with a button to open Dads Army
  - a graph of the days you could last
- **Today's checklist.** Your routine checks can go on a Home Assistant to-do list. Checks that are due, overdue or not done yet appear with their due dates. Tick one off on the dashboard or in the Companion app and it's marked done in Dads Army, with the next one worked out.

## 1.6.1

- **Possible fires nearby.** A new warnings source, off until you tick it in the warnings settings: hotspots NASA's satellites picked up in the last 24 hours within 10 km of home (you can change the distance).
  - Nearby hotspots are grouped into one **Possible fire**, such as "Possible fire 6 km north-east of home", with a link to NASA's fire map and fire safety advice.
  - Satellites also see controlled burns, farm fires and industrial flares. Places that come up again and again over a week or more are left out, and you can tap **Not a wildfire: ignore this spot** for any other.
- A warning that drops out for one check (if a feed hiccups) no longer sends a second phone alert when it comes back.

## 1.6.0

- **Warnings for where you live.** Switch them on under **HQ → Warnings** to see official warnings from:
  - the Met Office (yellow, amber and red weather warnings for your region)
  - the Environment Agency (flood alerts and warnings near you, England only)
  - GOV.UK Emergency Alerts
  - GDACS, the UN and EU disaster alert system (orange and red alerts within 1,000 km)
  - optionally, news from the UK Health Security Agency and WHO disease outbreak news
- The most serious warnings show at the top of the Sitrep. The Plan tab lists them all, with the health news.
- Tap a warning for the official message and a link to the full details. You also get what to do, and the parts of your emergency plan that matter, such as where to meet and how to turn off the gas, electricity and water.
- **Private and offline-friendly.** Dads Army downloads the same public files for everyone and works out what's near you on your own machine, so your location is never sent. Without the internet, everything else carries on and the last warnings stay on show with when they were checked.
- **Home Assistant.**
  - New `sensor.dads_army_warnings`, and a `dads_army_warning` event when a new warning comes in.
  - The phone alerts blueprint tells you straight away: amber and worse unless you choose otherwise.
  - The weekly round-up lists warnings in force, and **Needs attention** comes on for serious ones.
  - Re-import both blueprints to get these changes.

## 1.5.0

- **New Plan tab: routine checks.** Keep track of the jobs that keep your kit ready, such as testing the smoke alarms, charging the power banks, rotating stored water and checking the grab bag.
  - Tap **Done** when you've done one, and Dads Army works out when it's next due.
  - **Add suggested checks** gives you nine to start with, based on the usual advice.
  - Checks that are due show on the Sitrep, with a count on the Plan tab.
- **Household emergency plan.** Also on the Plan tab: contacts (tap to call), where to meet, how to turn off the water, gas and electricity, medical needs, pets, documents and local radio.
  - **Add UK emergency numbers** fills in 999, 111, 105, the gas emergency line, Floodline and 101.
  - It works with the internet down, and **Print** puts it on paper for the grab bag, with the checks.
- **How long things last.** Set **Used a day** on things like tablets, nappies or toilet roll.
  - Dads Army shows how long each one lasts, counting only stock that's still in date.
  - A new **Daily supplies** bar on the Sitrep shows the first thing to run out.
  - The form suggests a target that covers your readiness period.
  - The starter list now sets this for toilet roll, wet wipes, tea bags and gas canisters.
- **Prices.** Set **Price each** on an item. The Sitrep then shows what the stores are worth, and the supply run shows what it should cost.
- **Like last time.** When you add stock, a new button sets the best-before date as far ahead as last time.
- **Home Assistant.**
  - New sensors: `sensor.dads_army_checks_due`, `sensor.dads_army_supplies` and `sensor.dads_army_stores_value`.
  - The supply run sensor has a `cost`.
  - **Needs attention** also comes on when a check is due.
  - The phone alerts blueprint tells you each morning about checks that fall due that day.
  - The weekly round-up lists the checks that are due and what runs out first.
  - Re-import both blueprints to get these changes. The dashboard card on the Documentation tab has the new tiles.
- Backups and the spreadsheet export include the new details. Restoring a backup from an older version leaves your checks and plan as they are.

## 1.4.0

- **Delete several items at once.** In Stores, tap **Select to delete**, then tick the items you don't want to keep. **Select all** picks everything showing, so you can clear out a whole category or a search in one go. Before anything is deleted, Dads Army lists what's going and warns you about any stock that goes with it. **Undo** puts it all back.
- Deleted items also come off your Home Assistant supply run list.

## 1.3.0

- **Supply run on a Home Assistant to-do list.** In HQ → Home Assistant, tap **Make a "Supply run" list**, or pick a list you already have. The supply run then shows in Home Assistant's To-do lists and the Companion app, and stays in step both ways:
  - Below-target items come off the list once you're back up to target.
  - Tick off an item in Home Assistant and it's marked on the supply run here, ready for **Got it**.
  - Extras are shared. Add, tick, rename or delete them on either side.
  - Anything added in Home Assistant, including by voice ("Add matches to the supply run list"), becomes an extra.
- **Phone alerts.** Two blueprints:
  - **Phone alerts** tells you straight away when something runs out, and each morning about anything that went out of date overnight or is on its last day.
  - **Weekly round-up** lists what to use first, what's out of date, the supply run, and how long you could hold out.

  The setup steps are on the Documentation tab.
- **Readiness gauge.** A new sensor, `sensor.dads_army_readiness`, shows your hold-out as a percentage of your target. The dashboard card now opens with a red, amber and green gauge, next to hold-out, food and water.
- **For automations.** A `dads_army_ran_out` event fires when the last of something is used up. The expired and expiring-soon sensors also list what went off overnight (`newly_expired`) and what expires today (`expires_today`).

## 1.2.0

- **Dashboard sensors.** Dads Army now publishes sensors to Home Assistant for:
  - hold-out days, plus food and water days
  - kit stocked
  - out of stock and running low
  - expired, expiring soon, and next to expire
  - the supply run
  - a "needs attention" alert

  They update within seconds of any change. The item lists are in each sensor's attributes.
- **Dashboard card.** A ready-made card is in the Documentation tab: paste it into any dashboard.
- **Summary for other tools.** `GET /api/summary` gives the same figures as JSON.
- **Local dates.** "Today" now follows your Home Assistant time zone.

## 1.1.1

- The app's log now tells you how to open Dads Army from Home Assistant, instead of showing internal container addresses.

## 1.1.0

- Installs from the Dads Army app repository, so updates arrive in **Settings → Updates** like any other app.
- Home Assistant now restarts Dads Army automatically if it stops responding.
- Works inside the Home Assistant sidebar and the Companion app.

## 1.0.0

- First release. It includes the Sitrep, Stores, Supply run and HQ screens. Stock is tracked in batches with best-before dates and used oldest first. There's undo, a starter list, daily backups, a printed copy and CSV export.
