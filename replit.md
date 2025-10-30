# Coach Fitness Platform

## Overview
Coach Fitness is a comprehensive fitness coach marketplace platform built with FastAPI and Python, featuring a 3-way matching system (coach ↔ gym ↔ client). It functions as "Uber for fitness coaching" with secure authentication. The platform includes a worldwide gym database, OpenStreetMap integration, country selection, and geographic search capabilities. It offers a modern, motivating client dashboard and extensive search functionalities for coaches and gyms based on location and preferences. The business vision is to connect fitness enthusiasts with qualified coaches and gyms efficiently, leveraging technology to streamline the fitness coaching market.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: FastAPI for high-performance API development with automatic documentation.
- **Template Engine**: Jinja2 for server-side HTML rendering.
- **Static Files**: FastAPI StaticFiles for serving CSS/JS assets.
- **Geographic Services**: Geopy with Nominatim geocoder for location-based searches and custom Haversine formula for distance calculations.
- **Data Layer**: Currently uses in-memory mock data for coaches and transformations, with architecture prepared for Supabase integration.
- **Authentication & Authorization**: Infrastructure for login/signup, role-based access (client, coach), and session management is in place.

### Frontend Architecture
- **Styling**: Tailwind CSS for responsive, utility-first design.
- **Template Structure**: Base template with block inheritance for consistent layout.
- **Forms**: HTML forms with FastAPI form handling.
- **Responsive Design**: Mobile-first approach with grid layouts.
- **UI/UX Decisions**: Modern, minimalist design inspired by Planity, utilizing the Inter font family, clean white backgrounds, subtle borders, and a professional color scheme. Features a motivating client dashboard with progress tracking and achievement badges.

### Feature Specifications
- **Coach Onboarding**: Comprehensive 4-section setup form (basic info with profile photo upload, zone, specialties, gym locations) with profile completion tracking and redirection logic. Includes worldwide gym selection autocomplete via Google Places API. Profile photo upload with live preview, processed via Pillow (original + thumbnail), stored in Supabase Storage or locally in /attached_assets/profile_photos for demo mode.
- **Search & Discovery**:
    - **Homepage Search**: Dual interface for "Adresse/Ville" and "Spécialité" with smart autocomplete for locations.
    - **Coach Cards**: Professional display with photo, name, verified badge, rating, specialties, associated gyms, and pricing.
    - **Gym Cards**: Comprehensive information including photo, name, address, opening hours, and a button to view coaches.
    - **Filtering**: Quick filters for availability ("Aujourd'hui"), distance ("≤ 5 km"), and price ("Prix ≤ 50€").
    - **Sorting**: Options for "Pertinence", "Note", and "Distance".
    - **Logic**: Handles various search combinations (address only, specialty only, address + specialty).
    - **Public Gym Pages**: Allows discovery of coaches by searching gyms via postal codes, even without login.
- **Coach Profile Pages**: Public profile pages accessible via `/coach/{coach_id}` with Planity-style minimalist design (white background, Inter font, clean layout):
    - **Header**: Large profile photo (128px circular), full name with verified badge, rating with review count, city location, and pricing
    - **Sections**: Specialties with emoji badges, biography ("À propos"), gym locations with addresses, Instagram link with gradient button
    - **Navigation**: Back button to return to previous page
    - **Data Sources**: Loads from coaches.json, Supabase profiles, or demo_users with automatic fallback
    - **Responsive Design**: Mobile-friendly layout with proper spacing and typography
- **Client Dashboard**: Redesigned home page with fitness-inspired gradient background, dynamic motivational quotes, visual progress bar, upcoming workout sessions, and badge system.
- **FAQ Section**: Homepage includes a Planity-style FAQ section using native HTML5 `<details>` for accordion functionality.
- **Email Reminder Section**: Added to `/coach-signup` page, featuring an iPhone showing Gmail app with FitMatch reminder email. Image served via /attached_assets directory. Highlights automatic email reminders, instant confirmation, and flexible cancellation policy.
- **Testimonials Section**: Coach testimonials section added to `/coach-signup` page
  - Title: "Ils coachent avec FitMatch"
  - 3 coach testimonial cards: Laura Martin (Fitness Park Maurepas), Anas B. (Basic-Fit Élancourt), Mehdi K. (Fitness Park Trappes)
  - Each card includes: coach photo, name, gym location, 5-star rating, testimonial quote, specialty tags
  - Instagram credibility boost section with SVG icon
  - Responsive grid layout: 3 columns on desktop, 2 on tablet, 1 on mobile
  - Clean, minimal design with soft shadows and rounded corners
  - Images from Unsplash for coach photos
- **FAQ Section**: Added to `/coach-signup` page at the bottom
  - Title: "Les questions fréquentes"
  - 7 questions covering: platform overview, booking process, payment (current & future), session management, coach profile setup, social media integration
  - Native HTML5 `<details>` element for accordion functionality
  - Chevron animation on open/close (CSS-only)
  - JavaScript accordion behavior (auto-close other items when opening one)
  - Planity-style design with clean borders, rounded corners, smooth animations
  - Responsive padding adjustments for mobile
  - Badge "Bientôt" on future payment question

### System Design Choices
- **Modular Data**: JSON-based data layer for gyms and coaches, designed for easy migration to a backend API.
- **URL Parameters**: Shareable search URLs with parameter persistence.
- **Error Handling**: 404 handling for non-existent gyms and various UI states for loading, empty results, and errors.
- **Internationalization**: Support for 249 countries with ISO 3166-1 alpha-2 standardization for gym database.

## External Dependencies

### Third-Party Services
- **Google Places API**: For worldwide gym search, autocomplete, and coach onboarding.
- **Geopy**: Geographic location services using Nominatim geocoder.
- **Supabase**: Planned integration for user authentication and data storage.

### Frontend Libraries
- **Tailwind CSS**: Delivered via CDN for UI development.

### Python Libraries
- **FastAPI**: Core web framework.
- **Uvicorn**: ASGI server.
- **Jinja2Templates**: Server-side template rendering.
- **Geopy**: Geographic calculations.