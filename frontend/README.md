# AI Workflow Framework - React Vite Frontend

Professional React Vite frontend for the AI Workflow Framework. Built with modern best practices, modular architecture, and comprehensive UI components.

## ✨ Features

- **Authentication**: Secure login/register with JWT tokens
- **Workflow Management**: Create, edit, and manage workflows
- **Execution Tracking**: Monitor workflow executions with detailed logs
- **Scheduler**: Schedule workflows to run automatically
- **Settings**: Configure LLM providers and API keys
- **Responsive Design**: Mobile-friendly interface with professional styling
- **Modular Code**: Each component limited to ~200 lines for maintainability

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Create .env file from example
cp .env.example .env

# Start development server
npm run dev
```

The app will run at `http://localhost:3000`

### Build for Production

```bash
npm run build
npm run preview
```

## 📁 Project Structure

```
src/
├── main.jsx                    # App entry point
├── App.jsx                    # Root component with routing
├── components/
│   ├── ProtectedRoute.jsx     # Auth wrapper for protected pages
│   └── layout/
│       ├── Sidebar.jsx        # Navigation sidebar
│       └── Sidebar.css        # Sidebar styles
├── pages/
│   ├── Home.jsx               # Landing page (redirects)
│   ├── Dashboard.jsx          # Main dashboard with stats
│   ├── Workflows.jsx          # Workflow list management
│   ├── Executions.jsx         # Execution history
│   ├── ExecutionDetail.jsx    # Detailed execution logs
│   ├── Scheduler.jsx          # Workflow scheduling
│   ├── Settings.jsx           # Settings hub
│   ├── auth/
│   │   ├── Login.jsx          # Login form
│   │   └── Register.jsx       # Registration form
│   ├── settings/
│   │   └── LLMSettings.jsx    # LLM configuration
│   └── workflow/
│       └── WorkflowEditor.jsx # Workflow editor
├── utils/
│   └── api.js                 # API client & endpoints
└── styles/
    ├── global.css             # Global styles & variables
    ├── layout.css             # Layout & common components
    └── pages/
        ├── auth.css           # Auth pages styling
        ├── dashboard.css      # Dashboard styling
        ├── list.css           # List pages styling
        ├── detail.css         # Detail pages styling
        ├── settings.css       # Settings styling
        └── workflow.css       # Workflow editor styling
```

## 🔑 Key Components

### Authentication Module
- **Login**: Email/password authentication with JWT
- **Register**: New user account creation with validation
- **Protected Routes**: Automatic redirect for unauthorized access

### API Client (`src/utils/api.js`)
Organized API endpoints:
```javascript
// Authentication
authAPI.login(email, password)
authAPI.register(email, password)
authAPI.logout()

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

### UI Components

**Sidebar Navigation**
- Collapsible on mobile
- Active link highlighting
- Quick logout button

**Dashboard**
- Statistics cards with icons
- Recent workflows list
- Quick action buttons

**Workflows Page**
- Search and filter
- Create/edit/delete workflows
- Status badges
- Responsive table

**Executions Page**
- Execution history with status
- Duration tracking
- Detailed view with logs

**Settings Pages**
- LLM provider configuration
- API key management
- Temperature and token controls

## 🎨 Styling System

Professional CSS with:
- **CSS Variables** for colors, spacing, shadows
- **Dark mode support** with `prefers-color-scheme`
- **Mobile responsive** with breakpoints at 768px
- **Smooth transitions** on all interactive elements
- **Professional color palette**:
  - Primary: #2563eb (Blue)
  - Success: #10b981 (Green)
  - Danger: #ef4444 (Red)
  - Warning: #f59e0b (Amber)

### Using CSS Variables
```css
color: var(--primary);
background: var(--bg-secondary);
padding: var(--radius-lg);
transition: var(--transition);
```

## 🔐 Authentication Flow

1. User submits login/register form
2. API returns JWT token
3. Token stored in localStorage and set in API headers
4. Protected routes check token on navigation
5. Logout clears token and redirects to login

```javascript
// Set token
setAuthToken(token);

// Use in API requests
api.defaults.headers.common['Authorization'] = `Bearer ${token}`;

// On logout
setAuthToken(null);
```

## 🚀 API Integration

All API calls use Axios with base URL configuration:
```javascript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

Configure in `.env`:
```
VITE_API_URL=http://localhost:8000
```

## 📱 Responsive Design

- **Desktop**: Full layout with sidebar navigation
- **Tablet**: Adjusted grid columns, compact spacing
- **Mobile**: Single column, collapsed sidebar, touch-friendly buttons

## 🔄 State Management

Uses React hooks:
- `useState` for component state
- `useEffect` for side effects and data fetching
- `useNavigate` for routing
- `useParams` for URL parameters

## 🧪 Testing

Run linting:
```bash
npm run lint
```

## 📦 Dependencies

- **react**: UI framework
- **react-router-dom**: Client-side routing
- **axios**: HTTP client
- **lucide-react**: Icon library
- **@xyflow/react**: Node-based editor (optional for workflow builder)

## 🎯 Code Standards

- Maximum 200 lines per component
- Clear comments for complex logic
- Consistent naming conventions
- Modular component structure
- Reusable CSS classes

## 🛠️ Development

### Add New Page
1. Create file in `src/pages/`
2. Add route in `App.jsx`
3. Create page-specific styles in `src/styles/pages/`
4. Use `ProtectedRoute` wrapper if authenticated required

### Add New API Endpoint
1. Add function in `src/utils/api.js`
2. Use organized endpoint groups
3. Use consistent naming pattern

### Add New Component
1. Create file in `src/components/`
2. Keep under 200 lines
3. Add comprehensive comments
4. Create CSS file with `.module.css` or in `styles/`

## 🚀 Deployment

### Build
```bash
npm run build
# Output in dist/ folder
```

### Deploy to Vercel
```bash
npm install -g vercel
vercel
```

### Docker
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "preview"]
```

## 📝 Environment Variables

- `VITE_API_URL`: Backend API URL (default: http://localhost:8000)
- `VITE_APP_NAME`: Application name
- Feature flags for enabling/disabling features

## 🤝 Contributing

1. Follow the modular structure
2. Keep components under 200 lines
3. Add comments for clarity
4. Test on mobile and desktop
5. Update this README for new features

## 📄 License

Private - AI Workflow Framework

## 📞 Support

For issues or questions, contact the development team.

---

**Built with ❤️ using React, Vite, and modern web standards**
