# SecureStay — Deliberately Vulnerable Web Application

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-black)
![SQLite](https://img.shields.io/badge/Database-SQLite-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![Security Lab](https://img.shields.io/badge/Purpose-Security%20Lab-red)

SecureStay is a deliberately vulnerable web application designed as a hands-on web penetration testing laboratory.

The project simulates a small vacation-rental platform and intentionally contains multiple security vulnerabilities that can be chained together to obtain administrative access.

The application is designed to be deployed locally with Docker and used as the target for a separate black-box penetration testing project.

> ⚠️ **Disclaimer**
>
> SecureStay is intentionally vulnerable.
> It is designed exclusively for authorized security testing, education, CTF-style practice, and local laboratory environments.
> Do not expose this application to the public Internet.

## 🎯 Project Goals

The main goals of this project are:

- Build a realistic vulnerable web application from scratch.
- Practice identifying and exploiting common web vulnerabilities.
- Create multiple independent attack paths.
- Demonstrate vulnerability chaining.
- Separate the vulnerable application from the penetration testing project.
- Produce professional penetration testing documentation based on real evidence.
- Practice reporting findings using a professional reporting platform such as SysReptor.

The application is intentionally designed so that compromising the application requires more than discovering a single vulnerability.

## 🏗️ Architecture

SecureStay is a small Python web application running inside Docker.

The application uses a lightweight SQLite database for application data and exposes a single HTTP service for testing.

### Technology Stack

- **Python**
- **Flask**
- **SQLite**
- **Werkzeug**
- **HTML / CSS**
- **Docker**
- **Docker Compose**

The application is available locally at:

    http://securestay.test:8080

The hostname can be mapped locally through `/etc/hosts`:

    127.0.0.1 securestay.test

---

## 🚀 Running the Lab

### Requirements

The following software is recommended:

- Docker
- Docker Compose

Optional tools for penetration testing:

- Nmap
- Burp Suite
- ffuf
- curl
- sqlmap

### Start the application

    docker compose up --build

The application should then be available at:

    http://securestay.test:8080

### Stop the application

    docker compose down

### Rebuild the application

    docker compose down
    docker compose up --build

## 🧭 Application Functionality

SecureStay simulates a small vacation-rental platform with functionality for both regular users and administrators.

### Public Functionality

Unauthenticated users can interact with features such as:

- Home page
- Property search
- Property details
- Property brochure downloads
- User authentication

### Authenticated Functionality

Authenticated users can access:

- User profiles
- Bookings
- Messaging
- Password recovery functionality

### Administrative Functionality

Administrative users have access to an administrative dashboard containing application-wide information and management functionality.

Example routes include:

    /
    /login
    /search
    /profile
    /profile/<id>
    /bookings
    /messages
    /messages/send
    /download
    /reset-password
    /admin

Some of these features are intentionally insecure and form part of the security testing laboratory.

---

## 🔎 Security Testing Scope

The application is intentionally designed to expose multiple attack surfaces, including:

- Authentication
- Authorization
- Input handling
- Database queries
- File handling
- Account recovery
- Messaging functionality
- Administrative functionality

The application should be approached as a black-box target during the penetration testing phase.

The source code is provided as part of the laboratory repository, but the separate penetration test should be performed without relying on source-code access.

# 🔐 Security Lab

SecureStay is intentionally vulnerable and contains multiple security weaknesses designed for hands-on penetration testing practice.

The vulnerabilities are not included as isolated examples. Several of them can be chained together to demonstrate realistic attack paths and privilege escalation.

## Vulnerability Classes

The current laboratory includes examples of:

- **SQL Injection**
- **Credential Disclosure**
- **IDOR / Broken Access Control**
- **Account Recovery Weakness**
- **Path Traversal / Arbitrary File Read**
- **Exposed Internal Functionality**
- **Broken Access Control**
- **Administrative Account Takeover**

The exact exploitation techniques and payloads are intentionally not documented in this repository.

The goal is for the application to be assessed as a real black-box target during the penetration testing phase.

---

## 🛣️ Attack Paths

SecureStay contains multiple attack paths that can ultimately lead to administrative access.

### Attack Path 1

The first path demonstrates how an attacker can chain multiple vulnerabilities together:

    SQL Injection
          ↓
    Credential Disclosure
          ↓
    User Authentication
          ↓
    IDOR / Broken Access Control
          ↓
    Administrative Recovery Information
          ↓
    Account Recovery Weakness
          ↓
    Administrative Account

This path demonstrates how individually exploitable weaknesses can combine to produce a significantly greater impact.

### Attack Path 2

A separate path begins without requiring the SQL injection chain:

    Path Traversal
          ↓
    Internal File Disclosure
          ↓
    Internal Support Information
          ↓
    Legacy Support Functionality
          ↓
    Administrative Recovery Information
          ↓
    Account Recovery Weakness
          ↓
    Administrative Account

The two paths intentionally converge on the same administrative objective.

---

## 🏁 Final Objective

The ultimate objective of the laboratory is to obtain genuine administrative authentication.

Successfully authenticating as the administrative user provides access to the administrative dashboard and reveals the final laboratory flag:

    SECURESTAY{...}

The flag is only displayed after successfully obtaining administrative access.

Accessing administrative information through an authorization vulnerability alone does not constitute completion of the laboratory.

## 🎓 Learning Objectives

This laboratory is designed to provide practical experience with common web application security concepts and penetration testing techniques.

### Reconnaissance

- Identify exposed services and technologies.
- Enumerate web application endpoints.
- Map the application's attack surface.
- Identify authentication and authorization boundaries.

### Injection

- Identify SQL injection vulnerabilities.
- Perform boolean-based SQL injection testing.
- Understand UNION-based SQL injection.
- Extract application data through vulnerable database queries.

### Authentication

- Identify exposed credentials.
- Test discovered credentials against application functionality.
- Analyze authentication mechanisms.
- Understand the impact of weak account recovery functionality.

### Authorization

- Identify IDOR vulnerabilities.
- Test horizontal and vertical access controls.
- Identify missing authorization checks.
- Demonstrate privilege escalation through broken access control.

### File Handling

- Test file download functionality.
- Identify path traversal vulnerabilities.
- Demonstrate arbitrary file disclosure.
- Understand the risks of insecure filesystem access.

### Client-Side Security

- Identify stored Cross-Site Scripting vulnerabilities.
- Analyze how untrusted input is stored and rendered.
- Understand the security impact of executing attacker-controlled content in another user's browser.

### Attack Chaining

A major objective of the laboratory is understanding how multiple vulnerabilities can be combined to achieve a larger impact.

For example:

    SQL Injection
          +
    Credential Disclosure
          +
    IDOR
          +
    Account Recovery Weakness
          =
    Administrative Account Takeover

The laboratory also provides an alternative attack path beginning with Path Traversal.

The objective is to understand not only how individual vulnerabilities work, but how they interact within a realistic application.

## 🔬 Penetration Testing Workflow

SecureStay is designed to be paired with a separate penetration testing repository.

The vulnerable application represents the target, while the second repository contains the assessment methodology, evidence, findings, and final report.

The recommended workflow is:

    SecureStay
        │
        │ Target Application
        ▼
    Reconnaissance
        │
        ▼
    Enumeration
        │
        ▼
    Vulnerability Discovery
        │
        ▼
    Exploitation
        │
        ▼
    Attack Chaining
        │
        ▼
    Evidence Collection
        │
        ▼
    Risk Assessment
        │
        ▼
    Professional Reporting

The penetration test should be performed as a black-box assessment without relying on the application's source code.

The objective is to reproduce the perspective of an external security tester who has been provided with access to the application but no knowledge of its internal implementation.

## 📁 Repository Structure

The repository contains the vulnerable SecureStay application and all files required to run the laboratory locally.

A simplified structure is:

    web-pentesting-lab/
    │
    ├── app/
    │   ├── app.py
    │   ├── database.py
    │   ├── logging_config.py
    │   │
    │   ├── files/
    │   │   ├── madrid-brochure.txt
    │   │   ├── barcelona-brochure.txt
    │   │   └── lisbon-brochure.txt
    │   │
    │   ├── internal/
    │   │   └── support-notes.txt
    │   │
    │   ├── static/
    │   │   └── style.css
    │   │
    │   └── templates/
    │       ├── admin.html
    │       ├── bookings.html
    │       ├── index.html
    │       ├── login.html
    │       ├── messages.html
    │       ├── profile.html
    │       ├── property.html
    │       ├── reset_password.html
    │       ├── search.html
    │       └── send_message.html
    │
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    └── README.md

The repository is intentionally self-contained so that the application can be deployed locally without requiring external infrastructure.

## 🖥️ Intended Environment

SecureStay is intended to run in an isolated local laboratory environment.

A typical setup consists of a host machine running penetration testing tools and a Docker container hosting the vulnerable application.

The recommended architecture is:

    ┌─────────────────────────────────────┐
    │             Host Machine            │
    │                                     │
    │  Penetration Testing Tools          │
    │  - Burp Suite                       │
    │  - Nmap                             │
    │  - ffuf                             │
    │  - curl                             │
    │  - sqlmap                           │
    │                                     │
    │              │                      │
    │              ▼                      │
    │       SecureStay :8080              │
    │              │                      │
    │              ▼                      │
    │       Docker Container              │
    │              │                      │
    │              ▼                      │
    │            SQLite                   │
    └─────────────────────────────────────┘

The application should remain accessible only from the local testing environment unless it is deployed inside a specifically isolated security lab.

## ⚠️ Security Warning

SecureStay contains intentional security vulnerabilities and must only be used in controlled environments.

Do not:

- Deploy the application to a production server.
- Expose the application to the public Internet.
- Use real credentials or sensitive information.
- Store personal or confidential data in the laboratory.
- Reuse laboratory credentials outside the lab environment.

The application exists exclusively for authorized security testing, education, and penetration testing practice.

---

## 🎯 Purpose

This project is a practical web application security laboratory focused on learning through hands-on exploitation and professional penetration testing.

The objective is not simply to demonstrate that vulnerabilities exist, but to understand the complete security assessment process:

- Discovering vulnerabilities from a black-box perspective.
- Understanding how individual vulnerabilities can be chained together.
- Demonstrating real security impact.
- Collecting reproducible technical evidence.
- Assessing risk and business impact.
- Providing appropriate remediation recommendations.
- Communicating findings through a professional penetration testing report.

The final objective is to demonstrate the complete workflow from initial reconnaissance to administrative compromise and professional reporting.

---

## 📊 Project Status

The vulnerable application is currently functional and contains multiple intentional vulnerabilities and attack paths.

### Completed

- [x] Vulnerable Flask web application
- [x] Dockerized deployment
- [x] SQLite database
- [x] Authentication functionality
- [x] Property search and booking functionality
- [x] Messaging functionality
- [x] SQL Injection attack path
- [x] Credential disclosure
- [x] IDOR / Broken Access Control
- [x] Account recovery weakness
- [x] Administrative account takeover
- [x] Path Traversal / Arbitrary File Read
- [x] Exposed internal support functionality
- [x] Alternative attack path to administrative access
- [x] Final administrative flag

---

## 👨‍💻 Author

Built as a personal web application security laboratory and penetration testing portfolio project.

The project combines application development, vulnerability research, exploitation, attack-path analysis, evidence collection, and professional security reporting.



