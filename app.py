import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import io
import uuid
import base64
from github import Github

# Load GitHub secrets
GITHUB_TOKEN = st.secrets["github_token"]
REPO_OWNER = st.secrets["repo_owner"]
REPO_NAME = st.secrets["repo_name"]
FILE_PATH = st.secrets["file_path"]
BRANCH = st.secrets["branch"]

# Setup GitHub repo
g = Github(GITHUB_TOKEN)
repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")

st.set_page_config("ORAICAN Tracker", layout="wide")
st.title("📊 ORAICAN Tracker (GitHub Sync)")

# Initialize session state
task_cols = ["ID", "Title", "Description", "Status", "DueDate", "Created"]
meet_cols = ["ID", "Topic", "Date", "Time", "Link", "Created"]

if "tasks" not in st.session_state:
    st.session_state.tasks = pd.DataFrame(columns=task_cols)
if "meetings" not in st.session_state:
    st.session_state.meetings = pd.DataFrame(columns=meet_cols)
if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0

# ----------------------------
# Sidebar GitHub Sync
with st.sidebar:
    st.header("📂 GitHub Sync")

    if st.button("📥 Fetch latest from GitHub"):
        try:
            contents = repo.get_contents(FILE_PATH, ref=BRANCH)
            decoded = base64.b64decode(contents.content)
            excel_data = pd.read_excel(io.BytesIO(decoded), sheet_name=None)

            if "Tasks" in excel_data:
                for col in task_cols:
                    if col not in excel_data["Tasks"].columns:
                        excel_data["Tasks"][col] = ""
                st.session_state.tasks = excel_data["Tasks"][task_cols]

            if "Meetings" in excel_data:
                for col in meet_cols:
                    if col not in excel_data["Meetings"].columns:
                        excel_data["Meetings"][col] = ""
                st.session_state.meetings = excel_data["Meetings"][meet_cols]

            st.success("✅ Latest file fetched and loaded.")
        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e):
                st.warning("⚠️ File not found. It will be created on first save.")
            else:
                st.error(f"❌ Fetch failed: {e}")

    if st.button("📤 Save changes to GitHub"):
        try:
            # Ensure ID column exists and is a string
            for df_name in ["tasks", "meetings"]:
                df = st.session_state[df_name]
                if "ID" not in df.columns:
                    df.insert(0, "ID", [str(uuid.uuid4()) for _ in range(len(df))])
                df["ID"] = df["ID"].astype(str)
                st.session_state[df_name] = df

            # Try loading existing file
            try:
                contents = repo.get_contents(FILE_PATH, ref=BRANCH)
                decoded = base64.b64decode(contents.content)
                existing_excel = pd.read_excel(io.BytesIO(decoded), sheet_name=None)
                sha = contents.sha
            except Exception:
                existing_excel = {}
                sha = None

            # Merge changes
            for sheet, session_df, expected_cols in [("Tasks", st.session_state.tasks, task_cols),
                                                      ("Meetings", st.session_state.meetings, meet_cols)]:
                session_df = session_df.dropna(subset=["ID"])
                if sheet in existing_excel:
                    old_df = existing_excel[sheet]
                    old_df["ID"] = old_df["ID"].astype(str)
                    merged_df = pd.concat([old_df.set_index("ID"), session_df.set_index("ID")])
                    merged_df = merged_df[~merged_df.index.duplicated(keep='last')].reset_index()
                else:
                    merged_df = session_df
                existing_excel[sheet] = merged_df[expected_cols]

            # Save and upload to GitHub
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                for sheet, df in existing_excel.items():
                    df.to_excel(writer, sheet_name=sheet, index=False)
            output.seek(0)
            content_bytes = output.read()
            commit_msg = "Update ORAICAN tracker via Streamlit"

            if sha:
                repo.update_file(FILE_PATH, commit_msg, content_bytes, sha, branch=BRANCH)
            else:
                repo.create_file(FILE_PATH, commit_msg, content_bytes, branch=BRANCH)

            st.success("✅ Changes pushed to GitHub.")
        except Exception as e:
            st.error(f"❌ Save failed: {e}")

# ----------------------------
# Week Navigation
def get_week_range(offset):
    today = datetime.today() + timedelta(weeks=offset)
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.date(), end.date()

start_date, end_date = get_week_range(st.session_state.week_offset)

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("⬅️ Previous Week"):
        st.session_state.week_offset -= 1
        st.rerun()
with col2:
    st.markdown(f"### Week: {start_date} to {end_date}")
with col3:
    if st.button("Next Week ➡️"):
        st.session_state.week_offset += 1
        st.rerun()

with st.expander("📅 Or pick custom dates"):
    start_date = st.date_input("Start Date", start_date)
    end_date = st.date_input("End Date", end_date)

# ----------------------------
# Tabs
tab1, tab2 = st.tabs(["📝 Tasks", "📅 Meetings"])

# ----------------------------
# TASKS TAB
with tab1:
    st.subheader("➕ Add New Task")
    st.text_input("Title", key="task_title")
    st.text_area("Description", key="task_desc")
    st.selectbox("Status", ["To Do", "In Progress", "Done"], key="task_status")
    st.date_input("Due Date", value=datetime.today(), key="task_due")

    if st.button("Add Task"):
        new_task = {
            "ID": str(uuid.uuid4()),
            "Title": st.session_state.task_title,
            "Description": st.session_state.task_desc,
            "Status": st.session_state.task_status,
            "DueDate": st.session_state.task_due.strftime("%Y-%m-%d"),
            "Created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.tasks = pd.concat([st.session_state.tasks, pd.DataFrame([new_task])], ignore_index=True)
        st.success("✅ Task added.")

    st.subheader("📋 Tasks in Selected Date Range")
    df_tasks = st.session_state.tasks
    if "DueDate" in df_tasks.columns:
        df_filtered = df_tasks[
            (df_tasks["DueDate"] >= str(start_date)) &
            (df_tasks["DueDate"] <= str(end_date))
        ]
    else:
        df_filtered = pd.DataFrame(columns=df_tasks.columns)

    status_options = ["All"] + df_filtered["Status"].dropna().unique().tolist()
    selected_status = st.selectbox("Filter by Status", status_options)

    if selected_status != "All":
        df_filtered = df_filtered[df_filtered["Status"] == selected_status]

    group_by = st.radio("Group by", ["None", "Week", "Month"], horizontal=True)

    if group_by != "None":
        group_col = pd.to_datetime(df_filtered["DueDate"])
        df_filtered["Group"] = group_col.dt.strftime("Week %U - %Y") if group_by == "Week" else group_col.dt.strftime("%B %Y")
        for grp, group_df in df_filtered.groupby("Group"):
            st.markdown(f"**📁 {grp}**")
            for idx, row in group_df.iterrows():
                with st.expander(f"✏️ {row['Title']} ({row['Status']})"):
                    new_title = st.text_input("Edit Title", row["Title"], key=f"edit_title_{idx}")
                    new_desc = st.text_area("Edit Description", row["Description"], key=f"edit_desc_{idx}")
                    new_status = st.selectbox("Edit Status", ["To Do", "In Progress", "Done"],
                                              index=["To Do", "In Progress", "Done"].index(row["Status"]),
                                              key=f"edit_status_{idx}")
                    new_due = st.date_input("Edit Due Date", pd.to_datetime(row["DueDate"]), key=f"edit_due_{idx}")
                    if st.button("💾 Save", key=f"save_task_{idx}"):
                        st.session_state.tasks.at[idx, "Title"] = new_title
                        st.session_state.tasks.at[idx, "Description"] = new_desc
                        st.session_state.tasks.at[idx, "Status"] = new_status
                        st.session_state.tasks.at[idx, "DueDate"] = new_due.strftime("%Y-%m-%d")
                        st.success("✅ Task updated.")
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"delete_task_{idx}"):
                        st.session_state.tasks.drop(index=idx, inplace=True)
                        st.session_state.tasks.reset_index(drop=True, inplace=True)
                        st.success("❌ Task deleted.")
                        st.rerun()
    else:
    
        for idx, row in df_filtered.iterrows():
            with st.expander(f"✏️ {row['Title']} ({row['Status']})"):
                new_title = st.text_input("Edit Title", row["Title"], key=f"edit_title_{idx}")
                new_desc = st.text_area("Edit Description", row["Description"], key=f"edit_desc_{idx}")
                new_status = st.selectbox("Edit Status", ["To Do", "In Progress", "Done"],
                                        index=["To Do", "In Progress", "Done"].index(row["Status"]),
                                        key=f"edit_status_{idx}")
                new_due = st.date_input("Edit Due Date", pd.to_datetime(row["DueDate"]), key=f"edit_due_{idx}")
                if st.button("💾 Save", key=f"save_task_{idx}"):
                    st.session_state.tasks.at[idx, "Title"] = new_title
                    st.session_state.tasks.at[idx, "Description"] = new_desc
                    st.session_state.tasks.at[idx, "Status"] = new_status
                    st.session_state.tasks.at[idx, "DueDate"] = new_due.strftime("%Y-%m-%d")
                    st.success("✅ Task updated.")
                    st.rerun()
                if st.button("🗑️ Delete", key=f"delete_task_{idx}"):
                    st.session_state.tasks.drop(index=idx, inplace=True)
                    st.session_state.tasks.reset_index(drop=True, inplace=True)
                    st.success("❌ Task deleted.")
                    st.rerun()

# ----------------------------
# MEETINGS TAB
with tab2:
    st.subheader("➕ Schedule Meeting")
    st.text_input("Meeting Topic", key="meeting_topic")
    st.date_input("Meeting Date", datetime.today(), key="meeting_date")
    st.time_input("Meeting Time", value=time(10, 0), key="meeting_time")
    st.text_input("Meeting Link (Optional)", key="meeting_link")

    if st.button("Add Meeting"):
        new_meeting = {
            "ID": str(uuid.uuid4()),
            "Topic": st.session_state.meeting_topic,
            "Date": st.session_state.meeting_date.strftime("%Y-%m-%d"),
            "Time": st.session_state.meeting_time.strftime("%H:%M"),
            "Link": st.session_state.meeting_link,
            "Created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.meetings = pd.concat([st.session_state.meetings, pd.DataFrame([new_meeting])], ignore_index=True)
        st.success("📅 Meeting added.")

    st.subheader("📆 Meetings in Selected Date Range")
    df_meet = st.session_state.meetings
    df_filtered_meet = df_meet[
        (df_meet["Date"] >= str(start_date)) &
        (df_meet["Date"] <= str(end_date))
    ]

    if not df_filtered_meet.empty:
        first_date = pd.to_datetime(df_filtered_meet.iloc[0]["Date"])
        st.markdown(f"## 🗓️ Weekly Update on {first_date.strftime('%d-%m-%Y')}")
    else:
        st.markdown("## 🗓️ No meetings this week.")

    for idx, row in df_filtered_meet.iterrows():
        link_md = f"[🔗 Join Meeting]({row['Link']})" if row.get("Link") else "No link provided"
        with st.expander(f"🗓️ {row['Topic']} on {row['Date']} — {link_md}"):
            topic = st.text_input("Edit Topic", row["Topic"], key=f"meet_topic_{idx}")
            date = st.date_input("Edit Date", pd.to_datetime(row["Date"]), key=f"meet_date_{idx}")
            time_val = st.time_input("Edit Time", datetime.strptime(row["Time"], "%H:%M").time(), key=f"meet_time_{idx}")
            link = st.text_input("Edit Link", row.get("Link", ""), key=f"meet_link_{idx}")
            if link:
                st.markdown(f"Meeting Link: [🔗 Join Meeting]({link})", unsafe_allow_html=True)
            else:
                st.markdown("Meeting Link: No link provided")

            if st.button("💾 Save", key=f"save_meeting_{idx}"):
                st.session_state.meetings.at[idx, "Topic"] = topic
                st.session_state.meetings.at[idx, "Date"] = date.strftime("%Y-%m-%d")
                st.session_state.meetings.at[idx, "Time"] = time_val.strftime("%H:%M")
                st.session_state.meetings.at[idx, "Link"] = link
                st.success("✅ Meeting updated.")
                st.rerun()

            if st.button("🗑️ Delete", key=f"delete_meeting_{idx}"):
                st.session_state.meetings.drop(index=idx, inplace=True)
                st.session_state.meetings.reset_index(drop=True, inplace=True)
                st.success("❌ Meeting deleted.")
                st.rerun()
