import csv
import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)
app.context_processor(lambda: dict(enumerate=enumerate))

@app.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)

CSV_BABY = 'baby_info.csv'
CSV_SLEEP = 'sleep_log.csv'
CSV_FEED = 'feeding_log.csv'

html = """
<!DOCTYPE html>
<html>
<head>
    <title>Baby Sleep Tracker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body { font-family: Arial, sans-serif; margin: 12px; }
      input, button { font-size: 1em; }
      form { margin-bottom: 1.5em; }
      .advice-box { background:#f0f0f0; padding:1em; border-radius:8px; margin-bottom: 1em; }
      @media (max-width: 600px) {
        body { font-size: 1.1em; }
        input, button { width: 100%; margin-bottom: 0.5em; }
      }
    </style>
</head>
<body>
    <h1>Baby Sleep Tracker</h1>
    <h2>Baby Info</h2>
    <form method="POST" action="/">
        <label for="name">Baby's Name:</label>
        <input type="text" id="name" name="name" value="{{ name or '' }}" required>
        <label for="birthday">Birthday:</label>
        <input type="date" id="birthday" name="birthday" value="{{ birthday or '' }}" required>
        <button type="submit">Save</button>
    </form>
    {% if name and birthday %}
        <p><strong>Name:</strong> {{ name }}</p>
        <p><strong>Birthday:</strong> {{ birthday }}</p>
        <p><strong>Age:</strong> {{ age_days }} days ({{ age_weeks }} weeks)</p>
    {% endif %}

    {% if advice %}
        <div class="advice-box">
            <h2>Advice for Week {{ age_weeks }}</h2>
            <div>{{ advice }}</div>
        </div>
    {% endif %}

    <div class="advice-box">
      <h3>Today's Summary</h3>
      <ul>
        <li>Last feeding: {{ last_feed_time_str or 'N/A' }} ({{ last_feed_ago or 'N/A' }} ago)</li>
        <li>Last sleep ended: {{ last_sleep_end_str or 'N/A' }} ({{ last_sleep_ago or 'N/A' }} ago)</li>
        <li>Total sleep in last 24h: {{ total_sleep_24h }} hours</li>
        <li>Total feedings in last 24h: {{ total_feeds_24h }}</li>
      </ul>
      {% if next_feed_suggestion %}
        <div style="margin-top:0.5em;"><strong>Tip:</strong> {{ next_feed_suggestion }}</div>
      {% endif %}
    </div>

    <h2>Log Sleep</h2>
    <form method="POST" action="/log_sleep">
        <label for="sleep_start">Sleep Start:</label>
        <input type="datetime-local" id="sleep_start" name="sleep_start" required>
        <label for="sleep_end">Sleep End:</label>
        <input type="datetime-local" id="sleep_end" name="sleep_end" required>
        <button type="submit">Log Sleep</button>
    </form>

    <h3>Recent Sleep Logs</h3>
<ul>
{% for idx, sleep in enumerate(sleep_logs) %}
    <li>{{ sleep[0] }} to {{ sleep[1] }}
        <form method="POST" action="/delete_sleep" style="display:inline;">
            <input type="hidden" name="index" value="{{ idx }}">
            <button type="submit" class="delete-button">Delete</button>
        </form>
    </li>
{% endfor %}
</ul>

    <h2>Log Feeding</h2>
<form method="POST" action="/log_feed">
    <label for="feed_time">Feeding Time:</label>
    <input type="datetime-local" id="feed_time" name="feed_time" required>
    <label for="amount">Amount (oz):</label>
    <input type="number" id="amount" name="amount" step="0.1" min="0">
    <label for="side">Breast Side:</label>
    <select id="side" name="side">
        <option value="">N/A</option>
        <option value="Left">Left</option>
        <option value="Right">Right</option>
        <option value="Both">Both</option>
    </select>
    <label for="notes">Notes:</label>
    <input type="text" id="notes" name="notes">
    <button type="submit">Log Feeding</button>
</form>

    <h3>Recent Feeding Logs</h3>
<ul>
{% for idx, feed in enumerate(feed_logs) %}
    <li>
        {{ feed[0] }} | {{ feed[1] }} oz | {{ feed[2] }} | {{ feed[3] if feed|length > 3 else '' }}
        <form method="POST" action="/delete_feed" style="display:inline;">
            <input type="hidden" name="index" value="{{ idx }}">
            <button type="submit" class="delete-button">Delete</button>
        </form>
    </li>
{% endfor %}
</ul>
</body>
</html>
"""

def load_baby_info():
    if os.path.exists(CSV_BABY):
        with open(CSV_BABY, newline='') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip header row
            for row in reader:
                if len(row) == 2:
                    return row[0], row[1]
    return None, None

def save_baby_info(name, birthday):
    with open(CSV_BABY, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Name", "Birthday"])  # Header
        writer.writerow([name, birthday])

def append_csv(filename, row):
    file_exists = os.path.exists(filename)
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            # Add headers based on filename
            if filename == CSV_FEED:
                writer.writerow(["Time", "Amount", "Side", "Notes"])
            elif filename == CSV_SLEEP:
                writer.writerow(["Start", "End"])
        writer.writerow(row)

def load_recent(filename, num=5):
    if not os.path.exists(filename):
        return []
    with open(filename, newline='') as csvfile:
        rows = list(csv.reader(csvfile))
        return rows[-num:]

def load_all(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        try:
            has_header = csv.Sniffer().has_header(csvfile.read(1024))
            csvfile.seek(0)
            if has_header:
                next(reader)  # Skip header
        except:
            pass
        return list(reader)

def calculate_age(birthday_str):
    try:
        birthday = datetime.strptime(birthday_str, "%Y-%m-%d").date()
        today = date.today()
        delta = today - birthday
        age_days = delta.days
        age_weeks = age_days // 7
        return age_days, age_weeks
    except Exception:
        return None, None

def total_sleep_last_24h(sleep_logs):
    now = datetime.now()
    total_seconds = 0
    for sleep in sleep_logs:
        try:
            start = datetime.strptime(sleep[0], "%Y-%m-%dT%H:%M")
            end = datetime.strptime(sleep[1], "%Y-%m-%dT%H:%M")
            if end > now:
                end = now
            if end > now - timedelta(days=1):
                sleep_start = max(start, now - timedelta(days=1))
                total_seconds += (end - sleep_start).total_seconds()
        except Exception:
            continue
    return round(total_seconds / 3600, 1)

def total_feeding_last_24h(feed_logs):
    now = datetime.now()
    total_oz = 0.0
    for feed in feed_logs:
        try:
            feed_time = datetime.strptime(feed[0], "%Y-%m-%dT%H:%M")
            if feed_time > now - timedelta(days=1):
                total_oz += float(feed[1] or 0)
        except Exception:
            continue
    return round(total_oz, 1)

def night_sleep_advice(sleep_logs, birthday):
    try:
        today = datetime.now().date()
        birthday_date = datetime.strptime(birthday, "%Y-%m-%d").date()
        age_weeks = (today - birthday_date).days // 7
        if age_weeks < 8:
            return None

        night_start = datetime.combine(today, datetime.min.time()) + timedelta(hours=19)
        night_end = night_start + timedelta(hours=12)
        longest_night_sleep = 0

        for sleep in sleep_logs:
            start = datetime.strptime(sleep[0], "%Y-%m-%dT%H:%M")
            end = datetime.strptime(sleep[1], "%Y-%m-%dT%H:%M")
            if end > night_start and start < night_end:
                overlap_start = max(start, night_start)
                overlap_end = min(end, night_end)
                duration = (overlap_end - overlap_start).total_seconds() / 3600
                longest_night_sleep = max(longest_night_sleep, duration)

        if longest_night_sleep >= 11.5:
            return "Great job! Baby achieving ~12h night sleep."
        elif longest_night_sleep >= 8:
            return "Night sleep: {:.1f}h - aim for 12h gradually.".format(longest_night_sleep)
        else:
            return "Night sleep: {:.1f}h - focus on reducing night feeds.".format(longest_night_sleep)
    except Exception:
        return None

def feeding_schedule_advice(feed_logs, birthday):
    try:
        today = datetime.now().date()
        birthday_date = datetime.strptime(birthday, "%Y-%m-%d").date()
        age_weeks = (today - birthday_date).days // 7
        if age_weeks < 4:
            return None

        feeding_times = []
        for feed in feed_logs:
            feed_time = datetime.strptime(feed[0], "%Y-%m-%dT%H:%M")
            if 7 <= feed_time.hour < 19:
                feeding_times.append(feed_time)

        feeding_times.sort()
        intervals = []
        for i in range(1, len(feeding_times)):
            diff = (feeding_times[i] - feeding_times[i-1]).total_seconds() / 3600
            intervals.append(diff)

        if not intervals:
            return "Log more daytime feedings for schedule analysis"

        avg_interval = sum(intervals) / len(intervals)
        if 3.5 <= avg_interval <= 4.5:
            return "Good feeding spacing: avg {:.1f}h".format(avg_interval)
        else:
            return "Adjust feeding spacing: current avg {:.1f}h".format(avg_interval)
    except Exception:
        return None


def get_advice(age_weeks, sleep_logs, feed_logs, birthday, last_side=None):
    base_advice = []
    
    # Add core age-based advice
    if age_weeks is None:
        return None
    if age_weeks < 4:
        base_advice.append("Focus on feeding and bonding. Track weight gain and daily ounces.")
    elif 4 <= age_weeks < 8:
        base_advice.append("Establish 4 daytime feedings every 4 hours. Notice sleep patterns.")
    elif 8 <= age_weeks < 12:
        base_advice.append("Gradually reduce night feedings. Strengthen bedtime routine.")
    elif age_weeks >= 12:
        base_advice.append("Maintain 12-hour night sleep. Celebrate your progress!")
    
    # Add quantitative advice from logs
    total_sleep = total_sleep_last_24h(sleep_logs)
    total_feeding = total_feeding_last_24h(feed_logs)
    
    sleep_advice = []
    if age_weeks >= 8:
        night_advice = night_sleep_advice(sleep_logs, birthday)
        if night_advice:
            sleep_advice.append(night_advice)
    
    if total_sleep < 14 and age_weeks < 8:
        sleep_advice.append("Aim for 14-17 hours total sleep daily. Current: {:.1f}h".format(total_sleep))
    
    # Add feeding schedule advice
    feeding_advice = []
    if age_weeks >= 4:
        feed_schedule = feeding_schedule_advice(feed_logs, birthday)
        if feed_schedule:
            feeding_advice.append(feed_schedule)
    
    if total_feeding < 24 and age_weeks >= 4:
        feeding_advice.append("Daily intake below 24oz. Current: {:.1f}oz".format(total_feeding))
    
    # Add breast side advice
    if last_side:
        if last_side == "Left":
            base_advice.append("Last feeding was left breast - consider right next.")
        elif last_side == "Right":
            base_advice.append("Last feeding was right breast - consider left next.")
        elif last_side == "Both":
            base_advice.append("Both breasts used last feeding - monitor baby's fullness.")
    
    # Combine all advice
    full_advice = base_advice + sleep_advice + feeding_advice
    return " ".join(full_advice) if full_advice else None

def get_last_feed_info(feed_logs):
    if not feed_logs:
        return None, None, None, None
    last_feed = feed_logs[-1]
    # Update indices to match new CSV structure [time, amount, side, notes]
    last_feed_time_str = last_feed[0]
    try:
        last_feed_time = datetime.strptime(last_feed_time_str, "%Y-%m-%dT%H:%M")
        now = datetime.now()
        delta = now - last_feed_time
        hours_ago = int(delta.total_seconds() // 3600)
        minutes_ago = int((delta.total_seconds() % 3600) // 60)
        last_feed_ago = f"{hours_ago}h {minutes_ago}m"
        return last_feed_time_str.replace("T", " "), last_feed_ago, last_feed_time, now
    except Exception:
        return last_feed_time_str, "N/A", None, None

def get_last_sleep_info(sleep_logs):
    if not sleep_logs:
        return None, None
    last_sleep = sleep_logs[-1]
    last_sleep_end_str = last_sleep[1]
    try:
        last_sleep_end = datetime.strptime(last_sleep_end_str, "%Y-%m-%dT%H:%M")
        now = datetime.now()
        delta = now - last_sleep_end
        hours_ago = int(delta.total_seconds() // 3600)
        minutes_ago = int((delta.total_seconds() % 3600) // 60)
        last_sleep_ago = f"{hours_ago}h {minutes_ago}m"
        return last_sleep_end_str.replace("T", " "), last_sleep_ago
    except Exception:
        return last_sleep_end_str, "N/A"

def get_total_sleep_24h(sleep_logs):
    now = datetime.now()
    total_seconds = 0
    for sleep in sleep_logs:
        try:
            start = datetime.strptime(sleep[0], "%Y-%m-%dT%H:%M")
            end = datetime.strptime(sleep[1], "%Y-%m-%dT%H:%M")
            if end > now:
                end = now
            if end > now - timedelta(days=1):
                # Only count the portion in the last 24h
                sleep_start = max(start, now - timedelta(days=1))
                total_seconds += (end - sleep_start).total_seconds()
        except Exception:
            continue
    return round(total_seconds / 3600, 2)

def get_total_feeds_24h(feed_logs):
    now = datetime.now()
    count = 0
    for feed in feed_logs:
        try:
            feed_time = datetime.strptime(feed[0], "%Y-%m-%dT%H:%M")  # [0] is time
            if feed_time > now - timedelta(days=1):
                count += 1
        except Exception:
            continue
    return count

def get_next_feed_suggestion(last_feed_time, now, age_weeks):
    if last_feed_time is None or now is None:
        return None
    if age_weeks is None:
        return None
    # Book's general advice: 4 hours between feeds after week 4
    if age_weeks >= 4:
        next_feed_time = last_feed_time + timedelta(hours=4)
        delta = next_feed_time - now
        if delta.total_seconds() > 0:
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            return f"Next feeding in about {hours}h {minutes}m"
        else:
            return "It's time for the next feeding!"
    return None

def get_last_breast_side(feed_logs):
    for feed in reversed(feed_logs):
        if len(feed) >= 3:  # [2] is the side
            side = feed[2].strip()
            if side in ["Left", "Right", "Both"]:
                return side
    return None


@app.route("/", methods=["GET", "POST"])
def home():
    name, birthday = load_baby_info()
    age_days, age_weeks = None, None
    advice = None
    
    sleep_logs = load_all(CSV_SLEEP)
    feed_logs = load_all(CSV_FEED)

    if name and birthday:
        age_days, age_weeks = calculate_age(birthday)
        advice = get_advice(age_weeks, sleep_logs, feed_logs, birthday) if age_weeks is not None else None

    if request.method == "POST":
        name = request.form["name"]
        birthday = request.form["birthday"]
        save_baby_info(name, birthday)
        return redirect(url_for('home'))

    sleep_logs = load_all(CSV_SLEEP)
    feed_logs = load_all(CSV_FEED)
    recent_sleep = sleep_logs[-5:] if sleep_logs else []
    recent_feed = feed_logs[-5:] if feed_logs else []

    last_feed_time_str, last_feed_ago, last_feed_time, now = get_last_feed_info(feed_logs)
    last_sleep_end_str, last_sleep_ago = get_last_sleep_info(sleep_logs)
    total_sleep_24h = get_total_sleep_24h(sleep_logs)
    total_feeds_24h = get_total_feeds_24h(feed_logs)
    next_feed_suggestion = get_next_feed_suggestion(last_feed_time, now, age_weeks)
    last_side = get_last_breast_side(feed_logs)
    advice = get_advice(age_weeks, sleep_logs, feed_logs, birthday, last_side)

    return render_template_string(
        html,
        name=name,
        birthday=birthday,
        age_days=age_days,
        age_weeks=age_weeks,
        advice=advice,
        sleep_logs=recent_sleep,
        feed_logs=recent_feed,
        last_feed_time_str=last_feed_time_str,
        last_feed_ago=last_feed_ago,
        last_sleep_end_str=last_sleep_end_str,
        last_sleep_ago=last_sleep_ago,
        total_sleep_24h=total_sleep_24h,
        total_feeds_24h=total_feeds_24h,
        next_feed_suggestion=next_feed_suggestion
    )

@app.route("/log_sleep", methods=["POST"])
def log_sleep():
    sleep_start = request.form["sleep_start"]
    sleep_end = request.form["sleep_end"]
    append_csv(CSV_SLEEP, [sleep_start, sleep_end])
    return redirect(url_for('home'))

@app.route("/log_feed", methods=["POST"])
def log_feed():
    feed_time = request.form["feed_time"]
    amount = request.form["amount"]
    side = request.form["side"]
    notes = request.form["notes"]
    append_csv(CSV_FEED, [feed_time, amount, side, notes])
    return redirect(url_for('home'))

@app.route("/delete_sleep", methods=["POST"])
def delete_sleep():
    index = int(request.form["index"])
    if os.path.exists(CSV_SLEEP):
        with open(CSV_SLEEP, newline='') as csvfile:
            rows = list(csv.reader(csvfile))
        if 0 <= index < len(rows):
            rows.pop(index)
            with open(CSV_SLEEP, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(rows)
    return redirect(url_for('home'))

@app.route("/delete_feed", methods=["POST"])
def delete_feed():
    index = int(request.form["index"])
    if os.path.exists(CSV_FEED):
        with open(CSV_FEED, newline='') as csvfile:
            rows = list(csv.reader(csvfile))
        if 0 <= index < len(rows):
            rows.pop(index)
            with open(CSV_FEED, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(rows)
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)