"""Stand-ins for the public feeds, served from this machine. Each records the requests it gets, so the
tests can check that nothing about where you live is ever sent."""
import datetime as dt
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOW = dt.datetime.now(dt.timezone.utc)


def ago(**kw):
    return NOW - dt.timedelta(**kw)


def rfc(d):
    return d.strftime("%a, %d %b %Y %H:%M:%S GMT")


def met():
    items = [("Amber warning of wind affecting Yorkshire &amp; Humber",
              "Amber warning of wind affecting Yorkshire &amp; Humber: North Yorkshire valid from 0600 Fri to 2359 Fri", "w1"),
             ("Yellow warning of rain affecting London &amp; South East England",
              "Yellow warning of rain affecting London &amp; South East England: Kent valid from 0000 Sat", "w2")]
    body = "".join("<item><title>%s</title><link>https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings#?id=%s"
                   "</link><description>%s</description><pubDate>%s</pubDate><guid isPermaLink=\"false\">%s</guid></item>"
                   % (t, g, d, rfc(ago(hours=2)), g) for t, d, g in items)
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Met Office</title>%s'
            '</channel></rss>' % body).encode()


FLOODS = {"items": [
    {"floodAreaID": "NEAR1", "severityLevel": 3, "severity": "Flood alert", "description": "River Esk at Sleights",
     "message": "River levels are rising.", "floodArea": {"county": "North Yorkshire", "notation": "NEAR1"},
     "timeRaised": ago(hours=1).strftime("%Y-%m-%dT%H:%M:%S")},
    {"floodAreaID": "FAR1", "severityLevel": 1, "severity": "Severe flood warning", "description": "Thames at Putney",
     "message": "Danger to life.", "floodArea": {"county": "Greater London", "notation": "FAR1"},
     "timeRaised": ago(hours=2).strftime("%Y-%m-%dT%H:%M:%S")}]}
CENTRES = {"NEAR1": (54.46, -0.67), "FAR1": (51.46, -0.22)}


def govalerts():
    def entry(eid, area, sent, stopped, text):
        stamp = lambda d: d.strftime("%Y-%m-%d %H:%M") + " GMT"   # noqa: E731
        summ = "Alert area: %s. Sent: x [%s]." % (area, stamp(sent)) + (" Stopped: y [%s]" % stamp(stopped) if stopped else "")
        return ("<entry><id>https://www.gov.uk/alerts/%s</id><title>%s</title><updated>%s</updated>"
                "<content type=\"xhtml\"><div xmlns=\"http://www.w3.org/1999/xhtml\"><p>%s</p></div></content>"
                "<link href=\"https://www.gov.uk/alerts/%s\"/><summary>%s</summary><published>%s</published></entry>"
                % (eid, area, sent.isoformat(), text, eid, summ, sent.isoformat()))
    return ('<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Alerts</title>' +
            entry("live", "North Yorkshire", ago(hours=1), None, "Severe flooding. Leave the area now if it is safe.") +
            entry("test", "England", ago(hours=3), ago(minutes=10), "This is a test of Emergency Alerts. You do not need to take any action.") +
            '</feed>').encode()


def gdacs():
    def item(guid, title, lvl, lat, lon):
        return ('<item><title>%s</title><description>%s</description><link>https://www.gdacs.org/report.aspx?eventid=%s</link>'
                '<pubDate>%s</pubDate><gdacs:iscurrent>true</gdacs:iscurrent><gdacs:alertlevel>%s</gdacs:alertlevel>'
                '<gdacs:country>X</gdacs:country><guid isPermaLink="false">%s</guid><georss:point>%s %s</georss:point></item>'
                % (title, title, guid, rfc(ago(hours=3)), lvl, guid, lat, lon))
    return ('<?xml version="1.0" encoding="utf-8"?><rss version="2.0" xmlns:gdacs="http://www.gdacs.org" '
            'xmlns:georss="http://www.georss.org/georss"><channel>' +
            item("EQ1", "Orange earthquake in Norway", "Orange", 60.4, 5.3) +
            item("TC1", "Red tropical cyclone in the Philippines", "Red", 13.0, 122.0) + '</channel></rss>').encode()


def ukhsa():
    return ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>UKHSA</title>'
            '<entry><id>tag:x,2005:cold</id><updated>%s</updated><link rel="alternate" type="text/html" '
            'href="https://www.gov.uk/government/news/cold"/><title>Cold-health alert</title><summary>Cold</summary>'
            '</entry></feed>' % ago(days=1).isoformat()).encode()


def who():
    return json.dumps({"value": [{"UrlName": "2026-DON625", "PublicationDateAndTime": ago(days=3).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "UseOverrideTitle": False, "Title": "Ebola disease - DRC"}]}).encode()


def fires():
    d = NOW.strftime("%Y-%m-%d")
    return ("latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"
            "54.52,-0.55,330.1,0.4,0.4,%s,0124,N20,nominal,2.0NRT,280.1,5.2,N\n"
            "54.521,-0.552,331.0,0.4,0.4,%s,0124,N20,high,2.0NRT,281.0,7.9,N\n"
            "60.1,5.3,320.0,0.4,0.4,%s,0124,N20,high,2.0NRT,280.0,3.0,N\n" % (d, d, d)).encode()


def fires_modis():
    return b"latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,confidence,version,bright_t31,frp,daynight\n"


def places():
    """Home's area, for which Emergency Alerts count (postcodes.io's reverse lookup)."""
    return json.dumps({"status": 200, "result": [{"admin_county": "North Yorkshire", "admin_district": "Scarborough",
                                                  "region": "Yorkshire and The Humber", "country": "England"}]}).encode()


class FakeFeeds(object):
    """Serves each feed at /<key>. EXTRA lets a test add more (the live information feeds)."""

    def __init__(self, extra=None):
        self.log, self.broken, self.missed = [], {}, []   # missed: asked for a feed there's no stand-in for
        self.routes = {"met": (met, "application/xml"), "floods": (lambda: json.dumps(FLOODS).encode(), "application/json"),
                       "govalerts": (govalerts, "application/xml"), "gdacs": (gdacs, "application/xml"),
                       "ukhsa": (ukhsa, "application/xml"), "who": (who, "application/json"),
                       "fires": (fires, "text/csv"), "fires_modis": (fires_modis, "text/csv"),
                       "places": (places, "application/json")}
        self.routes.update(extra or {})
        feeds = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                feeds.log.append({"path": self.path, "ua": self.headers.get("User-Agent", ""),
                                  "headers": dict(self.headers)})
                key = self.path.strip("/").split("/")[0].split("?")[0]
                if key in feeds.broken:
                    return self.send(feeds.broken[key], b"broken", "text/plain")
                if key == "floodarea":
                    nid = self.path.rsplit("/", 1)[1]
                    if nid not in CENTRES:
                        return self.send(404, b"{}", "application/json")
                    lat, lon = CENTRES[nid]
                    return self.send(200, json.dumps({"items": {"lat": lat, "long": lon}}).encode(), "application/json")
                if key not in feeds.routes:
                    feeds.missed.append(self.path)
                    return self.send(404, b"no", "text/plain")
                fn, ctype = feeds.routes[key]
                self.send(200, fn(), ctype)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.base = "http://127.0.0.1:%d/" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def urls(self):
        b = self.base
        return {"metoffice": b + "met", "floods": b + "floods", "floodarea": b + "floodarea/{id}",
                "govalerts": b + "govalerts", "gdacs": b + "gdacs", "ukhsa": b + "ukhsa", "who": b + "who",
                "fires": b + "fires", "fires_modis": b + "fires_modis", "places": b + "places"}

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# -- More of the wider picture (1.15.0): stand-ins for the threat level, NCSC, FCDO, the drought report, the
# flood risk outlook, rain gauges, boreholes, carbon intensity, frequency, margins and water incidents.
def threat():
    """GOV.UK's "Terrorism and national emergencies" guide, as its Content API gives it (17 Nov 2026's shape)."""
    return json.dumps({"title": "Terrorism and national emergencies", "details": {"parts": [
        {"slug": "terrorism-threat-levels", "title": "Terrorism threat levels",
         "body": '<p>The threat level indicates the likelihood of a terrorist attack in the UK.</p>'
                 '<h2 id="national-threat-level">National threat level</h2><p>The threat to the UK (England, Wales, '
                 'Scotland and Northern Ireland) from terrorism is substantial.</p><h2 id="northern-ireland-related-threat-'
                 'level">Northern Ireland-related threat level</h2><p>The threat to Northern Ireland from Northern '
                 'Ireland-related terrorism is substantial.</p>'},
        {"slug": "counterterrorism", "title": "Counter-terrorism", "body": "<p>Nothing about levels here.</p>"}]}}).encode()


def ncsc():
    def item(title, when):
        return ("<item><title>%s</title><description>%s</description><link>https://www.ncsc.gov.uk/news/x-%d</link>"
                "<pubDate>%s</pubDate></item>" % (title, title, int(when.timestamp()), rfc(when)))
    return ('<?xml version="1.0"?><rss version="2.0"><channel>' +
            item("Critical vulnerability in a widely used router, actively exploited", ago(days=1)) +
            item("NCSC annual review published", ago(days=5)) + item("Old news", ago(days=40)) +
            '</channel></rss>').encode()


def fcdo():
    def entry(country, text, when):
        return ('<entry><title>%s</title><updated>%s</updated><link rel="alternate" '
                'href="https://www.gov.uk/foreign-travel-advice/%s"/><summary>%s</summary></entry>'
                % (country, when.isoformat(), country.lower(), text))
    return ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">' +
            entry("Ruritania", "The FCDO now advises against all travel to Ruritania.", ago(days=1)) +
            entry("Freedonia", "Updated information on local laws.", ago(days=2)) +
            entry("Atlantis", "Old change.", ago(days=10)) + '</feed>').encode()


DROUGHT_BODY = ('<h2>Summary</h2><p>It has been a dry week.</p><p>Total reservoir storage for England fell to 61.5% of '
                'capacity, which is 12.3% below the average for this time of year.</p>'
                '<h2>Areas in drought</h2><ul><li>East Anglia</li><li>Thames</li></ul>'
                '<h2>Areas in prolonged dry weather</h2><ul><li>Wessex</li></ul>'
                '<h2>Temporary use bans</h2><ul><li>Thames Water: a hosepipe ban from 14 July</li></ul>'
                '<h2>Thames Water</h2><p>Reservoirs are lower than usual.</p>')


def dsearch():
    return json.dumps({"results": [{"title": "Dry weather and drought in England: weekly report",
                                    "link": "/government/publications/dry-weather-drought", "public_timestamp": "2026-11-10"}]}).encode()


def govuk():
    end = ago(days=4).date()
    return json.dumps({"details": {"attachments": [
        {"title": "Dry weather and drought in England, %s to %s" % ((end - dt.timedelta(days=6)).strftime("%-d %B"),
                                                                    end.strftime("%-d %B %Y")),
         "url": "/government/publications/dry-weather-drought/week"}], "body": DROUGHT_BODY}}).encode()


def floodrisk():
    """Check for flooding's front page, as it was on 17 November 2026 (just the parts read)."""
    days = [{"idx": n, "level": 0, "date": (NOW + dt.timedelta(days=n - 1)).strftime("%Y-%m-%dT10:30:00.000Z")} for n in range(1, 6)]
    return ("<html><body><h2>Flood forecast for the next 5 days</h2><p>River flooding is possible in the north east "
            "&amp; Yorkshire.</p><p>Updated at 10:30am</p><script>window.flood.model = {\n  \"outlookUTC\": \"%s\"}\n"
            "window.flood.model.outlookDays = %s</script></body></html>"
            % (ago(hours=3).strftime("%Y-%m-%dT%H:%M:%SZ"), json.dumps(days))).encode()


def _around(lat, lon, d):
    return {"type": "Polygon", "coordinates": [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d],
                                                [lon - d, lat + d], [lon - d, lat - d]]]}


def floodrisk_areas():
    """The areas at risk: medium round Whitby from tomorrow, low across more of Yorkshire, high in Cumbria."""
    return json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"risk-level": 2, "days": [1, 2, 3], "z-index": 1}, "geometry": _around(54.4, -0.8, 0.5)},
        {"type": "Feature", "properties": {"risk-level": 3, "days": [2, 3], "z-index": 2}, "geometry": _around(54.486, -0.615, 0.1)},
        {"type": "Feature", "properties": {"risk-level": 4, "days": [2], "z-index": 3}, "geometry": _around(54.6, -3.1, 0.2)},
        {"type": "Feature", "properties": {"risk-level": "x"}}, None]}).encode()


def rainst():
    return json.dumps({"items": [{"notation": "R1", "label": "Near gauge", "lat": 54.47, "long": -0.62},
                                 {"notation": "R2", "label": "Far gauge", "lat": 51.5, "long": -0.1}]}).encode()


def rain():
    return json.dumps({"items": [{"dateTime": ago(hours=h).strftime("%Y-%m-%dT%H:%M:%SZ"), "value": 3.0}
                                 for h in range(1, 12)] + [{"dateTime": ago(days=3).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                            "value": 5.0}]}).encode()


def gwst():
    return json.dumps({"items": [{"label": "NEAR BOREHOLE", "lat": 54.45, "long": -0.6,
                                  "measures": [{"@id": "http://environment.data.gov.uk/hydrology/id/measures/abc-gw-dipped-i-mAOD-qualified"}]}]}).encode()


def gw():
    rows = []
    for y in range(1, 9):   # the same time of year in earlier years: 10 to 17 m
        rows.append({"date": (NOW.date() - dt.timedelta(days=365 * y + 5)).isoformat(), "value": 10.0 + y})
    rows.append({"date": (NOW.date() - dt.timedelta(days=10)).isoformat(), "value": 9.0})
    return json.dumps({"items": rows}).encode()


def ci():
    return json.dumps({"data": [{"from": ago(minutes=10).isoformat(), "intensity": {"forecast": 150, "actual": 140,
                                                                                    "index": "moderate"}}]}).encode()


def cimix():
    return json.dumps({"data": {"generationmix": [{"fuel": "wind", "perc": 40}, {"fuel": "gas", "perc": 30},
                                                  {"fuel": "coal", "perc": 0}]}}).encode()


def freq():
    return json.dumps({"data": [{"frequency": 50.01}, {"frequency": 49.97}, {"frequency": 50.02}]}).encode()


def margin():
    t = NOW.replace(minute=0, second=0, microsecond=0)
    return json.dumps({"data": [{"startTime": (t + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "publishTime": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "deratedMargin": 2500 + 400 * h,
                                 "lossOfLoadProbability": 0} for h in range(4)]}).encode()


def margind():
    return json.dumps({"data": [{"forecastDate": (NOW.date() + dt.timedelta(days=d)).isoformat(), "margin": 4000 + 100 * d}
                                for d in range(1, 5)]}).encode()


def dfs():
    return json.dumps({"result": {"records": [
        {"Delivery Date": NOW.date().isoformat(), "From_Local": "17:00", "To_Local": "17:30", "Event Type": "Down",
         "Service Requirement MW": 300},
        {"Delivery Date": NOW.date().isoformat(), "From_Local": "17:30", "To_Local": "18:00", "Event Type": "Down",
         "Service Requirement MW": 350}]}}).encode()


def water():
    return json.dumps({"features": [{"attributes": {"Region__c": "C", "JobGroup__c": "Supply", "JobType__c": "NO WATER",
                                                    "ReportedDate__c": int(ago(hours=2).timestamp() * 1000)},
                                     "geometry": {"x": -0.12, "y": 51.51}}]}).encode()


def wider_routes():
    return {"threat": (threat, "application/xml"), "ncsc": (ncsc, "application/xml"), "fcdo": (fcdo, "application/xml"),
            "dsearch": (dsearch, "application/json"), "govuk": (govuk, "application/json"),
            "floodrisk": (floodrisk, "text/html"), "floodareas": (floodrisk_areas, "application/json"), "rainst": (rainst, "application/json"),
            "rain": (rain, "application/json"), "gwst": (gwst, "application/json"), "gw": (gw, "application/json"),
            "ci": (ci, "application/json"), "cimix": (cimix, "application/json"), "freq": (freq, "application/json"),
            "margin": (margin, "application/json"), "margind": (margind, "application/json"),
            "dfs": (dfs, "application/json"), "water": (water, "application/json"),
            "places": (places, "application/json")}


def wider_urls(b):
    return {"threat": b + "threat", "cyber": b + "ncsc", "travel": b + "fcdo", "drought_search": b + "dsearch",
            "govuk_content": b + "govuk", "floodrisk": b + "floodrisk", "floodrisk_areas": b + "floodareas", "rain_stations": b + "rainst",
            "rain": b + "rain/{id}?since={since}", "gw_stations": b + "gwst", "gw": b + "gw/{id}?{query}",
            "ci_now": b + "ci", "ci_mix": b + "cimix", "frequency": b + "freq?from={start}&to={end}",
            "margin": b + "margin?from={start}&to={end}", "margin_daily": b + "margind", "dfs": b + "dfs?",
            "water": b + "water", "places": b + "places"}


# -- The rest of the UK (1.15.0): stand-ins for the regional providers, in the shapes their real feeds had on
# 17 November 2026. Neutral homes in city centres: Glasgow (SEPA), Cardiff (Natural Resources Wales), Belfast (NIE
# Networks, NI Water), Manchester (Electricity North West), Plymouth (South West Water), Whitby (Yorkshire Water).
GLASGOW = (55.861, -4.251)
CARDIFF = (51.4816, -3.1791)
BELFAST = (54.597, -5.930)
MANCHESTER = (53.479, -2.245)
PLYMOUTH = (50.3755, -4.1427)
BIRMINGHAM = (52.4796, -1.9026)
LONDON = (51.507, -0.128)
WHITBY = (54.486, -0.615)


def z(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def square(lat, lon, d=0.01):
    """A small outline round a point, as [lon, lat] rings (ArcGIS, South West Water)."""
    return [[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]


def sepa_floods():
    return json.dumps({"features": [
        {"attributes": {"fwa_name": "White Cart Water at Pollokshaws", "local_authority": "Glasgow City",
                        "severity": "Flood Warning", "message": "Flooding is expected.",
                        "updatedTime": int(ago(hours=2).timestamp() * 1000)},
         "geometry": {"rings": [square(GLASGOW[0] - 0.02, GLASGOW[1])]}},                  # 2 km away
        {"attributes": {"fwa_name": "Tarbert", "local_authority": "Comhairle nan Eilean Siar", "severity": None},
         "geometry": {"rings": [square(57.9, -6.8)]}},                                    # not in force
        {"attributes": {"fwa_name": "River Ness at Inverness", "severity": "Severe Flood Warning"},
         "geometry": {"rings": [square(57.47, -4.23)]}}]}).encode()                       # far away


def sepa_alerts():
    return json.dumps({"features": [
        {"attributes": {"name": "Glasgow and Clyde", "severity": "Flood Alert", "message": "Be prepared.",
                        "startTime": int(ago(hours=3).timestamp() * 1000)},
         "geometry": {"rings": [square(GLASGOW[0], GLASGOW[1], 0.3)]}}]}).encode()      # home is inside


def nrw_floods():
    data = {"messages": [
        {"name": {"english": "River Taff at Cardiff", "welsh": "Afon Taf yng Nghaerdydd"}, "issued": "2026-11-17T07:12:00",
         "updated": "2026-11-17T07:12:00", "uri": "/Detail/101WAF1/", "severity": 2, "fwaCode": "101WAF1", "active": True,
         "type": "W", "severityName": "Flood Warning", "point": {"x": 318132, "y": 176562},
         "description": {"english": "Properties near the River Taff in Cardiff"}},
        {"name": {"english": "Old one"}, "severity": 4, "fwaCode": "X", "active": True, "point": {"x": 318132, "y": 176562}},
        {"name": {"english": "Rivers Gwendraeths"}, "severity": 3, "fwaCode": "102WABF14", "active": True, "type": "A",
         "point": {"x": 245854.8, "y": 207572.0}}],                                       # Carmarthenshire: far
        "lastLiveMessage": None, "lastRefresh": "2026-11-17T09:51:00"}
    return ('<html><script>require(["/js/index.js"], function (app) { app.Landing.Page.setData("https://tiles.example/", '
            + json.dumps(data) + ', "101WAF1"); });</script></html>').encode()


def sepa_level(no, name, river, lat, lon, value, low, high, top):
    return {"station_no": no, "station_name": name, "river_name": river, "station_latitude": lat, "station_longitude": lon,
            "value": value, "timestamp": ago(minutes=20).strftime("%Y-%m-%dT%H:%M:00"),
            "sepa_median_annual_minimum_level": low, "sepa_median_annual_maximum_level": high, "sepa_maximum_level": top}


def sepa_rivers():
    return json.dumps([
        sepa_level(84001, "Dalsholm", "Kelvin", 55.89, -4.30, 0.6, 0.3, 2.1, 3.9),          # near, normal
        sepa_level(84013, "Overlee", "White Cart Water", 55.81, -4.26, 2.4, 0.2, 2.0, 3.1),   # near, above its range
        sepa_level(84999, "Glasgow Tidal", "Clyde", 55.856, -4.26, 4.0, 0.1, 3.0, 4.5),      # a tide gauge
        sepa_level(7001, "Aberlour", "Spey", 57.48, -3.2, 3.3, 0.44, 2.63, 3.41),            # far
        {"station_no": 1, "station_name": "Broken", "station_latitude": 55.86}]).encode()


def sepa_rain_stations():
    return json.dumps([["station_no", "station_name", "station_latitude", "station_longitude", "ts_id"],
                       ["1", "Glasgow gauge", "55.87", "-4.29", "111"], ["2", "Far away gauge", "57.5", "-4.2", "222"]]).encode()


def sepa_rain():
    return json.dumps([{"ts_id": "111", "rows": "3", "columns": "Timestamp,Value",
                        "data": [[z(ago(hours=1)), 2.0], [z(ago(hours=30)), 5.0], [z(ago(days=9)), 9.0]]}]).encode()


def nrw_rain_stations():
    return json.dumps([{"monitoring_station_reference": "H1", "monitoring_station_name_en": "Llandaff Raingauge",
                        "latitude": "51.495", "longitude": "-3.215"},
                       {"monitoring_station_reference": "H2", "monitoring_station_name_en": "Cardiff river",
                        "latitude": "51.48", "longitude": "-3.18"}]).encode()


def nrw_rain_measures():
    return json.dumps([{"monitoring_station_reference": "H1", "measure_id": "H1 Rainfall Total 15min",
                        "measure_type_en": "Rainfall", "measure_status_name": "Online"},
                       {"monitoring_station_reference": "H2", "measure_id": "H2 Water Level Stage",
                        "measure_type_en": "Water Level", "measure_status_name": "Online"}]).encode()


def nrw_rain():
    return json.dumps([{"measureId": "H1 Rainfall Total 15min", "timestamp": ago(hours=h).strftime("%Y-%m-%d %H:%M:%S"),
                        "value": v} for h, v in ((2, "1.5"), (3, "0.5"), (50, "4.0"))]).encode()


def sff(minor=True):
    item = ('<item><title>Scottish Flood Forecast - %s</title><link>https://scottishfloodforecast.sepa.org.uk?d=%s</link>'
            '%s<description><![CDATA[%s]]></description><pubDate>%s</pubDate></item>')
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Scottish Flood Forecast</title>' +
            item % ("old", "old", "", "No significant flooding is expected over the next three days.", rfc(ago(days=1))) +
            (item % ("new", "new", '<enclosure url="https://scottishfloodforecast.sepa.org.uk/build/assets/minor-flooding-'
                     'possible.png" type="image/png" />', "Minor river flooding is possible in the west on Wednesday. "
                     "Further rain is expected.", rfc(ago(hours=2))) if minor else "") +
            '</channel></rss>').encode()


def enwl():
    return json.dumps({"TotalResults": 3, "Items": [
        {"Type": "CurrentFault", "faultNumber": "INC 1", "faultStatus": "We're on site", "region": "Ancoats, Manchester",
         "consumersOff": 126, "date": "2026-11-17T08:00:00", "estimatedTimeOfRestoration": "2026-11-17T13:00:00",
         "actualTimeOfRestoration": None, "outageCentrePoint": {"lat": 53.485, "lng": -2.23},
         "AffectedPostcodes": " M4 5AA, M4 5AB"},
        {"Type": "ResolvedFault", "faultNumber": "INC 2", "consumersOff": 6, "outageCentrePoint": {"lat": 53.48, "lng": -2.24}},
        {"Type": "FuturePlannedWorks", "faultNumber": "INC 3", "consumersOff": 9,
         "outageCentrePoint": {"lat": 53.48, "lng": -2.24}}]}).encode()


def nie():
    return json.dumps({"escalationInfo": None, "outageMessage": [
        {"outageId": "5950522", "outageType": "Fault", "point": {"coordinates": "333770.0,374061.0"}, "numCustAffected": "17",
         "postCode": "BT1 1", "fullPostCodes": "BT1 1", "startTime": "8:05 AM, 17 Nov",
         "estRestoreFullDateTime": "Not available - Update to follow", "statusMessage": "A repair team has been assigned."},
        {"outageId": "2020/1", "outageType": "Planned", "point": {"coordinates": "333770.0,374061.0"}, "numCustAffected": "2",
         "postCode": "BT2 1", "estRestoreFullDateTime": "5:00 PM, 16 Nov 2020", "statusMessage": "Planned maintenance."},
        {"outageId": "x", "outageType": "Fault", "point": {"coordinates": "not here"}}]}).encode()


def yorkshire():
    def event(cat, title, lat, lon, update="Engineers are on site.", radius=1500):
        return {"category": cat, "title": title, "latitude": lat, "longitude": lon, "radiusDistance": radius,
                "latestUpdate": update, "location": "Somewhere", "lastUpdated": ago(hours=1).strftime("%Y-%m-%dT%H:%M:%S"),
                "detailsUrl": "https://www.yorkshirewater.com/your-water/problems-in-your-area/?incidentRef=1"}
    return json.dumps({"data": [
        event("Water supply", "No water or low water pressure in this area", WHITBY[0] + 0.005, WHITBY[1]),   # yours
        event("Bursts and leaks", "Burst or leak reported in this area", WHITBY[0], WHITBY[1] + 0.01,
              update="We've finished our work and the issue should now be resolved."),                   # put right
        event("Roadworks", "Roadworks reported in this area", WHITBY[0], WHITBY[1]),                       # not water
        event("Water quality", "Your water may look different", 54.0, -1.0)]}).encode()                   # far


def southwest():
    start, end = ago(hours=2).isoformat(), ago(hours=-6).isoformat()

    def job(cat, place, lat, lon, desc="<P>Some customers may have no water.</P>", ring=None, s=start, e=end):
        return {"categoryTitle": cat, "address": place, "coordinatesString": "%s %s" % (lat, lon),
                "polygon": {"polygonPoints": ring or []}, "description": desc, "startDate": s, "endDate": e}
    return json.dumps({"serviceData": [
        job("Unplanned interruption", "Union Street, Plymouth, Union Street, Plymouth, PL1 2AB", PLYMOUTH[0] + 0.004,
            PLYMOUTH[1], ring=square(PLYMOUTH[0], PLYMOUTH[1], 0.01)),                    # home's inside its outline
        job("Reported Leak", "", PLYMOUTH[0] + 0.01, PLYMOUTH[1]),
        job("South West Lakes Trust", "Burrator", 50.5, -4.03),                           # not supply
        job("Unplanned interruption", "Stoke, Plymouth", PLYMOUTH[0], PLYMOUTH[1] - 0.02,
            desc="<P>We would like to thank our customers for their patience.</P>"),     # finished
        job("Planned Interruption", "Plympton", 50.39, -4.05, s=ago(hours=30).isoformat(), e=ago(hours=3).isoformat())]}).encode()


def niwater():
    def block(n, status, cat, lat, lon, what, title, start=""):
        return ('<div class="site grid-item %s" data-event-id="%s" data-event-status="%s" data-id="1" data-category="%s">'
                '<ul class="update-events hidden"><li>%s,%s</li></ul><div class="detail-banner"><h3><strong>%s</strong><br />'
                '<span class="date">Last updated: 17 November 2026 09:05</span></h3></div><h3 class="title">%s</h3>'
                '<div class="content"><p><span class="date">Last updated: 17 November 2026 09:05 </span>%s'
                '| <span class="restoration">Estimated restoration time: 17 November 2026 16:00</span></p></div>'
                '<div class="content"><p>NI Water is aware of a loss of supply in your area.</p></div></div>'
                % (cat, n, status, cat, lat, lon, what, title, start))
    return ("<div>" + block(1, "Active", "water-supply-interruption", BELFAST[0] + 0.003, BELFAST[1], "Water Supply Interruption",
                            "Belfast - BT1", '| <span class="starttime">Estimated start time: 17 November 2026 08:15</span>') +
            block(2, "Active", "planned-maintenance", 54.27, -6.43, "Planned Maintenance", "Newry - BT35") +
            block(3, "Closed", "water-supply-interruption", BELFAST[0], BELFAST[1], "Water Supply Interruption",
                  "Belfast - BT2") + "</div>").encode()


def regional_routes():
    return {"sepafloods": (sepa_floods, "application/json"), "sepaalerts": (sepa_alerts, "application/json"),
            "nrwfloods": (nrw_floods, "text/html"), "separivers": (sepa_rivers, "application/json"),
            "separainst": (sepa_rain_stations, "application/json"), "separain": (sepa_rain, "application/json"),
            "nrwrainst": (nrw_rain_stations, "application/json"), "nrwrainms": (nrw_rain_measures, "application/json"),
            "nrwrain": (nrw_rain, "application/json"), "sff": (sff, "application/xml"),
            "enwl": (enwl, "application/json"), "nie": (nie, "application/json"),
            "yorkshire": (yorkshire, "application/json"), "southwest": (southwest, "application/json"),
            "bournemouth": (southwest, "application/json"), "niwater": (niwater, "text/html")}


def regional_urls(b):
    return {"sepa_floods": b + "sepafloods", "sepa_alerts": b + "sepaalerts", "nrw_floods": b + "nrwfloods",
            "sepa_rivers": b + "separivers", "sepa_rain_stations": b + "separainst", "sepa_rain": b + "separain?ts_id={id}",
            "nrw_rain_stations": b + "nrwrainst", "nrw_rain_measures": b + "nrwrainms",
            "nrw_rain": b + "nrwrain?measureId={id}&start={start}&end={end}", "sff": b + "sff", "power_enwl": b + "enwl",
            "power_nie": b + "nie", "water_yorkshire": b + "yorkshire", "water_southwest": b + "southwest",
            "water_bournemouth": b + "bournemouth", "water_ni": b + "niwater"}
