# Shree Karni QR Print System v3

A Flask-based customer upload and print-order manager for Shree Karni Computer.

## Features
- Customer photo/PDF upload with a 25 MB limit
- Order ID creation and order confirmation page
- Passport photo crop/zoom/rotation and 8-photo 4×6 sheet
- PDF page range, rotation and crop margin
- Admin dashboard for orders, print status and payment status
- Admin-only processed file downloads
- QR code for the customer upload page
- SQLite database and configurable persistent data directory
- Responsive Hindi/English interface

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```
Set environment variables before starting:
```powershell
# Windows PowerShell
$env:ADMIN_USER="admin"
$env:ADMIN_PASSWORD="Use-A-Strong-Unique-Password"
$env:SECRET_KEY="Use-A-Long-Random-Secret"
python app.py
```
Open http://127.0.0.1:5000. Admin: http://127.0.0.1:5000/admin/login

## Deploy on Render
1. Push the project folder to a GitHub repository.
2. In Render, create a Blueprint from that repository and review `render.yaml`.
3. Set `ADMIN_USER`, `ADMIN_PASSWORD`, and optionally `UPI_ID` in Render environment settings.
4. Confirm a Persistent Disk is attached at `/var/data`. The disk is needed to retain SQLite orders and uploaded files across deploys/restarts.
5. Deploy and test `/health`, customer upload, admin login, and QR code.

**Important:** Render persistent disks are a paid feature and are not available on every service plan. Without persistent storage, local SQLite and uploads may be lost on restart/redeploy. Do not use this app for production until persistence, backups and access controls have been tested.

## Security notes
- Never publish passwords or SECRET_KEY in GitHub.
- Configure a strong unique admin password in the hosting environment.
- Admin login is disabled until an admin password or password hash is configured.
- UPI payments are not verified automatically; the admin must mark them Paid only after checking the payment.
- The app does not connect directly to a printer. Download the processed file from the admin dashboard and print it from the shop PC.
- Uploaded files may contain personal information. Limit staff access and periodically remove files no longer needed.

## Current limitations
- Photo crop is centered; there is no freehand crop editor.
- No online payment gateway or automatic UPI verification.
- No direct printer-driver integration.
- No customer self-service live status lookup beyond the order confirmation page.
