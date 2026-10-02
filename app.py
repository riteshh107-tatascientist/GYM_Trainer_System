
import math
import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import streamlit as st

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    import plotly.express as px
except Exception:
    px = None

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "data" / "gymtrainer.db"
FOUNDER_IMG = APP_DIR / "assets" / "founder" / "ritesh_kumar_singh.jpg"

st.set_page_config(
    page_title="GymTrainer AI",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------- CSS -----------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp {
    background:
      radial-gradient(circle at 15% 10%, rgba(0,255,170,.08), transparent 28%),
      radial-gradient(circle at 90% 15%, rgba(0,190,255,.08), transparent 25%),
      linear-gradient(135deg, #06090d 0%, #0b1118 55%, #071016 100%);
    color: #f5f7fa;
}
.block-container { padding-top: 1.5rem; max-width: 1450px; }
.hero {
    padding: 42px 42px 36px; border-radius: 28px;
    background: linear-gradient(135deg, rgba(15,24,32,.96), rgba(9,15,22,.88));
    border: 1px solid rgba(90,255,196,.18);
    box-shadow: 0 25px 80px rgba(0,0,0,.35);
}
.hero h1 { font-size: clamp(2.5rem, 6vw, 5.2rem); margin: 0; line-height: .95; font-weight: 900;
    background: linear-gradient(90deg,#fff,#72ffd0,#7bdcff); -webkit-background-clip:text; color:transparent; }
.hero h2 { color:#d7e2e8; font-weight:600; margin-top:18px; }
.hero p { color:#9fb0bb; font-size:1.05rem; line-height:1.7; max-width:720px; }
.badge { display:inline-block; padding:7px 13px; border-radius:999px; background:rgba(89,255,195,.1);
    border:1px solid rgba(89,255,195,.25); color:#7dffd5; font-size:.78rem; font-weight:800; letter-spacing:.08em; }
.founder-card, .glass, .metric {
    background: rgba(13,20,28,.78); border:1px solid rgba(255,255,255,.08);
    border-radius:22px; padding:22px; box-shadow:0 15px 50px rgba(0,0,0,.22);
}
.founder-img { width:170px; height:170px; object-fit:cover; border-radius:50%;
    border:3px solid rgba(117,255,211,.65); box-shadow:0 0 35px rgba(60,255,190,.2); }
.metric .value { font-size:2rem; font-weight:800; color:#eafdf6; }
.metric .label { color:#91a1ab; font-size:.85rem; }
.section-title { font-size:1.8rem; font-weight:800; margin:25px 0 10px; }
.small { color:#94a5af; }
.exercise-card { min-height:145px; }
div.stButton > button {
    border-radius:12px; font-weight:700; border:1px solid rgba(105,255,205,.25);
    background:linear-gradient(135deg,rgba(29,52,61,.95),rgba(13,35,42,.95));
}
div.stButton > button:hover { border-color:#75ffd4; box-shadow:0 0 22px rgba(80,255,195,.14); }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#070b10,#0a1218); }
footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ----------------------------- Database -----------------------------
def db():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise TEXT NOT NULL,
            reps INTEGER DEFAULT 0,
            correct_reps INTEGER DEFAULT 0,
            form_score REAL DEFAULT 0,
            duration_sec INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profiles(
            user_id INTEGER PRIMARY KEY,
            age INTEGER,
            height_cm REAL,
            weight_kg REAL,
            goal TEXT,
            experience TEXT,
            training_days INTEGER,
            equipment TEXT
        );
        """)

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$",1)[1], digest)
    except Exception:
        return False

def create_user(name, email, password):
    try:
        with db() as con:
            con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                        (name.strip(), email.strip().lower(), hash_password(password), datetime.now().isoformat()))
        return True, "Account created. Please log in."
    except sqlite3.IntegrityError:
        return False, "An account with that email already exists."

def authenticate(email, password):
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return dict(row)
    return None

def save_workout(user_id, exercise, reps, correct_reps, form_score, duration_sec):
    with db() as con:
        con.execute("""INSERT INTO workouts
        (user_id,exercise,reps,correct_reps,form_score,duration_sec,created_at)
        VALUES(?,?,?,?,?,?,?)""",
        (user_id, exercise, int(reps), int(correct_reps), float(form_score), int(duration_sec),
         datetime.now().isoformat()))

def get_workouts(user_id):
    with db() as con:
        return pd.read_sql_query(
            "SELECT exercise,reps,correct_reps,form_score,duration_sec,created_at FROM workouts WHERE user_id=? ORDER BY created_at DESC",
            con, params=(user_id,)
        )

def save_profile(user_id, data):
    with db() as con:
        con.execute("""INSERT INTO profiles(user_id,age,height_cm,weight_kg,goal,experience,training_days,equipment)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
        age=excluded.age,height_cm=excluded.height_cm,weight_kg=excluded.weight_kg,
        goal=excluded.goal,experience=excluded.experience,training_days=excluded.training_days,equipment=excluded.equipment""",
        (user_id, data["age"], data["height_cm"], data["weight_kg"], data["goal"], data["experience"],
         data["training_days"], data["equipment"]))

def get_profile(user_id):
    with db() as con:
        row = con.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else {}

init_db()

# ----------------------------- Pose / Exercise Engine -----------------------------
EXERCISES = {
    "Squat": {"target": "Quads • Glutes • Core", "difficulty": "Beginner", "tips": "Keep your chest stable and control the descent."},
    "Bicep Curl": {"target": "Biceps", "difficulty": "Beginner", "tips": "Keep your elbow close to your torso and control the lowering phase."},
    "Push-up": {"target": "Chest • Triceps • Core", "difficulty": "Beginner", "tips": "Maintain a straight body line and controlled depth."},
    "Shoulder Press": {"target": "Shoulders • Triceps", "difficulty": "Intermediate", "tips": "Avoid excessive back arching and press with control."},
    "Lunge": {"target": "Quads • Glutes", "difficulty": "Beginner", "tips": "Keep the front knee stable and torso upright."},
    "Plank": {"target": "Core", "difficulty": "Beginner", "tips": "Keep hips aligned with shoulders and heels."},
    "Jumping Jacks": {"target": "Full Body • Cardio", "difficulty": "Beginner", "tips": "Land softly and keep a steady rhythm."},
    "Sit-up": {"target": "Core", "difficulty": "Beginner", "tips": "Use controlled movement rather than momentum."},
}

def angle(a, b, c):
    a, b, c = np.array(a, dtype=float), np.array(b, dtype=float), np.array(c, dtype=float)
    ba, bc = a - b, c - b
    denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-9
    value = np.dot(ba, bc) / denom
    return float(np.degrees(np.arccos(np.clip(value, -1, 1))))

def landmarks_from_result(result, width=1.0, height=1.0):
    if not result or not result.pose_landmarks:
        return None
    pts = {}
    for idx, lm in enumerate(result.pose_landmarks.landmark):
        pts[idx] = (lm.x * width, lm.y * height, lm.visibility)
    return pts

def form_metrics(exercise, pts):
    if pts is None:
        return {"score": 0, "feedback": "No clear pose detected.", "angles": {}}
    # MediaPipe Pose indices
    L_SH, R_SH, L_EL, R_EL = 11, 12, 13, 14
    L_WR, R_WR, L_HIP, R_HIP = 15, 16, 23, 24
    L_KN, R_KN, L_AN, R_AN = 25, 26, 27, 28
    def p(i): return pts[i][:2]
    try:
        if exercise == "Bicep Curl":
            ang = angle(p(L_SH), p(L_EL), p(L_WR))
            score = 95 if ang <= 100 else max(60, 100 - abs(ang-90)*0.5)
            feedback = "Good elbow position." if ang <= 115 else "Curl with more range and keep the elbow stable."
            return {"score": round(score,1), "feedback": feedback, "angles":{"left_elbow":round(ang,1)}}
        if exercise == "Squat":
            lk = angle(p(L_HIP), p(L_KN), p(L_AN))
            rk = angle(p(R_HIP), p(R_KN), p(R_AN))
            avg = (lk+rk)/2
            score = 96 if 75 <= avg <= 115 else max(62, 96 - min(abs(avg-95)*0.45, 30))
            feedback = "Strong squat position." if 75 <= avg <= 115 else "Adjust squat depth while keeping your torso controlled."
            return {"score":round(score,1), "feedback":feedback, "angles":{"left_knee":round(lk,1),"right_knee":round(rk,1)}}
        if exercise in ("Push-up", "Shoulder Press"):
            le = angle(p(L_SH), p(L_EL), p(L_WR))
            re = angle(p(R_SH), p(R_EL), p(R_WR))
            avg = (le+re)/2
            score = 94 if 75 <= avg <= 120 else max(60, 94 - min(abs(avg-100)*0.4, 30))
            feedback = "Controlled upper-body position." if 75 <= avg <= 120 else "Use a controlled arm range and keep your torso stable."
            return {"score":round(score,1), "feedback":feedback, "angles":{"left_elbow":round(le,1),"right_elbow":round(re,1)}}
        if exercise == "Lunge":
            lk = angle(p(L_HIP), p(L_KN), p(L_AN))
            score = 94 if 75 <= lk <= 120 else max(60, 94 - min(abs(lk-95)*0.4, 30))
            feedback = "Good lower-body alignment." if 75 <= lk <= 120 else "Keep the front knee stable and use controlled depth."
            return {"score":round(score,1), "feedback":feedback, "angles":{"left_knee":round(lk,1)}}
        if exercise == "Plank":
            shoulder = p(L_SH); hip = p(L_HIP); ankle = p(L_AN)
            line_angle = abs(angle((shoulder[0]-1, shoulder[1]), hip, ankle) - 180)
            score = max(65, 98 - line_angle*2)
            feedback = "Good body alignment." if line_angle < 8 else "Try to keep your shoulders, hips and ankles in a straighter line."
            return {"score":round(score,1), "feedback":feedback, "angles":{"alignment_deviation":round(line_angle,1)}}
    except Exception:
        pass
    return {"score":80, "feedback":"Pose detected. Maintain controlled movement.", "angles":{}}

def draw_landmarks(frame, result):
    if mp is None or result is None:
        return frame
    try:
        drawing = mp.solutions.drawing_utils
        styles = mp.solutions.drawing_styles
        drawing.draw_landmarks(frame, result.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS,
                               landmark_drawing_spec=styles.get_default_pose_landmarks_style())
    except Exception:
        pass
    return frame

def analyze_image(image_bytes, exercise):
    if mp is None:
        return None, {"error":"MediaPipe is not installed."}
    arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return None, {"error":"Could not decode the image."}
    with mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1, min_detection_confidence=.5) as pose:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose.process(rgb)
    metrics = form_metrics(exercise, landmarks_from_result(result, frame.shape[1], frame.shape[0]))
    out = draw_landmarks(frame.copy(), result)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB), metrics


def exercise_signal(exercise, pts):
    """Return a movement angle used by the repetition state machine."""
    if pts is None:
        return None
    L_SH, L_EL, L_WR = 11, 13, 15
    L_HIP, L_KN, L_AN = 23, 25, 27
    try:
        def p(i): return pts[i][:2]
        if exercise == "Bicep Curl":
            return angle(p(L_SH), p(L_EL), p(L_WR))
        if exercise == "Squat":
            return angle(p(L_HIP), p(L_KN), p(L_AN))
        if exercise in ("Push-up", "Shoulder Press"):
            return angle(p(L_SH), p(L_EL), p(L_WR))
        if exercise == "Lunge":
            return angle(p(L_HIP), p(L_KN), p(L_AN))
    except Exception:
        return None
    return None

def count_reps_from_signals(exercise, signals):
    clean = [float(x) for x in signals if x is not None and np.isfinite(x)]
    if len(clean) < 4:
        return 0, 0, "Not enough clear movement frames."
    if exercise in ("Bicep Curl", "Push-up", "Shoulder Press"):
        down_threshold, up_threshold = 105, 155
    elif exercise in ("Squat", "Lunge"):
        down_threshold, up_threshold = 115, 160
    else:
        return 0, 0, "This exercise needs a dedicated temporal model for reliable automatic reps."
    state, reps = "UP", 0
    for s in clean:
        if state == "UP" and s <= down_threshold:
            state = "DOWN"
        elif state == "DOWN" and s >= up_threshold:
            reps += 1
            state = "UP"
    return reps, reps, f"Detected {reps} complete repetition(s) from the selected angle signal."

def analyze_video(video_bytes, exercise, sample_every=3, max_frames=360):
    if mp is None:
        return None, {"error":"MediaPipe is not installed."}
    tmp = APP_DIR / "data" / "_gymtrainer_input.mp4"
    tmp.write_bytes(video_bytes)
    cap = cv2.VideoCapture(str(tmp))
    if not cap.isOpened():
        return None, {"error":"Could not open the uploaded video."}
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = int(frame_count / fps) if fps else 0
    signals, first_annotated, sampled = [], None, 0
    with mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1,
                                min_detection_confidence=.5,
                                min_tracking_confidence=.5) as pose:
        index = 0
        while sampled < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if index % sample_every == 0:
                result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                pts = landmarks_from_result(result, frame.shape[1], frame.shape[0])
                signals.append(exercise_signal(exercise, pts))
                if first_annotated is None and result.pose_landmarks:
                    first_annotated = cv2.cvtColor(
                        draw_landmarks(frame.copy(), result), cv2.COLOR_BGR2RGB
                    )
                sampled += 1
            index += 1
    cap.release()
    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass
    reps, correct, note = count_reps_from_signals(exercise, signals)
    valid = sum(x is not None for x in signals)
    visibility = round(100 * valid / max(1, len(signals)), 1)
    score = round(min(98, max(55, 65 + visibility * .3)), 1) if reps else 0
    return first_annotated, {
        "reps": reps, "correct": correct, "duration": duration,
        "score": score, "visibility": visibility, "note": note,
        "sampled_frames": sampled
    }

# ----------------------------- UI helpers -----------------------------
def metric(label, value):
    st.markdown(f'<div class="metric"><div class="value">{value}</div><div class="label">{label}</div></div>', unsafe_allow_html=True)

def login_page():
    st.markdown('<div class="section-title">🔐 Welcome back</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", use_container_width=True):
            user = authenticate(email, password)
            if user:
                st.session_state.user = user
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid email or password.")
    with tab2:
        name = st.text_input("Full name", key="reg_name")
        email = st.text_input("Email address", key="reg_email")
        p1 = st.text_input("Password", type="password", key="reg_p1")
        p2 = st.text_input("Confirm password", type="password", key="reg_p2")
        if st.button("Create Account", use_container_width=True):
            if not name or not email or not p1:
                st.warning("Please complete all fields.")
            elif p1 != p2:
                st.error("Passwords do not match.")
            elif len(p1) < 8:
                st.error("Use at least 8 characters for the password.")
            else:
                ok, msg = create_user(name, email, p1)
                (st.success if ok else st.error)(msg)

def home():
    st.markdown("""
    <div class="hero">
      <span class="badge">AI • COMPUTER VISION • FITNESS</span>
      <h1>GYMTRAINER AI</h1>
      <h2>Where Human Strength Meets Artificial Intelligence.</h2>
      <p>
      Train smarter with computer-vision exercise analysis, repetition tracking,
      form feedback, workout analytics and an intelligent coaching experience.
      Built as a practical AI fitness platform — not just a rep counter.
      </p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown("### 🚀 Your AI Fitness Journey")
        st.markdown("**See your movement. Understand your form. Track your progress.**")
        st.write("GymTrainer AI combines pose estimation and workout analytics to turn a camera-enabled device into a fitness assistance tool.")
        if st.button("🏋️ Start AI Workout", use_container_width=True):
            st.session_state.page = "AI Workout"
            st.rerun()
    with c2:
        if FOUNDER_IMG.exists():
            st.image(str(FOUNDER_IMG), width=220)
        st.markdown("**Ritesh Kumar Singh**  \n*Founder & Creator — GymTrainer AI*")
    st.markdown('<div class="section-title">Why GymTrainer AI?</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    features = [("🎯","Form Analysis","Joint-angle based movement feedback"),
                ("🔢","Rep Tracking","State-based repetition counting"),
                ("📊","Progress","Workout history and visual analytics"),
                ("🤖","AI Coach","Personalized, rule-based coaching with optional LLM enhancement")]
    for col, (icon,title,desc) in zip(cols, features):
        with col:
            st.markdown(f'<div class="glass"><h3>{icon} {title}</h3><p class="small">{desc}</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Supported Exercises</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, (name, info) in enumerate(EXERCISES.items()):
        with cols[i % 4]:
            st.markdown(f'<div class="glass exercise-card"><h3>{name}</h3><p class="small">{info["target"]}</p><b>{info["difficulty"]}</b></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Meet the Vision Behind GymTrainer AI</div>', unsafe_allow_html=True)
    a,b = st.columns([1,2])
    with a:
        if FOUNDER_IMG.exists(): st.image(str(FOUNDER_IMG), width=190)
    with b:
        st.markdown("### Ritesh Kumar Singh")
        st.write("Founder & Creator — GymTrainer AI")
        st.write("Built with vision, technology, and a passion for smarter fitness.")
        st.caption("Fitness guidance only — not medical advice.")

def workout_page():
    st.markdown('<div class="section-title">🏋️ AI Workout Studio</div>', unsafe_allow_html=True)
    exercise = st.selectbox("Select exercise", list(EXERCISES.keys()))
    mode = st.radio("Input mode", ["Camera Snapshot", "Upload Image", "Upload Video (analysis preview)"], horizontal=True)
    target = st.number_input("Target repetitions", min_value=1, max_value=500, value=12)
    if mode == "Camera Snapshot":
        img = st.camera_input("Take a posture snapshot")
    elif mode == "Upload Image":
        img = st.file_uploader("Upload a clear full-body image", type=["jpg","jpeg","png"])
    else:
        img = st.file_uploader("Upload a short workout video", type=["mp4","mov","avi","mkv"])
    if img is not None and mode != "Upload Video (analysis preview)":
        with st.spinner("Analyzing pose..."):
            rendered, metrics = analyze_image(img.getvalue(), exercise)
        if "error" in metrics:
            st.error(metrics["error"])
        else:
            c1,c2 = st.columns([1.35,1])
            with c1:
                st.image(rendered, caption="Pose landmarks", use_container_width=True)
            with c2:
                metric("Form Score", f'{metrics["score"]}/100')
                st.write("**AI feedback**")
                st.info(metrics["feedback"])
                if metrics["angles"]:
                    st.write("**Detected angles**")
                    for k,v in metrics["angles"].items():
                        st.write(f"- {k.replace('_',' ').title()}: {v}°")
                st.caption("This prototype analyzes a single frame. For reliable rep counting, use controlled full-body video and the exercise state engine.")
    elif img is not None:
        st.video(img)
        with st.spinner("Analyzing movement frames..."):
            preview, result = analyze_video(img.getvalue(), exercise)
        if "error" in result:
            st.error(result["error"])
        else:
            if preview is not None:
                st.image(preview, caption="Pose preview from analyzed video", use_container_width=True)
            a,b,c,d = st.columns(4)
            with a: metric("Detected Reps", result["reps"])
            with b: metric("Correct Reps", result["correct"])
            with c: metric("Form Score", f'{result["score"]}%')
            with d: metric("Pose Visibility", f'{result["visibility"]}%')
            st.info(result["note"])
            st.caption(f"Analyzed {result['sampled_frames']} sampled frames. Best results: one person, full-body view, good lighting and a stable camera.")
            if st.button("💾 Save Analyzed Session", use_container_width=True):
                if st.session_state.get("user"):
                    save_workout(st.session_state.user["id"], exercise, result["reps"], result["correct"], result["score"], result["duration"])
                    st.success("Workout analysis saved.")
                else:
                    st.warning("Login first to save workout history.")

    st.markdown('<div class="section-title">Session Summary</div>', unsafe_allow_html=True)
    a,b,c,d = st.columns(4)
    with a: metric("Target Reps", target)
    with b: metric("Exercise", exercise)
    with c: metric("Analysis", "Ready")
    with d: metric("Duration", "Auto")
    st.caption("Fitness assistance only — not medical advice.")

def dashboard():
    user = st.session_state.get("user")
    if not user:
        login_page(); return
    df = get_workouts(user["id"])
    st.markdown('<div class="section-title">📊 Performance Dashboard</div>', unsafe_allow_html=True)
    total = int(df["reps"].sum()) if not df.empty else 0
    workouts = len(df)
    avg = round(float(df["form_score"].mean()),1) if not df.empty else 0
    minutes = round(float(df["duration_sec"].sum())/60,1) if not df.empty else 0
    a,b,c,d = st.columns(4)
    for col, label, value in [(a,"Total Workouts",workouts),(b,"Total Reps",total),(c,"Average Form",f"{avg}%"),(d,"Workout Minutes",minutes)]:
        with col: metric(label,value)
    if df.empty:
        st.info("No workouts yet. Start your first AI workout to populate the dashboard.")
        return
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    c1,c2 = st.columns(2)
    with c1:
        if px:
            st.plotly_chart(px.bar(df.groupby("exercise",as_index=False)["reps"].sum(), x="exercise", y="reps", title="Reps by Exercise"), use_container_width=True)
    with c2:
        if px:
            st.plotly_chart(px.line(df.sort_values("created_at"), x="created_at", y="form_score", markers=True, title="Form Score Trend"), use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

def exercises_page():
    st.markdown('<div class="section-title">📚 Exercise Library</div>', unsafe_allow_html=True)
    for name, info in EXERCISES.items():
        with st.expander(f"{name}  •  {info['difficulty']}"):
            st.write(f"**Target muscles:** {info['target']}")
            st.write(f"**Form tip:** {info['tips']}")
            st.write("**Common mistakes:** rushing reps, losing stable alignment, using momentum, or training through pain.")
            st.caption("General fitness information only. Stop if you experience pain and consult a qualified professional when appropriate.")

def planner():
    st.markdown('<div class="section-title">📅 AI Workout Planner</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1: goal = st.selectbox("Goal", ["Strength","Muscle Building","General Fitness","Endurance"])
    with c2: exp = st.selectbox("Experience", ["Beginner","Intermediate","Advanced"])
    with c3: days = st.selectbox("Days / week", [3,4,5,6])
    equipment = st.selectbox("Equipment", ["Bodyweight","Dumbbells","Full Gym"])
    duration = st.selectbox("Session duration", [20,30,45,60])
    if st.button("✨ Generate Workout Plan", use_container_width=True):
        pools = {
            "Bodyweight":["Squat","Push-up","Lunge","Plank","Jumping Jacks","Sit-up"],
            "Dumbbells":["Squat","Bicep Curl","Shoulder Press","Lunge","Plank"],
            "Full Gym":["Squat","Bicep Curl","Shoulder Press","Lunge","Push-up","Plank"]
        }
        reps = 10 if goal == "Strength" else 12
        plan = pools[equipment]
        st.success(f"{goal} plan • {days} days/week • {duration} minutes")
        for i, ex in enumerate(plan[:5], 1):
            st.markdown(f"**{i}. {ex}** — 3 sets × {reps} reps • Rest 60–90 sec")
        st.caption("Recommendations are general fitness guidance and are not a substitute for professional medical or fitness advice.")

def progress_page():
    user = st.session_state.get("user")
    if not user: login_page(); return
    df = get_workouts(user["id"])
    st.markdown('<div class="section-title">📈 Progress</div>', unsafe_allow_html=True)
    if df.empty:
        st.info("Your progress will appear after you save workout sessions.")
        return
    df["created_at"] = pd.to_datetime(df["created_at"])
    latest = df.sort_values("created_at").tail(1).iloc[0]
    metric("Latest Form Score", f"{latest.form_score}%")
    if px:
        st.plotly_chart(px.line(df.sort_values("created_at"), x="created_at", y="form_score", color="exercise", markers=True, title="Your Form Progress"), use_container_width=True)

def profile_page():
    user = st.session_state.get("user")
    if not user: login_page(); return
    p = get_profile(user["id"])
    st.markdown('<div class="section-title">👤 Profile</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        age = st.number_input("Age", 13, 100, int(p.get("age") or 20))
        height = st.number_input("Height (cm)", 100.0, 240.0, float(p.get("height_cm") or 170))
        weight = st.number_input("Weight (kg)", 25.0, 250.0, float(p.get("weight_kg") or 65))
        goal = st.selectbox("Goal", ["Strength","Muscle Building","General Fitness","Endurance"], index=["Strength","Muscle Building","General Fitness","Endurance"].index(p.get("goal")) if p.get("goal") in ["Strength","Muscle Building","General Fitness","Endurance"] else 2)
    with c2:
        exp_opts=["Beginner","Intermediate","Advanced"]
        exp = st.selectbox("Experience", exp_opts, index=exp_opts.index(p.get("experience")) if p.get("experience") in exp_opts else 0)
        days = st.selectbox("Training days", [3,4,5,6], index=[3,4,5,6].index(p.get("training_days")) if p.get("training_days") in [3,4,5,6] else 0)
        equipment = st.selectbox("Equipment", ["Bodyweight","Dumbbells","Full Gym"], index=["Bodyweight","Dumbbells","Full Gym"].index(p.get("equipment")) if p.get("equipment") in ["Bodyweight","Dumbbells","Full Gym"] else 0)
    if st.button("Save Profile", use_container_width=True):
        save_profile(user["id"], {"age":age,"height_cm":height,"weight_kg":weight,"goal":goal,"experience":exp,"training_days":days,"equipment":equipment})
        st.success("Profile updated.")

def coach_page():
    st.markdown('<div class="section-title">🤖 AI Coach</div>', unsafe_allow_html=True)
    exercise = st.selectbox("Exercise", list(EXERCISES.keys()))
    score = st.slider("Example form score", 50, 100, 88)
    if score >= 90:
        msg = "Excellent control. Keep your range consistent and focus on steady breathing."
    elif score >= 75:
        msg = "Good work. Focus on slower, more controlled repetitions and stable alignment."
    else:
        msg = "Reduce speed and prioritize safe movement quality before increasing load or reps."
    st.markdown(f'<div class="glass"><h3>Coach feedback</h3><p>{msg}</p><p class="small">Exercise: {exercise} • Fitness guidance only, not medical advice.</p></div>', unsafe_allow_html=True)

def settings():
    st.markdown('<div class="section-title">⚙️ Settings</div>', unsafe_allow_html=True)
    st.write("GymTrainer AI is configured for Streamlit Community Cloud.")
    st.info("For cloud persistence, connect Supabase in a future production version. The included SQLite database is suitable for local development and demos; Streamlit Cloud storage can reset when the app restarts.")

# ----------------------------- Main -----------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Home"

with st.sidebar:
    st.markdown("## 🏋️ GymTrainer AI")
    st.caption("Train Smarter. Move Better.")
    pages = ["Home","AI Workout","Dashboard","AI Coach","Exercises","Workout Planner","Progress","Profile","Settings"]
    selected = st.radio("Navigation", pages, index=pages.index(st.session_state.page) if st.session_state.page in pages else 0)
    st.session_state.page = selected
    st.divider()
    if st.session_state.user:
        st.success(f"Hi, {st.session_state.user['name']}")
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.page = "Home"
            st.rerun()
    else:
        if st.button("🔐 Login / Signup", use_container_width=True):
            st.session_state.page = "Login"
            st.rerun()
    st.divider()
    st.caption("Founder")
    st.write("**Ritesh Kumar Singh**")
    st.caption("Founder & Creator — GymTrainer AI")

if st.session_state.page == "Home": home()
elif st.session_state.page == "Login": login_page()
elif st.session_state.page == "AI Workout": workout_page()
elif st.session_state.page == "Dashboard": dashboard()
elif st.session_state.page == "AI Coach": coach_page()
elif st.session_state.page == "Exercises": exercises_page()
elif st.session_state.page == "Workout Planner": planner()
elif st.session_state.page == "Progress": progress_page()
elif st.session_state.page == "Profile": profile_page()
elif st.session_state.page == "Settings": settings()

st.markdown("---")
st.caption("GYMTRAINER AI • Built with Computer Vision & AI • Fitness assistance only, not medical advice.")
