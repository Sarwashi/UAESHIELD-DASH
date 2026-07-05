# UAE SHIELD RP - Render Ready

## Local Run

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Render Deployment

### Render Settings

Use these settings if you create the service manually:

```text
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

### Required Environment Variables

Add these in Render → Environment:

```env
SECRET_KEY=اكتب_اي_كود_طويل
REQUIRE_LOGIN=true
ADMIN_PASSWORD=كلمة_مرور_الإدارة
DISCORD_WEBHOOK_URL=رابط_الدسكورد_ويبهوك
DATABASE_PATH=/var/data/uae_shield.db
AUTO_SEND_DASHBOARD_ON_CHANGE=false
APPROVER_POSITIONS=مسؤول الإدارة العليا,مسؤول الادارة العليا
PROMOTION_ALLOWED_POSITIONS=مسؤول الإدارة العليا,مسؤول الادارة العليا,مسؤول الاداريين
LEAVE_ALLOWED_POSITIONS=مسؤول الإدارة العليا,مسؤول الادارة العليا,مسؤول الاداريين,نائب مسؤول الاداريين
```

### Persistent Disk

For SQLite data to stay saved, add a Render Disk:

```text
Mount Path: /var/data
Size: 1 GB
```

If you deploy using `render.yaml`, the disk is already configured.

## Common Render Error

If you see:

```text
npm run start
package.json not found
```

Render detected the wrong environment. Change it to:

```text
Environment: Python
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```
