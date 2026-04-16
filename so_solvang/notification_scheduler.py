"""
Notification Scheduler - Run via Windows Task Scheduler or cron (e.g., every 15-60 minutes).

Tasks:
1. Booking request reminder: 8 hours before 24h (i.e., at 16h) - notifies TSR and creator (Med Rep)
2. Admin L1/L2 approval reminders: First at 16h, then every 16h until approved
3. Auto-cancel booking requests after 24 hours
4. Logs all sends (including Failed to Send for null emails)
"""

import os
import sys
from datetime import datetime, timedelta

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_manager import DatabaseManager

# Email config - use script directory so Send.txt is found regardless of CWD
_script_dir = os.path.dirname(os.path.abspath(__file__))
SEND_TXT = os.path.join(_script_dir, 'Send.txt')
EMAIL_LOG_FILE = os.path.join(_script_dir, 'email_notifications.log')
HEARTBEAT_FILE = os.path.join(_script_dir, 'notification_scheduler_heartbeat.txt')
NOTIFICATION_ENABLED_FILE = os.path.join(_script_dir, 'notification_enabled.txt')
# CC list is read from database (notification_cc_email table)

def get_notification_enabled():
    """Read notification enabled state from file. Default True if file missing."""
    try:
        if os.path.exists(NOTIFICATION_ENABLED_FILE):
            with open(NOTIFICATION_ENABLED_FILE, 'r', encoding='utf-8') as f:
                val = f.read().strip().lower()
                return val not in ('false', '0', 'off', 'no')
    except Exception:
        pass
    return True
GMAIL_ACCOUNT = ''
APP_URL = 'https://so.solvang-pharma.com/'  # Sales Order app URL for email buttons

def build_notification_email(title, salutation, message_html, button_text='Access App', highlight_value=None):
    """Build email body with standard format: purple banner, content, clickable button, footer."""
    highlight_div = f'<div class="count">{highlight_value}</div>' if highlight_value is not None else ''
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #7B2CBF; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .count {{ font-size: 32px; font-weight: bold; color: #7B2CBF; text-align: center; margin: 20px 0; }}
            .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
            .button {{ display: inline-block; padding: 15px 30px; background-color: #7B2CBF; color: #FFFFFF !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; font-size: 16px; border: 2px solid #FFFFFF; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Sales Order Management System</h2>
            </div>
            <div class="content">
                <h3>{title}</h3>
                <p>{salutation}</p>
                {message_html}
                {highlight_div}
                <p style="text-align: center;">
                    <a href="{APP_URL}" class="button" style="display: inline-block; padding: 15px 30px; background-color: #7B2CBF; color: #FFFFFF !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; font-size: 16px; border: 2px solid #FFFFFF; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);">{button_text}</a>
                </p>
                <p><strong>Note:</strong> This is an automated notification. Please do not reply to this email.</p>
            </div>
            <div class="footer">
                <p>InnoGen's IT Department © 2026</p>
                <p>This is an automated email notification.</p>
            </div>
        </div>
    </body>
    </html>
    """

def log_message(level, message, to_email=None, subject=None, error=None):
    """Log to file and optionally to DB (for Failed to Send, we log to DB from caller)."""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}]"
        if to_email:
            log_entry += f" To: {to_email}"
        if subject:
            log_entry += f" Subject: {subject}"
        if message:
            log_entry += f" | {message}"
        if error:
            log_entry += f" | Error: {str(error)}"
        log_entry += "\n"
        with open(EMAIL_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Log error: {e}")

def send_email(to_email, subject, body, trigger_category=None):
    """Send email without Streamlit UI. Returns True if sent, False otherwise."""
    try:
        if not os.path.exists(SEND_TXT):
            log_message("ERROR", "Send.txt not found. Email disabled.")
            return False
        with open(SEND_TXT, 'r') as f:
            lines = f.readlines()
        if len(lines) >= 2:
            gmail_account = lines[0].strip()
            password = lines[1].strip()
        else:
            password = lines[0].strip() if lines else ''
            gmail_account = GMAIL_ACCOUNT or ''
        if not gmail_account or not password:
            log_message("ERROR", "Email credentials not configured")
            return False
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        msg = MIMEMultipart()
        msg['From'] = gmail_account
        msg['To'] = to_email
        db = DatabaseManager()
        # Fetch filtered CC list
        cc_list = db.get_cc_emails(trigger_category=trigger_category)
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
            server.login(gmail_account, password)
            # Prepare recipients list (To + CC)
            recipients = [to_email] + cc_list
            server.send_message(msg, to_addrs=recipients)
        log_message("SUCCESS", f"Email sent to {to_email} (trigger: {trigger_category})", to_email=to_email, subject=subject)
        return True
    except Exception as e:
        log_message("ERROR", f"Send failed: {e}", to_email=to_email, subject=subject, error=e)
        return False

def get_user_email_by_rep_code(db, rep_code):
    users = db.get_all_users()
    for username, data in users.items():
        if str(data.get('rep_code', '')).strip() == str(rep_code).strip():
            email = data.get('email')
            return email.strip() if email and email.strip() else None
    return None

def get_user_email_by_username(db, username):
    """Get email for a user by username (e.g., creator of booking request)."""
    if not username or not str(username).strip():
        return None
    users = db.get_all_users()
    uname = str(username).strip().lower()
    for u, data in users.items():
        if str(u).strip().lower() == uname:
            email = data.get('email')
            return email.strip() if email and email.strip() else None
    return None

def get_emails_by_role(db, role):
    users = db.get_all_users()
    emails = []
    for username, data in users.items():
        if data.get('role') == role:
            email = data.get('email')
            if email and email.strip():
                emails.append(email.strip())
    return emails

def parse_datetime(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(s)[:19], fmt)
        except ValueError:
            continue
    return None

def hours_since(dt):
    if not dt:
        return 999999
    return (datetime.now() - dt).total_seconds() / 3600

def run_scheduler():
    if not get_notification_enabled():
        log_message("INFO", "Notifications disabled (toggle OFF). Skipping all sends.")
        return
    db = DatabaseManager()
    
    # Task 3: Auto-cancel booking requests older than 24 hours
    old_br = db.get_pending_booking_requests_older_than_hours(24)
    auto_cancel_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for _, row in old_br.iterrows():
        rid = row.get('request_id', '')
        if rid:
            db.update_booking_request_status(rid, 'Auto-Cancel', auto_cancel_date=auto_cancel_ts)
            log_message("INFO", f"Auto-cancelled booking request {rid} (24h exceeded)")
            db.insert_notification_log(
                notification_type='booking_request_auto_cancel',
                recipient_type='system',
                recipient_id='',
                order_id='',
                request_id=rid,
                status='Auto-Cancel',
                message=f'Booking request {rid} auto-cancelled after 24 hours'
            )
    
    # Task 1: TSR + Creator reminder at 16 hours (8h before 24h expiry)
    br_16h = db.get_pending_booking_requests_older_than_hours(16)
    for _, row in br_16h.iterrows():
        rid = row.get('request_id', '')
        tsr_code = row.get('tsr_code', '')
        tsr_name = row.get('tsr_name', '')
        client_name = row.get('client_name', '')
        created_by = row.get('created_by', '')
        created_date = row.get('created_date', '')
        if not rid or not tsr_code:
            continue
        last_sent = db.get_last_notification_sent('booking_request', rid, 'tsr_16h_reminder')
        if last_sent:
            last_dt = parse_datetime(last_sent)
            if last_dt and hours_since(last_dt) < 16:
                continue  # Already sent within last 16h
        msg = f"""<p><strong>Request ID:</strong> {rid}</p>
        <p><strong>Client:</strong> {client_name}</p>
        <p><strong>Created:</strong> {created_date} by {created_by}</p>
        <p>This request will be auto-cancelled in 8 hours if not completed. Please log in to complete it.</p>"""
        subject = f"Reminder: Booking Request {rid} - Complete within 8 hours"
        sent_any = False
        # Notify TSR
        tsr_email = get_user_email_by_rep_code(db, tsr_code)
        body_tsr = build_notification_email("Booking Request Reminder", f"Dear {tsr_name},", msg, "Complete Booking Request")
        if tsr_email:
            if send_email(tsr_email, subject, body_tsr, trigger_category='overdue'):
                sent_any = True
                db.insert_notification_log('tsr_16h_reminder', 'TSR', tsr_code, '', rid, 'Sent',
                    f'Reminder sent to TSR {tsr_code} for request {rid}', None)
        else:
            db.insert_notification_log('tsr_16h_reminder', 'TSR', tsr_code, '', rid, 'Failed to Send',
                f'No email for TSR {tsr_code}', 'Recipient email is null or not configured')
        
        # Notify creator (Med Rep who submitted the booking request)
        creator_email = get_user_email_by_username(db, created_by) if created_by else None
        if creator_email and creator_email != tsr_email:  # Avoid duplicate if creator is same as TSR
            users = db.get_all_users()
            creator_name = users.get(created_by, {}).get('rep_name', created_by) or created_by
            body_creator = build_notification_email("Booking Request Reminder", f"Dear {creator_name},", msg, "View Booking Request")
            if send_email(creator_email, subject, body_creator, trigger_category='overdue'):
                sent_any = True
                db.insert_notification_log('creator_16h_reminder', 'Creator', created_by, '', rid, 'Sent',
                    f'Reminder sent to creator {created_by} for request {rid}', None)
        elif created_by and not creator_email:
            db.insert_notification_log('creator_16h_reminder', 'Creator', created_by, '', rid, 'Failed to Send',
                f'No email for creator {created_by}', 'Recipient email is null or not configured')
        if sent_any:
            db.upsert_notification_sent_tracking('booking_request', rid, 'tsr_16h_reminder')
    
    # Task 2: Admin L1/L2 approval reminders
    orders_df = db.get_all_orders()
    
    if not orders_df.empty:
        for _, row in orders_df.iterrows():
            order_id = row.get('OrderID', '')
            status = str(row.get('Status', ''))
            approved_l1 = str(row.get('ApprovedByLevel1', '') or '')
            approved_l2 = str(row.get('ApprovedByLevel2', '') or '')
            order_date = parse_datetime(row.get('OrderDate', ''))
            approved_date_l1 = parse_datetime(row.get('ApprovedDateLevel1', ''))
            
            # L1 reminder: Pending for Approval 1 (or legacy Pending), not Pending for SGF, no L1 approval, order > 16h old
            needs_l1 = (status in ('Pending', 'Pending for Approval 1') or status.startswith('Pending for Approval 1')) and 'SGF' not in status
            if needs_l1 and not approved_l1 and approved_l1 != 'SYSTEM':
                if hours_since(order_date) >= 16:
                    last_sent = db.get_last_notification_sent('order', order_id, 'approval_l1_reminder')
                    should_send = not last_sent or hours_since(parse_datetime(last_sent)) >= 16
                    if should_send:
                        admin_emails = get_emails_by_role(db, 'Admin Level 1')
                        if admin_emails:
                            subject = f"Reminder: Order {order_id} - Pending Level 1 Approval"
                            msg = f"<p>Order {order_id} has been pending for over 16 hours. Please log in to approve.</p>"
                            body = build_notification_email("Approval Reminder", "Dear Admin Level 1,", msg, "Review Orders")
                            for email in admin_emails:
                                if send_email(email, subject, body, trigger_category='overdue'):
                                    db.upsert_notification_sent_tracking('order', order_id, 'approval_l1_reminder')
                                    db.insert_notification_log('approval_l1_reminder', 'Admin Level 1', email, order_id, '', 'Sent',
                                        f'L1 reminder sent for order {order_id}', None)
                                    break
                        else:
                            db.insert_notification_log('approval_l1_reminder', 'Admin Level 1', '', order_id, '', 'Failed to Send',
                                'No Admin Level 1 users with email', None)
            
            # L2 reminder: L1 approved, no L2, use ApprovedDateLevel1 or OrderDate
            if approved_l1 and approved_l1 != 'SYSTEM' and not approved_l2:
                ref_date = approved_date_l1 if approved_date_l1 else order_date
                if ref_date and hours_since(ref_date) >= 16:
                    last_sent = db.get_last_notification_sent('order', order_id, 'approval_l2_reminder')
                    should_send = not last_sent or hours_since(parse_datetime(last_sent)) >= 16
                    if should_send:
                        admin_emails = get_emails_by_role(db, 'Admin Level 2')
                        if admin_emails:
                            subject = f"Reminder: Order {order_id} - Pending Level 2 Approval"
                            msg = f"<p>Order {order_id} has been pending Level 2 approval for over 16 hours. Please log in to approve.</p>"
                            body = build_notification_email("Approval Reminder", "Dear Admin Level 2,", msg, "Review Orders")
                            for email in admin_emails:
                                if send_email(email, subject, body, trigger_category='overdue'):
                                    db.upsert_notification_sent_tracking('order', order_id, 'approval_l2_reminder')
                                    db.insert_notification_log('approval_l2_reminder', 'Admin Level 2', email, order_id, '', 'Sent',
                                        f'L2 reminder sent for order {order_id}', None)
                                    break
                        else:
                            db.insert_notification_log('approval_l2_reminder', 'Admin Level 2', '', order_id, '', 'Failed to Send',
                                'No Admin Level 2 users with email', None)
            
            # TRADE orders: skip L1 (SYSTEM), go to L2. Use OrderDate for L2 reminder.
            if approved_l1 == 'SYSTEM' and not approved_l2:
                if order_date and hours_since(order_date) >= 16:
                    last_sent = db.get_last_notification_sent('order', order_id, 'approval_l2_reminder')
                    should_send = not last_sent or hours_since(parse_datetime(last_sent)) >= 16
                    if should_send:
                        admin_emails = get_emails_by_role(db, 'Admin Level 2')
                        if admin_emails:
                            subject = f"Reminder: Order {order_id} - Pending Level 2 Approval (TRADE)"
                            msg = f"<p>Order {order_id} (TRADE) has been pending for over 16 hours. Please log in to approve.</p>"
                            body = build_notification_email("Approval Reminder", "Dear Admin Level 2,", msg, "Review Orders")
                            for email in admin_emails:
                                if send_email(email, subject, body, trigger_category='overdue'):
                                    db.upsert_notification_sent_tracking('order', order_id, 'approval_l2_reminder')
                                    db.insert_notification_log('approval_l2_reminder', 'Admin Level 2', email, order_id, '', 'Sent',
                                        f'L2 reminder (TRADE) sent for order {order_id}', None)
                                    break

    # Write heartbeat so app can check if scheduler ran recently
    try:
        with open(HEARTBEAT_FILE, 'w', encoding='utf-8') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        log_message("WARN", f"Could not write heartbeat: {e}")

if __name__ == '__main__':
    run_scheduler()
