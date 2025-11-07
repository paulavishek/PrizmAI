# Security Policy

## Supported Versions

We actively support the following versions of PrizmAI:

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in PrizmAI, please report it responsibly:

### How to Report

1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Send an email to: [your-email@domain.com] with:
   - A clear description of the vulnerability
   - Steps to reproduce the issue
   - The potential impact
   - Any suggested fixes (optional)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Critical issues within 14 days, others within 30 days

### Security Best Practices for Users

1. **Environment Variables**: Never commit `.env` files or expose API keys
2. **Database Security**: Use strong passwords and restrict database access
3. **HTTPS**: Always use HTTPS in production
4. **Updates**: Keep all dependencies updated regularly
5. **Access Control**: Implement proper user authentication and authorization

### Areas of Concern

Please pay special attention to:

- Authentication and authorization mechanisms
- API endpoints and data validation
- File upload functionality
- Database queries and injection vulnerabilities
- Cross-site scripting (XSS) prevention
- Cross-site request forgery (CSRF) protection

### Out of Scope

The following are generally considered out of scope:
- Issues requiring physical access to systems
- Social engineering attacks
- Vulnerabilities in third-party dependencies (please report to upstream)
- Issues affecting only unsupported browsers

## Acknowledgments

We appreciate the security research community and will acknowledge researchers who responsibly disclose vulnerabilities (with their permission).

## Contact

For any questions about this security policy, please contact the maintainers.
