# Coach Fitness Platform

## Overview
Coach Fitness is a comprehensive fitness coach marketplace platform built with FastAPI and Python, featuring a 3-way matching system (coach ↔ gym ↔ client). It functions as "Uber for fitness coaching" with secure authentication. The platform includes a worldwide gym database, OpenStreetMap integration, country selection, and geographic search capabilities. It offers a modern, motivating client dashboard and extensive search functionalities for coaches and gyms based on location and preferences. The business vision is to connect fitness enthusiasts with qualified coaches and gyms efficiently, leveraging technology to streamline the fitness coaching market.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: FastAPI for high-performance API development with automatic documentation.
- **Template Engine**: Jinja2 for server-side HTML rendering.
- **Geographic Services**: Geopy with Nominatim geocoder for location-based searches and custom Haversine formula for distance calculations.
- **Data Layer**: In-memory mock data with architecture prepared for Supabase integration.
- **Authentication & Authorization**: Infrastructure for login/signup, role-based access (client, coach), session management, bcrypt password hashing, and server-side auth on all protected routes.
- **Security**: bcrypt password hashing (with backward compatibility for existing plain-text passwords), secure cookies in production (REPLIT_DEPLOYMENT flag), rate limiting via slowapi on login/OTP/password-reset endpoints, proper 401 JSON responses for API endpoints.

### Frontend Architecture
- **Styling**: Tailwind CSS for responsive, utility-first design.
- **Template Structure**: Base template with block inheritance for consistent layout.
- **UI/UX Decisions**: Modern, minimalist design inspired by Planity, utilizing the Inter font family, clean white backgrounds, subtle borders, and a professional color scheme. Features a motivating client dashboard with progress tracking and achievement badges.

### Feature Specifications
- **Coach Onboarding**: 4-section setup form with profile photo upload, zone, specialties, and gym locations. Includes worldwide gym selection autocomplete via Google Places API.
- **Search & Discovery**:
    - **Homepage Search**: Dual interface for location and specialty with smart autocomplete.
    - **Coach Cards**: Professional display with photo, name, verified badge, rating, specialties, associated gyms, and pricing.
    - **Gym Cards**: Comprehensive information including photo, name, address, opening hours, and coach listings.
    - **Filtering & Sorting**: Quick filters for availability, distance, and price; sorting options for relevance, rating, and distance.
    - **Public Gym Pages**: Allows discovery of coaches by searching gyms via postal codes.
- **Coach Profile Pages**: Public profiles with large photo, full name, rating, city, pricing, specialties, biography, gym locations, and Instagram link.
- **Booking System**: Complete reservation flow with calendar interface and confirmation page. Includes:
    - **Calendar Interface**: Weekly grid view with 30-minute time slots, visual indicators for availability.
    - **Reservation Confirmation**: Planity-style confirmation with service summary, date/time adjustments, and autonomous signup form with email verification (OTP).
    - **Booking Notification Flow**: Email notifications to coach for new bookings, client for confirmation, and automated reminders (24h and 2h before session) via Resend.
    - **Booking Persistence**: Bookings stored in demo_users.json with conflict detection.
- **Client Dashboard**: Redesigned home page with gradient background, motivational quotes, progress bar, upcoming workouts, and badge system.
- **FAQ Section**: Homepage and coach signup page include Planity-style FAQ sections using native HTML5 `<details>`.
- **Testimonials Section**: Coach testimonials with photos, names, gyms, ratings, and quotes on the `/coach-signup` page.

### System Design Choices
- **Modular Data**: JSON-based data layer for gyms and coaches, designed for easy migration.
- **URL Parameters**: Shareable search URLs with parameter persistence.
- **Error Handling**: 404 handling and various UI states for loading, empty results, and errors.
- **Internationalization**: Support for 249 countries with ISO 3166-1 alpha-2 standardization.

## External Dependencies

### Third-Party Services
- **Google Places API**: For worldwide gym search, autocomplete, and coach onboarding.
- **Geopy**: Geographic location services using Nominatim geocoder.
- **Supabase**: Planned integration for user authentication and data storage.
- **Resend**: Transactional email service for OTP verification, password reset, and booking notifications.

### Stripe Subscription System
- **Coach Monthly Subscription**: 29€/month subscription for coaches.
- **Subscription-First Signup**: Payment required before account access for new coaches.
- **Stripe Integration**: Securely connected via Replit.
- **Coach Signup Flow**: Account creation, redirection to Stripe Checkout, then profile setup.
- **Access Control Middlewares**: `require_coach_or_pending`, `require_active_subscription`, `require_coach_role`.
- **Subscription Page**: Displays pricing, active subscription status, and link to Stripe Customer Portal.
- **API Endpoints**: For creating checkout sessions, customer portal sessions, handling webhooks, and retrieving subscription status.
- **Grandfathered Accounts**: Legacy coach accounts are automatically upgraded to "active" subscription status upon login.

### Subscription Lifecycle & Enforcement
- **Status Lifecycle**: active → past_due (payment fails) → blocked (after 24h grace period) → active (on payment success)
- **Coach Visibility**: Coaches with status "blocked", "cancelled", or "past_due" are hidden from all public pages (search results, gym pages, public profiles)
- **Background Worker**: Runs every 5 minutes checking for coaches with payment failed 24h+ ago and automatically blocks them
- **Email Notifications**:
    - `send_subscription_success_email()` - Sent on checkout.session.completed
    - `send_payment_failed_email()` - Sent on invoice.payment_failed with 24h warning
    - `send_account_blocked_email()` - Sent when coach is blocked after 24h grace period
    - `send_account_restored_email()` - Sent when blocked coach pays and account is restored
- **Webhook Events**: Handles checkout.session.completed, invoice.payment_failed, invoice.payment_succeeded, customer.subscription.deleted, account.updated

### Stripe Connect (Session Payments to Coaches)
- **Business Model**: FitMatch receives 29€/month from coaches. Clients pay sessions directly to coaches' bank accounts.
- **Coach Onboarding**: Coaches connect their bank account via Stripe Connect Standard accounts.
- **Transfer System**: Session payments use `transfer_data` to send funds directly to coach's connected account.
- **Status Tracking**: Database tracks `stripe_connect_account_id`, `charges_enabled`, `payouts_enabled`, `details_submitted`.
- **Payment Mode**: Coaches can enable "required" payment mode only after Connect account is verified.
- **Webhooks**: `account.updated` event syncs Connect status automatically when Stripe validates coach accounts.
- **API Endpoints**:
    - `GET /api/coach/stripe-connect/status` - Get Connect account status
    - `POST /api/coach/stripe-connect/onboard` - Start Stripe Connect onboarding
    - `GET /api/coach/stripe-connect/refresh` - Regenerate expired onboarding link
    - `POST /api/coach/stripe-connect/sync` - Manual sync after returning from Stripe
- **DB Functions**: `update_stripe_connect_status()`, `get_stripe_connect_info()`, `find_coach_by_stripe_connect_account()`
- **Service File**: `stripe_connect_service.py` with `create_connect_account()`, `create_account_link()`, `get_account_status()`, `create_session_payment_checkout()`

### Password Reset System
- **Forgot Password**: Link on login page with modal for email input.
- **Reset Email**: FitMatch-branded email with a secure, expiring reset link.
- **Reset Password Page**: Interface at `/reset-password?token=...` for new password input and validation.
- **Auto-Login**: User automatically logged in after password change.

### Frontend Libraries
- **Tailwind CSS**: Delivered via CDN.

### Python Libraries
- **FastAPI**: Core web framework.
- **Uvicorn**: ASGI server.
- **Jinja2Templates**: Server-side template rendering.
- **Geopy**: Geographic calculations.