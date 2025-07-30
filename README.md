# 🍽️ Restaurant Reservation Management System

A modern, full-stack restaurant reservation management system built with React frontend and FastAPI backend. This system provides comprehensive table management, reservation handling, customer management, and analytics for restaurant owners and staff.

## ✨ Features

### 🎯 Core Features
- **Table Management**: Add, edit, delete tables with indoor/outdoor locations
- **Reservation System**: Create, manage, and track reservations
- **Customer Management**: Customer profiles and reservation history
- **Waitlist Management**: Handle overflow with waitlist system
- **Real-time Analytics**: Comprehensive reporting and insights

### 👥 User Management
- **Role-based Access Control**: Admin, Sub-Admin, and Staff roles
- **User Authentication**: Secure login system with session management
- **Permission Management**: Feature access based on user roles

### 📊 Analytics & Reporting
- **Dashboard Analytics**: Real-time occupancy rates and statistics
- **Peak Hours Analysis**: Identify busy periods
- **Customer Analytics**: Customer behavior and preferences
- **Table Utilization**: Monitor table usage efficiency
- **Revenue Tracking**: Sales and revenue reports
- **Custom Reports**: Generate reports for any variables

### 🎨 Modern UI/UX
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Beautiful Interface**: Modern Material-UI design with gradients
- **Interactive Elements**: Hover effects, animations, and smooth transitions
- **Grid/List Views**: Multiple viewing options for tables
- **Real-time Updates**: Live data updates without page refresh

### 🔧 Advanced Features
- **Operating Hours Management**: Set and manage restaurant hours
- **Holiday Management**: Handle special days and closures
- **Logo Upload**: Customize restaurant branding
- **Capacity Management**: Indoor and outdoor seating limits
- **Email Notifications**: Automated customer communications
- **SMS Notifications**: Simulated SMS alerts
- **Customer Portal**: Public booking form for customers
- **Online Booking**: Customer-facing reservation system

## 🏗️ Architecture

### Frontend (React + Vite)
- **Framework**: React 18 with Vite
- **UI Library**: Material-UI (MUI) v5
- **Routing**: React Router v6
- **State Management**: React Hooks
- **Styling**: MUI System with custom themes
- **Charts**: Chart.js for analytics

### Backend (FastAPI + Python)
- **Framework**: FastAPI with Uvicorn
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: API key-based authentication
- **File Upload**: Logo and image handling
- **Email**: SMTP integration for notifications
- **Validation**: Pydantic models for data validation

## 🚀 Quick Start

### Prerequisites
- Node.js 16+ and npm
- Python 3.8+
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd restaurant-reservation
   ```

2. **Backend Setup**
   ```bash
   cd backend
   pip3 install -r requirements.txt
   python3 main.py
   ```
   Backend will run on: http://localhost:8000

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Frontend will run on: http://localhost:5173

4. **Access the Application**
   - **Admin Panel**: http://localhost:5173/admin
   - **Customer Portal**: http://localhost:5173/book
   - **API Documentation**: http://localhost:8000/docs

## 📁 Project Structure

```
restaurant-reservation/
├── backend/
│   ├── main.py              # Backend entry point
│   ├── models.py            # Database models and API endpoints
│   ├── requirements.txt     # Python dependencies
│   └── restaurant.db        # SQLite database
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/          # Page components
│   │   ├── App.jsx         # Main app component
│   │   └── main.jsx        # App entry point
│   ├── package.json        # Node.js dependencies
│   └── vite.config.js      # Vite configuration
├── .gitignore              # Git ignore rules
└── README.md               # Project documentation
```

## 🔐 Authentication

### Default Admin Credentials
- **Username**: admin
- **Password**: admin123
- **API Key**: admin-secret-key-2024

### User Roles
- **Admin**: Full access to all features
- **Sub-Admin**: Limited access (no user management)
- **Staff**: Basic reservation management only

## 🌐 API Endpoints

### Admin Endpoints (Require API Key)
- `GET /admin/tables` - List all tables
- `POST /admin/tables` - Create new table
- `PUT /admin/tables/{id}` - Update table
- `DELETE /admin/tables/{id}` - Delete table
- `GET /admin/reservations` - List reservations
- `POST /admin/reservations` - Create reservation
- `GET /admin/customers` - List customers
- `GET /admin/analytics/*` - Analytics endpoints

### Public Endpoints
- `POST /reservations` - Public booking (requires public key)
- `GET /operating-hours` - Restaurant hours
- `GET /is-open` - Restaurant status

## 🎨 UI Components

### Pages
- **Dashboard**: Overview with statistics and quick actions
- **Tables**: Table management with grid/list views
- **Reservations**: Reservation management with filters
- **Customers**: Customer management and profiles
- **Analytics**: Comprehensive reporting and charts
- **Settings**: System configuration and user management
- **Waitlist**: Waitlist management
- **Make Reservation**: Quick reservation creation for staff

### Features
- **Responsive Design**: Mobile-first approach
- **Dark/Light Theme**: Theme switching capability
- **Animations**: Smooth transitions and hover effects
- **Real-time Updates**: Live data synchronization
- **Error Handling**: Comprehensive error boundaries
- **Loading States**: User-friendly loading indicators

## 📊 Analytics Features

### Dashboard Metrics
- Total tables and occupancy rate
- Recent reservations and waitlist
- Peak hours and customer trends
- Revenue and table utilization

### Custom Reports
- Date range selection
- Multiple chart types
- Export capabilities
- Real-time data updates

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the backend directory:
```env
DATABASE_URL=sqlite:///restaurant.db
SECRET_KEY=your-secret-key
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

### API Keys
- **Admin Key**: `admin-secret-key-2024` (for admin operations)
- **Public Key**: `public-booking-key` (for customer bookings)

## 🚀 Deployment

### Backend Deployment (Python/FastAPI)
1. **Heroku**
   ```bash
   heroku create your-app-name
   git push heroku main
   ```

2. **Railway**
   ```bash
   railway login
   railway init
   railway up
   ```

3. **DigitalOcean App Platform**
   - Connect GitHub repository
   - Configure build settings
   - Deploy automatically

### Frontend Deployment (React)
1. **Vercel**
   ```bash
   npm install -g vercel
   vercel
   ```

2. **Netlify**
   ```bash
   npm run build
   # Upload dist folder to Netlify
   ```

3. **GitHub Pages**
   ```bash
   npm run build
   # Configure GitHub Actions for deployment
   ```

### Database Setup
- **Production**: Use PostgreSQL or MySQL
- **Development**: SQLite (included)
- **Migrations**: SQLAlchemy Alembic for schema changes

## 🛠️ Development

### Adding New Features
1. Create feature branch: `git checkout -b feature/new-feature`
2. Implement changes in both frontend and backend
3. Test thoroughly
4. Create pull request

### Code Style
- **Frontend**: ESLint + Prettier
- **Backend**: Black + Flake8
- **Commits**: Conventional commits format

### Testing
```bash
# Frontend tests
cd frontend
npm test

# Backend tests
cd backend
python -m pytest
```

## 📱 Mobile Support

The application is fully responsive and works on:
- **Desktop**: Full feature access
- **Tablet**: Optimized layout
- **Mobile**: Touch-friendly interface

## 🔒 Security Features

- **API Key Authentication**: Secure endpoint access
- **Role-based Permissions**: Feature access control
- **Input Validation**: Pydantic model validation
- **SQL Injection Protection**: SQLAlchemy ORM
- **XSS Protection**: React built-in protection
- **CSRF Protection**: API key validation

## 📈 Performance

- **Frontend**: Vite for fast development and optimized builds
- **Backend**: FastAPI for high-performance API
- **Database**: Optimized queries with SQLAlchemy
- **Caching**: React query for data caching
- **Lazy Loading**: Code splitting for better performance

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the API docs at `/docs`

## 🎉 Acknowledgments

- Material-UI for the beautiful components
- FastAPI for the excellent backend framework
- React team for the amazing frontend library
- Vite for the fast build tool

---

**Built with ❤️ for restaurant owners and staff** 