# Dads Army

A stores tracker for food, water and emergency kit, built to be used from your phone.

## Opening it

- **In Home Assistant:** click **Dads Army** in the sidebar. This also works in the Home Assistant Companion app, including away from home if you use Home Assistant Cloud.
- **Straight from the phone's browser:** open `http://<your-pi's-address>:8080` while on the home Wi-Fi, then use **Add to Home Screen** to give it its own app icon.

## Your data

Your data is kept in the add-on's own storage. It survives restarts and updates, and it's included in your Home Assistant backups. On top of that:

- Dads Army saves a copy of its database every day and keeps the last 14.
- HQ → **Download backup** saves a copy to your phone.
- HQ → **Print full inventory** gives you a paper copy to keep with the stores.

## Security

There's no separate login. Anyone who can reach port 8080 on your home network can open it. Through the sidebar, only signed-in Home Assistant users can open it. Don't port-forward 8080 on your router.
