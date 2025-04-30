import csv
import os
os.environ['TZ'] = 'America/Los_Angeles'
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import pytz

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-123'  # For session

@app.route('/set_timezone', methods=['POST'])
def set_timezone():
    timezone = request.json.get('timezone', 'UTC')
    session['user_timezone'] = timezone
    return jsonify({'status': 'success'})

app.context_processor(lambda: dict(enumerate=enumerate))

@app.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)

CSV_BABY = 'baby_info.csv'
CSV_SLEEP = 'sleep_log.csv'
CSV_FEED = 'feeding_log.csv'
CURRENT_SLEEP_FILE = 'current_sleep.txt'

html = """
<!DOCTYPE html>
<html>
<head>

<script>

// Timezone detection script
    document.addEventListener('DOMContentLoaded', function() {
        try {
            const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            console.log('Detected timezone:', timezone);
            fetch('/set_timezone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ timezone: timezone })
            });
        } catch (error) {
            console.error('Error detecting/sending timezone:', error);
        }
    });

// Preserve form values on page reload
window.addEventListener('beforeunload', function() {
    const sleepStart = document.getElementById('sleep_start').value;
    const sleepEnd = document.getElementById('sleep_end').value;
    if(sleepStart) sessionStorage.setItem('sleep_start', sleepStart);
    if(sleepEnd) sessionStorage.setItem('sleep_end', sleepEnd);
});

// Restore form values on page load
document.addEventListener('DOMContentLoaded', function() {
    // Only clear if there is no session data AND no server-tracked sleep
    const sleepStatus = document.getElementById('sleepStatus');
    const hasOngoingSleep = sleepStatus && sleepStatus.textContent.includes('ongoing');
    if (!sessionStorage.getItem('sleep_start') && !hasOngoingSleep) {
        document.getElementById('sleep_start').value = '';
        document.getElementById('sleep_end').value = '';
    }
});


// Clear fields on initial load if no session data
if(!sessionStorage.getItem('sleep_start')) {
    document.getElementById('sleep_start').value = '';
    document.getElementById('sleep_end').value = '';
}
</script>


</script>
    <title>The Tank Tracker</title>
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
    <h1>The Tank Tracker</h1>
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
        <li>Total feedings in last 24h: {{ total_feeds_count }} ({{ total_feeds_oz }}oz total)</li>
      </ul>
      {% if next_feed_suggestion %}
        <div style="margin-top:0.5em;"><strong>Tip:</strong> {{ next_feed_suggestion }}</div>
      {% endif %}
    </div>

    <h2>Log Sleep</h2>
<div id="sleepStatus" style="margin-bottom:1em;">
</div>

<form method="POST" action="/log_sleep" id="sleepForm">
    <div style="margin-bottom: 0.5em;">
        <button type="button" id="sleepStartBtn" {% if current_sleep %}disabled{% endif %}>
            Start Sleep Now
        </button>
        <button type="button" id="sleepEndBtn" {% if not current_sleep %}disabled{% endif %}>
            End Sleep Now
        </button>
    </div>
    <label for="sleep_start">Sleep Start:</label>
    <input type="datetime-local" id="sleep_start" name="sleep_start">
    <label for="sleep_end">Sleep End:</label>
    <input type="datetime-local" id="sleep_end" name="sleep_end">
    <input type="hidden" id="sleep_was_tracked" name="sleep_was_tracked" value="0">
    <button type="submit">Log Sleep</button>
</form>


<script>
document.getElementById('sleepStartBtn').addEventListener('click', function() {
    fetch('/start_sleep', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Convert UTC to local time correctly
                const utcDate = new Date(data.start_time + 'Z');
                const localDate = new Date(utcDate.getTime() - (utcDate.getTimezoneOffset() * 60000));
                const localISOTime = localDate.toISOString().slice(0, 16);
                
                // Update UI elements
                document.getElementById('sleep_start').value = localISOTime;
                document.getElementById('sleepStatus').innerHTML = 
                    `⏳ Sleep ongoing since ${utcDate.toLocaleTimeString('en-US', { 
                        hour: '2-digit', 
                        minute: '2-digit',
                        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
                    })}`;
                document.getElementById('sleepEndBtn').disabled = false;
                document.getElementById('sleepStartBtn').disabled = true;
            }
        });
});

document.getElementById('sleepEndBtn').addEventListener('click', function() {
    fetch('/end_sleep', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Use the server UTC time, convert to local for input field
                const utcDate = new Date(data.end_time + 'Z');
                const localDate = new Date(utcDate.getTime() - (utcDate.getTimezoneOffset() * 60000));
                const localISOTime = localDate.toISOString().slice(0, 16);

                document.getElementById('sleep_end').value = localISOTime;
                document.getElementById('sleepStatus').innerHTML = '';
                document.getElementById('sleepEndBtn').disabled = true;
                document.getElementById('sleepStartBtn').disabled = false;

                // Clear session storage
                sessionStorage.removeItem('sleep_start');
                sessionStorage.removeItem('sleep_end');

                document.getElementById('sleep_was_tracked').value = "1";
            }
        });
});


</script>




    <h3>Recent Sleep Logs</h3>
<ul>
{% for entry, original_index in sleep_logs_with_index %}
    <li>{{ entry[0] }} to {{ entry[1] }}
        <form method="POST" action="/delete_sleep" style="display:inline;">
            <input type="hidden" name="index" value="{{ original_index }}">
            <button type="submit" class="delete-button">Delete</button>
        </form>
    </li>
{% endfor %}
</ul>

    <h2>Log Feeding</h2>
<form method="POST" action="/log_feed" id="feedingForm">
    <label for="feeding_type">Feeding Type:</label>
    <select id="feeding_type" name="feeding_type" required>
        <option value="">Select...</option>
        <option value="breast">Breast</option>
        <option value="bottle">Bottle</option>
    </select>

    <!-- Breast Feeding Fields -->
<div id="breastFields" style="display:none;">
    <div style="margin-bottom: 0.5em;">
        <button type="button" id="breastStartBtn" style="margin-right: 0.5em;">Start Feeding Now</button>
        <button type="button" id="breastEndBtn">End Feeding Now</button>
    </div>
    
    <label for="feed_start">Feeding Start:</label>
    <input type="datetime-local" id="feed_start" name="feed_start" required>
    <label for="feed_end">Feeding End:</label>
    <input type="datetime-local" id="feed_end" name="feed_end" required>
    
    <label for="side">Breast Side:</label>
    <select id="side" name="side">
        <option value="">N/A</option>
        <option value="Left">Left</option>
        <option value="Right">Right</option>
        <option value="Both">Both</option>
    </select>
</div>

<script>
document.getElementById('breastStartBtn').addEventListener('click', function() {
    const now = new Date();
    const localISOTime = new Date(now.getTime() - (now.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
    document.getElementById('feed_start').value = localISOTime;
});

document.getElementById('breastEndBtn').addEventListener('click', function() {
    const now = new Date();
    const localISOTime = new Date(now.getTime() - (now.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
    document.getElementById('feed_end').value = localISOTime;
});
</script>


    <!-- Bottle Feeding Fields -->
    <div id="bottleFields" style="display:none;">
        <label for="bottle_start">Feeding Start:</label>
        <input type="datetime-local" id="bottle_start" name="bottle_start">
        <label for="amount">Amount (oz):</label>
        <input type="number" id="amount" name="amount" step="0.1" min="0">
    </div>

    <label for="notes">Notes:</label>
    <input type="text" id="notes" name="notes">
    <button type="submit">Log Feeding</button>
</form>

<script>
document.getElementById('feeding_type').addEventListener('change', function() {
    const breastFields = document.getElementById('breastFields');
    const bottleFields = document.getElementById('bottleFields');
    
    breastFields.style.display = this.value === 'breast' ? 'block' : 'none';
    bottleFields.style.display = this.value === 'bottle' ? 'block' : 'none';
    
    // Toggle required attributes
    document.querySelectorAll('#breastFields input, #breastFields select').forEach(el => {
        el.required = this.value === 'breast';
    });
    document.querySelectorAll('#bottleFields input').forEach(el => {
        el.required = this.value === 'bottle';
    });
});
</script>


    <h3>Recent Feeding Logs</h3>
<ul>
{% for entry, original_index in feed_logs_with_index %}
    <li>
        {{ entry[0] }} 
        {{ entry[1] }} to {{ entry[2] }} | 
        {{ entry[3] }} 
        {% if entry[4] %} | {{ entry[4] }}{% endif %}
        <form method="POST" action="/delete_feed" style="display:inline;">
            <input type="hidden" name="index" value="{{ original_index }}">
            <button type="submit" class="delete-button">Delete</button>
        </form>
    </li>
{% endfor %}
</ul>
</body>
</html>
"""

def to_user_timezone(naive_dt, timezone_str):
    """Convert naive UTC datetime to user's timezone."""
    try:
        utc_dt = naive_dt.replace(tzinfo=pytz.UTC)
        user_tz = pytz.timezone(timezone_str)
        return utc_dt.astimezone(user_tz)
    except Exception:
        return naive_dt

def format_datetime(dtstr, timezone_str='UTC'):
    """Convert 'YYYY-MM-DDTHH:MM' to local time."""
    try:
        naive_dt = datetime.strptime(dtstr, "%Y-%m-%dT%H:%M")
        user_tz = pytz.timezone(timezone_str)
        local_dt = naive_dt.replace(tzinfo=pytz.UTC).astimezone(user_tz)
        return local_dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return dtstr
app.jinja_env.globals.update(format_datetime=format_datetime)


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
            writer.writerow(["Type", "Start", "End", "Amount", "Side", "Notes"])
        writer.writerow(row)


def load_recent(filename, num=5):
    if not os.path.exists(filename):
        return []
    with open(filename, newline='') as csvfile:
        # Check for header
        has_header = csv.Sniffer().has_header(csvfile.read(1024))
        csvfile.seek(0)
        reader = csv.reader(csvfile)
        header_offset = 1 if has_header else 0
        
        # Read all rows
        rows = list(reader)
        
        # Separate header and data
        data_rows = rows[header_offset:]  # Skip header if present
        
        # Get most recent entries
        recent = data_rows[-num:]
        
        # Calculate original CSV indexes
        original_indexes = []
        for i, entry in enumerate(recent):
            # Find position in full CSV (header + data)
            csv_index = header_offset + (len(data_rows) - len(recent)) + i
            original_indexes.append(csv_index)
        
        return list(zip(recent, original_indexes))






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

def get_current_sleep():
    if os.path.exists(CURRENT_SLEEP_FILE):
        with open(CURRENT_SLEEP_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_current_sleep(sleep_data):
    with open(CURRENT_SLEEP_FILE, 'w') as f:
        f.write(sleep_data)

def clear_current_sleep():
    if os.path.exists(CURRENT_SLEEP_FILE):
        os.remove(CURRENT_SLEEP_FILE)



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

def get_last_feed_info(feed_logs, user_tz='UTC'):
    if not feed_logs:
        return None, None, None, None
    last_feed = feed_logs[-1]
    last_feed_time_str = last_feed[1]
    
    try:
        # 1. Parse stored UTC time
        utc_dt = datetime.strptime(last_feed_time_str, "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.UTC)
        
        # 2. Get current UTC time
        utc_now = datetime.now(pytz.UTC)
        
        # 3. Convert both to user's timezone
        user_tz_obj = pytz.timezone(user_tz)
        user_dt = utc_dt.astimezone(user_tz_obj)
        user_now = utc_now.astimezone(user_tz_obj)
        
        # 4. Calculate difference
        delta = user_now - user_dt
        hours_ago = int(delta.total_seconds() // 3600)
        minutes_ago = int((delta.total_seconds() % 3600) // 60)
        
        return user_dt.strftime("%b %d, %Y %I:%M %p"), f"{hours_ago}h {minutes_ago}m", utc_dt, utc_now
    except Exception as e:
        print(f"DEBUG [get_last_feed_info]: {str(e)}")
        return last_feed_time_str, "N/A", None, None

def get_last_sleep_info(sleep_logs, user_tz='UTC'):
    if not sleep_logs:
        return None, None
    last_sleep = sleep_logs[-1]
    last_sleep_end_str = last_sleep[1]
    
    try:
        # 1. Parse stored UTC time
        utc_dt = datetime.strptime(last_sleep_end_str, "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.UTC)
        
        # 2. Get current UTC time
        utc_now = datetime.now(pytz.UTC)
        
        # 3. Convert both to user's timezone
        user_tz_obj = pytz.timezone(user_tz)
        user_dt = utc_dt.astimezone(user_tz_obj)
        user_now = utc_now.astimezone(user_tz_obj)
        
        # 4. Calculate difference in user's local time
        delta = user_now - user_dt
        hours_ago = int(delta.total_seconds() // 3600)
        minutes_ago = int((delta.total_seconds() % 3600) // 60)
        
        return user_dt.strftime("%b %d, %Y %I:%M %p"), f"{hours_ago}h {minutes_ago}m"
    except Exception as e:
        print(f"DEBUG [get_last_sleep_info]: {str(e)}")
        return last_sleep_end_str, "N/A"

def get_total_sleep_24h(sleep_logs, user_tz='UTC'):
    user_tz_obj = pytz.timezone(user_tz)
    utc_now = datetime.now(pytz.UTC)
    user_now = utc_now.astimezone(user_tz_obj)
    
    total_seconds = 0
    for sleep in sleep_logs:
        try:
            # Parse stored UTC times
            start_utc = datetime.strptime(sleep[0], "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.UTC)
            end_utc = datetime.strptime(sleep[1], "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.UTC)
            
            # Convert to user's timezone
            start_user = start_utc.astimezone(user_tz_obj)
            end_user = end_utc.astimezone(user_tz_obj)
            
            # Calculate within last 24h in user's time
            if end_user > user_now - timedelta(days=1):
                sleep_start = max(start_user, user_now - timedelta(days=1))
                total_seconds += (end_user - sleep_start).total_seconds()
        except Exception:
            continue
    return round(total_seconds / 3600, 2)

def get_total_feeds_24h(feed_logs, user_tz='UTC'):
    user_tz_obj = pytz.timezone(user_tz)
    utc_now = datetime.now(pytz.UTC)
    user_now = utc_now.astimezone(user_tz_obj)
    
    total_count = 0
    total_oz = 0.0
    for feed in feed_logs:
        try:
            # Parse stored UTC time
            feed_utc = datetime.strptime(feed[1], "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.UTC)
            feed_user = feed_utc.astimezone(user_tz_obj)
            
            if feed_user > user_now - timedelta(days=1):
                total_count += 1
                # Sum the ounces from column index 3
                total_oz += float(feed[3])
        except Exception as e:
            print(f"Error processing feed log: {str(e)}")
            continue
    return total_count, round(total_oz, 1)


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
            side = feed[4].strip()
            if side in ["Left", "Right", "Both"]:
                return side
    return None

def calculate_feeding_amount(start_str, end_str):
    """Estimate ounces based on feeding duration (avg 0.5-1 oz per minute)."""
    try:
        start = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
        end = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
        duration_min = (end - start).total_seconds() / 60
        
        # Use average of 0.75 oz per minute (range 0.5-1 oz/min)
        estimated_oz = round(duration_min * 0.75, 1)
        return max(0.5, estimated_oz)  # Ensure at least 0.5 oz
    except Exception:
        return 0.0


@app.route("/", methods=["GET", "POST"])
def home():
    user_tz = session.get('user_timezone', 'UTC')
    print(f"DEBUG [home]: User timezone = {user_tz}")
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

    recent_sleep_with_index = [
        ([format_datetime(entry[0], user_tz), format_datetime(entry[1], user_tz)], idx)
        for entry, idx in load_recent(CSV_SLEEP, 5)
    ]
    recent_feed_with_index = [
    ([
        "🍼" if entry[0] == "bottle" else "🤱",
        format_datetime(entry[1], user_tz),  # Start time
        format_datetime(entry[2], user_tz),  # End time
        f"~{entry[3]} oz" if entry[0] == "breast" else f"{entry[3]} oz",
        entry[4] if entry[0] == "breast" else "",
        entry[5] if len(entry) > 5 else ""
    ], idx)
    for entry, idx in load_recent(CSV_FEED, 5)
]
    recent_sleep = [entry for entry, _ in recent_sleep_with_index]
    recent_feed = [entry for entry, _ in recent_feed_with_index]

    last_feed_time_str, last_feed_ago, last_feed_time, now = get_last_feed_info(feed_logs, user_tz)  # Added user_tz
    last_sleep_end_str, last_sleep_ago = get_last_sleep_info(sleep_logs, user_tz)

    total_sleep_24h = get_total_sleep_24h(sleep_logs, user_tz)
    total_feeds_count, total_feeds_oz = get_total_feeds_24h(feed_logs, user_tz)
    next_feed_suggestion = get_next_feed_suggestion(last_feed_time, now, age_weeks)
    last_side = get_last_breast_side(feed_logs)
    advice = get_advice(age_weeks, sleep_logs, feed_logs, birthday, last_side)
    current_sleep = get_current_sleep()

    return render_template_string(
        html,
        name=name,
        birthday=birthday,
        age_days=age_days,
        age_weeks=age_weeks,
        advice=advice,
        sleep_logs=recent_sleep,
        feed_logs=recent_feed,
        sleep_logs_with_index=recent_sleep_with_index,
        feed_logs_with_index=recent_feed_with_index,
        last_feed_time_str=last_feed_time_str,
        last_feed_ago=last_feed_ago,
        last_sleep_end_str=last_sleep_end_str,
        last_sleep_ago=last_sleep_ago,
        total_sleep_24h=total_sleep_24h,
        total_feeds_count=total_feeds_count,
        total_feeds_oz=total_feeds_oz,
        next_feed_suggestion=next_feed_suggestion,
        current_sleep=current_sleep,
        user_timezone=user_tz
    )

@app.route("/log_sleep", methods=["POST"])
def log_sleep():
    user_tz = session.get('user_timezone', 'UTC')
    try:
        sleep_start = request.form.get("sleep_start")
        sleep_end = request.form.get("sleep_end")
        was_tracked = request.form.get("sleep_was_tracked") == "1"

        # Get temporary sleep data if exists
        current_sleep = get_current_sleep()
        auto_start, auto_end = None, None
        if current_sleep and "|" in current_sleep:
            auto_start, auto_end = current_sleep.split("|")

        # Convert submitted times to UTC
        user_tz_obj = pytz.timezone(user_tz)
        naive_start = datetime.strptime(sleep_start, "%Y-%m-%dT%H:%M")
        naive_end = datetime.strptime(sleep_end, "%Y-%m-%dT%H:%M")
        local_start = user_tz_obj.localize(naive_start, is_dst=None)
        local_end = user_tz_obj.localize(naive_end, is_dst=None)
        utc_start = local_start.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M")
        utc_end = local_end.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M")

        # Always log if times match server-tracked session
        if was_tracked and current_sleep:
            append_csv(CSV_SLEEP, [utc_start, utc_end])
            clear_current_sleep()
        else:
            # Log manual entries
            append_csv(CSV_SLEEP, [utc_start, utc_end])

    except Exception as e:
        print(f"Error logging sleep: {str(e)}")
    
    return redirect(url_for('home'))




@app.route("/log_feed", methods=["POST"])
def log_feed():
    user_tz = session.get('user_timezone', 'UTC')
    feeding_type = request.form["feeding_type"]
    
    try:
        if feeding_type == "breast":
            # Process breast feeding
            naive_start = datetime.strptime(request.form["feed_start"], "%Y-%m-%dT%H:%M")
            naive_end = datetime.strptime(request.form["feed_end"], "%Y-%m-%dT%H:%M")
            side = request.form["side"]
            
            # Convert to UTC
            user_tz_obj = pytz.timezone(user_tz)
            local_start = user_tz_obj.localize(naive_start, is_dst=None)
            local_end = user_tz_obj.localize(naive_end, is_dst=None)
            utc_start = local_start.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M")
            utc_end = local_end.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M")
            
            # Calculate amount from duration
            duration = (local_end - local_start).total_seconds() / 60
            amount = round(duration * 0.75, 1)  # 0.75 oz/min estimate
            
            row = ["breast", utc_start, utc_end, amount, side, request.form["notes"]]
            
        elif feeding_type == "bottle":
            # Process bottle feeding
            naive_start = datetime.strptime(request.form["bottle_start"], "%Y-%m-%dT%H:%M")
            amount = float(request.form["amount"])
            
            # Convert to UTC
            user_tz_obj = pytz.timezone(user_tz)
            local_start = user_tz_obj.localize(naive_start, is_dst=None)
            utc_start = local_start.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M")
            
            # Estimate end time (0.5 oz/min consumption rate)
            duration = amount / 0.5  # minutes
            estimated_end = local_start + timedelta(minutes=duration)
            utc_end = estimated_end.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M")
            
            row = ["bottle", utc_start, utc_end, amount, "", request.form["notes"]]
            
        append_csv(CSV_FEED, row)
        
    except Exception as e:
        print(f"Error logging feed: {str(e)}")
    
    return redirect(url_for('home'))


@app.route("/delete_sleep", methods=["POST"])
def delete_sleep():
    try:
        index = int(request.form["index"])
        if os.path.exists(CSV_SLEEP):
            with open(CSV_SLEEP, newline='') as csvfile:
                rows = list(csv.reader(csvfile))
            if 0 <= index < len(rows):
                rows.pop(index)
                with open(CSV_SLEEP, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(rows)
    except Exception as e:
        print(f"Error deleting sleep: {str(e)}")
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


@app.route("/start_sleep", methods=["POST"])
def start_sleep():
    user_tz = session.get('user_timezone', 'UTC')
    try:
        # Get current time in UTC
        utc_now = datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M")
        save_current_sleep(utc_now)
        return jsonify(status="success", start_time=utc_now)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500

@app.route("/end_sleep", methods=["POST"])
def end_sleep():
    user_tz = session.get('user_timezone', 'UTC')
    try:
        start_time = get_current_sleep()
        if not start_time:
            return jsonify(status="error", message="No active sleep session"), 400

        # Get current UTC time but DON'T log yet
        utc_end = datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M")
        
        # Save both times temporarily
        save_current_sleep(f"{start_time}|{utc_end}")  # Store as "start|end"

        return jsonify(status="success", end_time=utc_end)
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500



if __name__ == "__main__":
    app.run(debug=True)