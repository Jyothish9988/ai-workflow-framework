# Quick Start Guide - React Vite Frontend

## 🚀 Setup in 5 Minutes

### 1. Install
```bash
npm install
```

### 2. Configure
```bash
cp .env.example .env
# Edit VITE_API_URL to your backend
```

### 3. Run
```bash
npm run dev
# Visit http://localhost:3000
```

### 4. Login
Use test credentials from your backend

### 5. Build (Production)
```bash
npm run build  # Creates dist/
npm run preview  # Test build locally
```

---

## 📁 Project Structure

```
/
├── index.html              # HTML entry
├── vite.config.js          # Vite config
├── package.json            # Dependencies
├── .env.example            # Environment template
├── src/
│   ├── main.jsx            # React entry
│   ├── App.jsx             # Root component + routing
│   ├── components/
│   │   ├── ProtectedRoute.jsx
│   │   └── layout/
│   │       ├── Sidebar.jsx
│   │       └── Sidebar.css
│   ├── pages/
│   │   ├── Home.jsx
│   │   ├── Dashboard.jsx
│   │   ├── Workflows.jsx
│   │   ├── Executions.jsx
│   │   ├── ExecutionDetail.jsx
│   │   ├── Scheduler.jsx
│   │   ├── Settings.jsx
│   │   ├── auth/
│   │   │   ├── Login.jsx
│   │   │   └── Register.jsx
│   │   ├── settings/
│   │   │   └── LLMSettings.jsx
│   │   └── workflow/
│   │       └── WorkflowEditor.jsx
│   ├── styles/
│   │   ├── global.css
│   │   ├── layout.css
│   │   └── pages/
│   │       ├── auth.css
│   │       ├── dashboard.css
│   │       ├── detail.css
│   │       ├── list.css
│   │       ├── settings.css
│   │       └── workflow.css
│   └── utils/
│       └── api.js          # API client
└── dist/                   # Production build
```

---

## 🔌 API Integration

Edit `src/utils/api.js` to match your backend:

```javascript
// Change this line:
const API_BASE_URL = 'http://localhost:8000';

// To your backend URL:
const API_BASE_URL = 'https://your-api.com';
```

### Available Endpoints

```javascript
// Auth
authAPI.login(email, password)
authAPI.register(email, password)

// Workflows
workflowAPI.getAll()
workflowAPI.getById(id)
workflowAPI.create(data)
workflowAPI.update(id, data)
workflowAPI.delete(id)

// Executions
executionAPI.getAll()
executionAPI.getById(id)
executionAPI.execute(workflowId, input)

// Scheduler
schedulerAPI.getAll()
schedulerAPI.create(data)
schedulerAPI.update(id, data)
schedulerAPI.delete(id)

// Settings
settingsAPI.getLLMSettings()
settingsAPI.updateLLMSettings(data)
```

---

## 🎨 Customize Styling

Edit CSS variables in `src/styles/global.css`:

```css
:root {
  --primary: #2563eb;          /* Change main color */
  --success: #10b981;          /* Change success color */
  --danger: #ef4444;           /* Change error color */
  /* ... more variables */
}
```

---

## 📱 Testing on Mobile

```bash
# Build and serve locally
npm run build
npm run preview

# Or use your phone to access:
http://YOUR_COMPUTER_IP:3000
```

---

## 🐛 Troubleshooting

**Port 3000 already in use?**
```bash
npm run dev -- --port 3001
```

**CORS errors?**
Configure backend CORS to allow:
```
http://localhost:3000
```

**Build too slow?**
```bash
# Use faster build
npm run build -- --sourcemap=false
```

---

## 📦 Add New Dependencies

```bash
npm install axios-retry  # Add retry logic
npm install zustand      # Add state management
npm install zod          # Add validation
```

---

## ✅ Pre-Deployment Checklist

- [ ] API URL configured in .env
- [ ] Backend CORS allows frontend domain
- [ ] All pages tested in browser
- [ ] Mobile responsiveness verified
- [ ] Forms tested and validated
- [ ] Error states handled gracefully
- [ ] Loading states visible
- [ ] Logout works properly
- [ ] Token refresh working
- [ ] No console errors

---

## 🚢 Deploy to Vercel

```bash
npm install -g vercel
vercel login
vercel
```

Set environment variables in Vercel dashboard:
```
VITE_API_URL=https://your-api.com
```

---

## 🆘 Need Help?

1. Check `README.md` for detailed docs
2. Look at component comments for usage
3. Review error messages in console
4. Check network tab for API issues
5. Verify environment variables

---

**All set! Happy coding! 🎉**
