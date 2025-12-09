# 🚀 PrizmAI - AI-Powered Project Management Platform

> **Kanban Boards Powered by AI**

PrizmAI combines visual project management with AI that helps you work smarter—no setup required, just start organizing. Built with Django, Python, Google Gemini API, WebSockets, and a professional REST API.

**Open-source portfolio project** demonstrating full-stack development, AI integration, enterprise security, and modern software architecture.

---

## ✨ Key Features

- ✅ **Visual Kanban Boards** - Drag & drop task management with smart column suggestions
- 🧠 **AI-Powered Insights** - Intelligent recommendations for priorities, assignments, and deadlines
- 📊 **Burndown Charts & Forecasting** - Real-time sprint progress with completion predictions
- 🚨 **Scope Creep Detection** - Automatic alerts when project scope grows unexpectedly
- ⚠️ **Conflict Detection** - Identifies resource, schedule, and dependency conflicts
- 💰 **Budget & ROI Tracking** - Control finances with AI cost optimization
- 🎓 **AI Coach** - Proactive suggestions to improve project management decisions
- 🔍 **Explainable AI** - Every recommendation includes "why" for full transparency
- 📚 **Knowledge Base & Wiki** - Markdown documentation with AI-assisted insights
- 🔐 **Enterprise Security** - 9.5/10 security rating with comprehensive protection
- 🌐 **RESTful API** - 20+ endpoints for integrations (Slack, Teams, Jira-ready)
- 📱 **Real-Time Collaboration** - WebSocket support for live updates and chat
- 🔗 **Webhook Integration** - Event-driven automation with external apps

**→ [See all 11 features in detail](FEATURES.md)**

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- pip
- Virtual environment (recommended)

### Installation (5 minutes)

```bash
# Clone the repository
git clone https://github.com/paulavishek/PrizmAI.git
cd PrizmAI

# Create and activate virtual environment
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create a superuser (optional)
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

**Open http://localhost:8000** and start creating boards!

**→ [Full setup guide with configuration options](SETUP.md)**

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[📖 USER_GUIDE.md](USER_GUIDE.md)** | Practical usage, examples, and best practices |
| **[✨ FEATURES.md](FEATURES.md)** | Detailed feature descriptions (11 major features) |
| **[🔌 API_DOCUMENTATION.md](API_DOCUMENTATION.md)** | REST API reference with 20+ endpoints |
| **[🪝 WEBHOOKS.md](WEBHOOKS.md)** | Webhook integration and automation guide |
| **[🔒 SECURITY_OVERVIEW.md](SECURITY_OVERVIEW.md)** | Security features and compliance |
| **[⚙️ SETUP.md](SETUP.md)** | Installation and configuration guide |
| **[🤝 CONTRIBUTING.md](CONTRIBUTING.md)** | How to contribute to the project |

---

## 🛠 Technology Stack

**Backend:**
- Python 3.10+ with Django 5.2.3
- Django REST Framework 3.15.2
- Google Gemini API (AI features)
- Django Channels 4.1.0 (WebSockets)
- PostgreSQL/SQLite

**Frontend:**
- HTML5, CSS3, JavaScript
- Bootstrap 5
- Real-time updates via WebSockets

**Security:**
- bleach 6.1.0 (XSS prevention)
- django-csp 3.8 (Content Security Policy)
- django-axes 8.0.0 (Brute force protection)
- OAuth 2.0 (Google login)
- HMAC signature verification

**Deployment Ready:**
- Docker containerization
- Self-hosted or cloud deployment
- Kubernetes-ready

---

## 🔒 Security Highlights

- **9.5/10 Security Rating** - Comprehensive vulnerability scanning and testing
- **Brute Force Protection** - Account lockout after 5 failed attempts
- **XSS & CSRF Protection** - HTML sanitization and token validation
- **SQL Injection Prevention** - Django ORM with parameterized queries
- **Secure File Uploads** - MIME type validation and malicious content detection
- **Data Isolation** - Organization-based multi-tenancy
- **Audit Logging** - Complete audit trail of sensitive operations
- **HTTPS Enforcement** - Encrypted data in transit with HSTS

**→ [Complete security documentation](SECURITY_OVERVIEW.md)**

---

## 📊 Why Choose PrizmAI?

| Feature | PrizmAI | Others |
|---------|---------|--------|
| **AI Recommendations** | ✅ Yes | Limited/No |
| **Explainable AI** | ✅ Full transparency | N/A |
| **Scope Creep Detection** | ✅ Automated | Manual |
| **Burndown Forecasting** | ✅ AI-powered | Basic/No |
| **Conflict Detection** | ✅ Real-time | Limited |
| **Self-Hosted** | ✅ Yes | Limited |
| **Open Source** | ✅ MIT License | No |
| **Cost** | 🆓 Free | Paid |

---

## 🎯 Use Cases

### Software Development Teams
Sprint planning, bug tracking, release management, burndown forecasting

### Marketing & Product Teams
Campaign planning, content tracking, timeline management

### Operations & Support
Process coordination, service requests, incident management

### Any Team Project
If you have 2+ people working together, PrizmAI helps you stay organized

**→ [See real-world examples and workflows](USER_GUIDE.md)**

---

## 🏆 Security Achievements

- ✅ Comprehensive security audit completed
- ✅ All critical vulnerabilities fixed
- ✅ Enterprise security features implemented
- ✅ Dependency security scanning passed
- ✅ 9.5/10 security rating achieved

---

## 📄 License

MIT License - Free to use, modify, and deploy anywhere.

---

## 🤝 Support & Contributing

- **📖 Documentation** - Comprehensive guides included
- **🐛 Issues** - [Report bugs on GitHub](https://github.com/paulavishek/PrizmAI/issues)
- **💬 Discussions** - Community forum for questions
- **🔧 Contributing** - Pull requests welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 👨‍💻 About This Project

PrizmAI is a **portfolio project** showcasing:
- Full-stack web development (Django + Modern Frontend)
- AI/ML integration and prompt engineering
- Enterprise security implementation
- REST API design and development
- Real-time communication (WebSockets)
- Database architecture and optimization
- DevOps and deployment practices
- Project management domain expertise

Perfect for developers building their portfolio or evaluating production-ready Python/Django applications.

---

## 🚀 Ready to Get Started?

1. **[Install PrizmAI](SETUP.md)** - Follow the setup guide
2. **[Explore Features](FEATURES.md)** - Learn what PrizmAI can do
3. **[Read User Guide](USER_GUIDE.md)** - See practical examples
4. **Create Your First Board** - Start managing projects with AI

---

**Built with ❤️ by [Avishek Paul](https://github.com/paulavishek)**
