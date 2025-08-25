# Security Policy

## Reporting Security Vulnerabilities

We take the security of the Windows Autoclicker seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### **Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@tmhsdigital.com**

## What to Include

Please include the following information in your security report:
- A description of the vulnerability
- Steps to reproduce the vulnerability
- Potential impact of the vulnerability
- Any suggested fixes or mitigations
- Your contact information for follow-up

## Response Process

1. **Acknowledgment**: We will acknowledge receipt of your vulnerability report within 48 hours.
2. **Assessment**: We will assess the reported vulnerability and determine its validity and severity.
3. **Updates**: We will provide regular updates on the status of the investigation.
4. **Resolution**: Once the vulnerability is confirmed and fixed, we will:
   - Create a security advisory
   - Release a patch or new version
   - Publicly disclose the vulnerability (if not already public)

## Security Assessment Criteria

We assess vulnerabilities based on:
- **Severity**: Critical, High, Medium, Low
- **Impact**: Potential harm to users or systems
- **Exploitability**: How easily the vulnerability can be exploited
- **Scope**: What systems or data are affected

## Known Security Considerations

### Current Security Features
- **Input Validation**: All user inputs are validated and sanitized
- **Safe Defaults**: Application uses secure default settings
- **Error Handling**: Safe error handling prevents information leakage
- **Resource Limits**: Built-in limits prevent resource exhaustion
- **Access Control**: No network access or remote control capabilities

### Areas of Focus
- **Code Injection**: Protection against malicious input
- **Privilege Escalation**: Prevention of unauthorized access
- **Data Exposure**: Protection of sensitive user information
- **Denial of Service**: Prevention of application disruption
- **Race Conditions**: Thread-safe operation

## Safe Usage Guidelines

For secure usage of the autoclicker:
- Run with least privilege (standard user account)
- Keep the application updated to latest version
- Do not use for unauthorized activities
- Monitor system resource usage
- Use in compliance with local laws and regulations

## Responsible Disclosure

We follow responsible disclosure practices:
- We will give credit to vulnerability reporters (if desired)
- We will work with researchers to ensure proper disclosure timing
- We will not take legal action against good-faith security research
- We will coordinate with affected parties before public disclosure

## Security Updates

Security updates will be:
- Released as soon as possible after fixes are developed
- Clearly marked as security-related in release notes
- Backported to supported versions when applicable
- Communicated through security advisories

## Contact

For security-related inquiries:
- **Primary**: security@tmhsdigital.com
- **Backup**: info@tmhsdigital.com
- **PGP Key**: [Available upon request]

## Acknowledgments

We appreciate the security research community for helping keep our users safe. Security researchers who report vulnerabilities responsibly will be acknowledged in our security advisories (unless they prefer to remain anonymous).
