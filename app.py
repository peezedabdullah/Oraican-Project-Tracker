import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import io

st.set_page_config("ORAICAN Tracker", layout="wide")
st.title("📊 ORAICAN Tracker (Excel File Upload/Sync)")

# Initialize session state
if "tasks" not in st.session_state:
    st.session_state.tasks = pd.DataFrame(columns=["Title", "Description", "Status", "DueDate", "Created"])
if "meetings" not in st.session_state:
    st.session_state.meetings = pd.DataFrame(columns=["Topic", "Date", "Time", "Link", "Created"])
if "week_offset" not in st.session_state:
    st.session_state.week_offset = 0
if "uploaded_once" not in st.session_state:
    st.session_state.uploaded_once = False

# ----------------------------
# Sidebar - File Upload & Sync
with st.sidebar:
    st.header("📂 Sync Excel File")
    uploaded_file = st.file_uploader("Upload Excel File (with 'Tasks' & 'Meetings' sheets)", type=["xlsx"])

    if uploaded_file and not st.session_state.uploaded_once:
        try:
            excel_data = pd.read_excel(uploaded_file, sheet_name=None)
            if "Tasks" in excel_data:
                st.session_state.tasks = excel_data["Tasks"]
            if "Meetings" in excel_data:
                st.session_state.meetings = excel_data["Meetings"]
            st.success("✅ Data loaded from Excel.")
            st.session_state.uploaded_once = True
        except Exception as e:
            st.error(f"❌ Failed to read file: {e}")

    if st.button("🔄 Sync to Excel"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            st.session_state.tasks.to_excel(writer, sheet_name="Tasks", index=False)
            st.session_state.meetings.to_excel(writer, sheet_name="Meetings", index=False)
        st.download_button("📥 Download Synced File", data=output.getvalue(), file_name="oraican_tracker.xlsx")

# ----------------------------
# Week range selection
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
# Tabs: Tasks and Meetings
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
    df_filtered = df_tasks[
        (df_tasks["DueDate"] >= str(start_date)) &
        (df_tasks["DueDate"] <= str(end_date))
    ]

    status_options = ["All"] + df_filtered["Status"].dropna().unique().tolist()
    selected_status = st.selectbox("Filter by Status", status_options)

    if selected_status != "All":
        df_filtered = df_filtered[df_filtered["Status"] == selected_status]

    group_by = st.radio("Group by", ["None", "Week", "Month"], horizontal=True)
    
    if group_by != "None":
        group_col = pd.to_datetime(df_filtered["DueDate"])
        if group_by == "Week":
            df_filtered["Group"] = group_col.dt.strftime("Week %U - %Y")
        else:
            df_filtered["Group"] = group_col.dt.strftime("%B %Y")
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
                        st.experimental_rerun()
                    if st.button("🗑️ Delete", key=f"delete_task_{idx}"):
                        st.session_state.tasks.drop(index=idx, inplace=True)
                        st.session_state.tasks.reset_index(drop=True, inplace=True)
                        st.success("❌ Task deleted.")
                        st.rerun()
    else:
        # If not grouped, show all tasks editable and deletable too
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
        # Display clickable link as markdown
        link_md = f"[🔗 Join Meeting]({row['Link']})" if row.get("Link") else "No link provided"

        with st.expander(f"🗓️ {row['Topic']} on {row['Date']} — {link_md}"):
            topic = st.text_input("Edit Topic", row["Topic"], key=f"meet_topic_{idx}")
            date = st.date_input("Edit Date", pd.to_datetime(row["Date"]), key=f"meet_date_{idx}")
            time_val = st.time_input("Edit Time", datetime.strptime(row["Time"], "%H:%M").time(), key=f"meet_time_{idx}")
            link = st.text_input("Edit Link", row.get("Link", ""), key=f"meet_link_{idx}")

            # Show clickable link inside expander as well
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

