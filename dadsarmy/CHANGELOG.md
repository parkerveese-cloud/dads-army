# Changelog

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
