# Session 43 Features - Usage Guide

**Last Updated:** 2025-11-08
**Status:** All features tested and working (100% success rate)

---

## 🎯 Overview

Session 43 added three major UX improvements:
1. **Setup Wizard** - 5-minute guided setup for new users
2. **Health Dashboard** - Real-time system monitoring
3. **User Management** - RBAC user administration (existing feature, now documented)

All features are production-ready and fully tested.

---

## 🚀 Quick Start

### First-Time Setup (Setup Wizard)

**Access:** `http://localhost:5173` (automatic redirect if setup needed)

**Time Required:** ~5 minutes

#### Step 1: Choose LLM Provider

**Recommended:** Groq (free, fast, no credit card required)

| Provider | Speed | Cost | Best For |
|----------|-------|------|----------|
| **Groq** | ⚡⚡⚡ Fast | 💰 FREE | Testing, development |
| OpenAI | ⚡⚡ Medium | 💰💰 Paid | Production quality |
| Gemini | ⚡ Slower | 💰 Free tier | Balanced option |

**Actions:**
1. Select provider from dropdown
2. Enter API key
3. (Optional) Specify model name
4. Click "Validate & Continue"

**Example:**
```
Provider: Groq
API Key: gsk_xxxxxxxxxxxxxxxxxxxx
Model: llama-3.3-70b-versatile (default)
```

#### Step 2: Create Admin User

**Required Fields:**
- Username (min 3 characters)
- Password (min 12 characters, complexity required)

**Optional Fields:**
- Email
- Enable MFA (TOTP-based)

**Password Requirements:**
- ✅ At least 12 characters
- ✅ Uppercase + lowercase letters
- ✅ Numbers
- ✅ Special characters (@, !, #, etc.)

**Example:**
```
Username: admin
Password: MySecure@Pass2024!
Email: admin@example.com
MFA: Disabled
```

#### Step 3: Complete Setup

**Actions:**
1. Review configuration summary
2. Click "Complete Setup"
3. Wait for confirmation
4. Redirected to Dashboard

**Result:**
- `.env` file created/updated
- Admin user created in database
- System ready to use

---

## 📊 Health Dashboard

**Access:** Dashboard → System Health (top section)

**Update Frequency:** 10 seconds (automatic)

### Components Monitored

#### 1. API Service
```json
{
  "status": "running",
  "uptime_seconds": 3600,
  "python_version": "3.11.14"
}
```

**Indicators:**
- 🟢 Green: API responding normally
- 🔴 Red: API down or errors

#### 2. Worker Service
```json
{
  "status": "active",
  "last_message_age_seconds": 45,
  "messages_last_hour": 52
}
```

**Status Meanings:**
- **active**: Messages sent within last 5 minutes
- **slow**: No messages in 5-60 minutes
- **idle**: No messages ever sent

**Indicators:**
- 🟢 Green (active): Generating messages normally
- 🟡 Yellow (slow): May need restart
- 🔴 Red (idle): Not started or crashed

#### 3. Database
```json
{
  "status": "connected",
  "type": "postgresql",
  "active_bots": 4,
  "total_messages": 159
}
```

**Indicators:**
- 🟢 Green: Connected and responsive
- 🔴 Red: Connection failed

#### 4. Redis (Optional)
```json
{
  "status": "connected",
  "available": true
}
```

**Status Values:**
- **connected**: Working normally
- **unavailable**: Connection failed (but optional)
- **not_configured**: Not enabled in `.env`

#### 5. Disk Usage
```json
{
  "usage_percent": 3.9,
  "free_gb": 918.5,
  "total_gb": 1006.9
}
```

**Alerts:**
- 🟡 Yellow: >80% used
- 🔴 Red: >90% used

### Alert System

Alerts appear as banners when issues detected:

**Critical Alerts (Red):**
- Database connection failed
- Disk >90% full
- No messages in 24+ hours

**Warning Alerts (Yellow):**
- Worker slow (5-60 min idle)
- Disk >80% full
- Test failures

**Example Alert:**
```
⚠️ Warning: Worker slow - No messages generated in last 15 minutes
```

### Manual Actions

**Refresh Button:**
- Forces immediate update
- Bypasses 10-second auto-refresh
- Useful after making changes

**Auto-Refresh Toggle:**
- On (default): Updates every 10 seconds
- Off: Manual refresh only

---

## 👥 User Management

**Access:** Dashboard → Users tab

**Requires:** Admin role

### User Roles

| Role | Permissions | Use Case |
|------|-------------|----------|
| **viewer** | Read-only access | Monitoring, reporting |
| **operator** | Manage bots/chats/settings | Day-to-day operations |
| **admin** | Full access | System administration |

### Creating Users

**Steps:**
1. Click "Add User" button
2. Fill in form:
   - Username (unique)
   - Password (meets requirements)
   - Role selection
   - (Optional) Enable MFA
3. Click "Create"

**Result:**
- User created in database
- API key auto-generated
- Email sent (if configured)

### Managing Users

**Available Actions:**
- ✏️ Edit user details
- 🔄 Rotate API key
- 🔐 Reset password
- 🗑️ Delete user
- ⏸️ Disable/enable account

**API Key Rotation:**
1. Click "Rotate" next to user
2. Confirm action
3. New key displayed (copy immediately!)
4. Old key invalidated

**Security Note:** API keys are hashed in database and cannot be retrieved after creation.

---

## 🔧 Troubleshooting

### Setup Wizard Issues

**Problem:** "API key validation failed"

**Solutions:**
1. Check API key is correct (no extra spaces)
2. Verify provider matches key type
3. Test key directly on provider website
4. Check internet connection

**Problem:** "Admin user already exists"

**Solutions:**
1. Use different username
2. Or skip wizard and login with existing credentials

### Health Dashboard Issues

**Problem:** All components show "error"

**Solutions:**
1. Check API is running: `docker ps`
2. Verify API_KEY in `.env` matches frontend
3. Check browser console for errors
4. Try manual refresh

**Problem:** Worker shows "idle" but should be active

**Solutions:**
1. Check `simulation_active` setting = true
2. Verify at least one enabled bot exists
3. Verify at least one enabled chat exists
4. Check worker logs: `docker logs piyasa_worker_1`

### User Management Issues

**Problem:** Cannot create user

**Solutions:**
1. Ensure logged in as admin
2. Check username doesn't already exist
3. Verify password meets requirements
4. Check database connection

**Problem:** Cannot login with new user

**Solutions:**
1. Wait 5 seconds for session to propagate
2. Verify correct username/password
3. Check user is enabled (not disabled)
4. Try API key authentication instead

---

## 📈 Best Practices

### Setup Wizard
- ✅ Use Groq for development (free)
- ✅ Use strong admin password
- ✅ Enable MFA for production
- ✅ Keep API keys secure
- ❌ Don't share admin credentials

### Health Dashboard
- ✅ Monitor daily for trends
- ✅ Set up alerts for critical issues
- ✅ Keep disk usage <80%
- ✅ Restart worker if slow >1 hour
- ❌ Don't ignore persistent warnings

### User Management
- ✅ Use viewer role for read-only users
- ✅ Rotate API keys regularly
- ✅ Disable unused accounts
- ✅ Document role assignments
- ❌ Don't create unnecessary admin accounts

---

## 🔗 Related Documentation

- [README.md](../README.md) - Installation and setup
- [CLAUDE.md](../CLAUDE.md) - Development guide
- [SESSION43_TAMAMLANDI.md](../SESSION43_TAMAMLANDI.md) - Session 43 completion report
- [error_management.md](error_management.md) - Error handling strategy

---

## 📞 Support

**Found a bug?** Create an issue on GitHub

**Need help?** Check README FAQ section

**Feature request?** Submit via GitHub issues

---

**Last Test Run:** 2025-11-08 20:04:39
**Test Success Rate:** 100% (14/14 tests passed)
**System Status:** ✅ All features operational
