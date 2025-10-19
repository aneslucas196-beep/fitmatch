# Coach Fitness Platform

## Overview

Coach Fitness is a comprehensive fitness coach marketplace platform built with FastAPI and Python, featuring a complete 3-way matching system (coach ↔ gym ↔ client). The application functions as "Uber for fitness coaching" with secure authentication using custom domain fitmatch.fr.

The platform includes a worldwide gym database with all gyms globally, OpenStreetMap integration, country selection, and geographic search capabilities. It features a modern, motivating client dashboard and comprehensive search functionalities for finding both coaches and gyms based on location and preferences.

## Recent Changes (October 2025)

### Public Gym Pages - Coach Discovery by Location
- **Feature**: Clients can now discover coaches by searching gyms using postal codes (no login required)
- **Complete User Flow**: 
  1. User searches by postal code on homepage (e.g., "78990")
  2. System displays all gyms in that postal code
  3. User clicks "Voir les coachs" on any gym card
  4. Public gym page shows all coaches training at that location
- **New Backend Route**: `GET /gym/{gym_id}` displays gym details + all coaches
  - Gym information: name, address, hours, phone
  - Coach cards sorted by: verified status → rating → review count
  - 404 handling for non-existent gyms with helpful error page
- **Enhanced Homepage Search**:
  - **Postal code only** → Displays gym cards with "Voir les coachs" button
  - **City/address only** → Redirects to /gyms-map (Google Maps view)
  - **Address + Specialty** → Shows filtered coach results
- **Gym Cards on Homepage**:
  - 180px photo with gradient placeholder (🏋️)
  - Gym name + chain affiliation
  - Full address with location icon (📍)
  - Opening hours with clock icon (🕐)
  - "Voir les coachs" CTA button linking to `/gym/{gym_id}`
- **Technical Implementation**:
  - `searchGymsByPostalCode()` function calls `/api/gyms/search?postal_code=X`
  - `createGymCard()` generates responsive gym cards
  - New CSS styles in `search-styles.css` for gym cards (.gym-card, .gym-photo, .gym-info-row)
  - Template `gym_coaches.html` displays gym header + coach grid
- **Data Flow**:
  - Backend loads gym from `static/data/gyms.json`
  - Coaches filtered by gym ID from `static/data/coaches.json`
  - Frontend displays results with proper fallbacks (empty state, 404)
- **Tested & Verified**: 
  - Basic-Fit Élancourt (78990) correctly shows 4 coaches
  - Fitness Park Maurepas (78310) correctly shows 2 coaches

### Coach Profile Data Persistence Fix - Critical Bug Resolution
- **Bug Fixed**: Coach profile data now persists correctly when returning to edit profile
- **Issue**: Previously, when coaches filled their profile and clicked "Finaliser mon profil", data was saved. However, when returning via "Gérer mon profil", all entered data (including gyms and specialties) disappeared
- **Solution Implemented**:
  - Backend now loads saved coach data in demo mode when returning to profile setup page
  - Specialties are properly saved and restored from user profile
  - Gym selections now stored with complete details (name, address, coordinates) in `selected_gyms_data` JSON field
  - JavaScript pre-loads saved gyms and specialties on page load
  - All profile fields (basic info, specialties, gyms, radius) now persist across sessions
- **Technical Changes**:
  - Added `selected_gyms_data` field to store complete gym objects (not just IDs)
  - Modified GET `/coach/profile-setup` to return existing profile data in demo mode
  - Enhanced JavaScript to parse and display saved gyms from JSON storage
  - Profile data now includes: full_name, bio, city, instagram_url, price_from, radius_km, specialties, selected_gyms_data

## Recent Changes (October 2025)

### Homepage Search System - Location & Specialty Discovery
- **Dual Search Interface**: Homepage now features two specialized search fields
  - "Adresse/Ville" field: Search coaches by city or postal code
  - "Quelle spécialité" dropdown: Filter coaches by training activity (musculation, boxe, MMA, yoga, etc.)
- **Smart Autocomplete**: Real-time location suggestions with 300ms debounce
  - City suggestions (🏙️ icon)
  - Postal code suggestions (🏷️ icon)
  - Minimum 2 characters to trigger, max 10 suggestions
- **Specialty Selection**: 16 pre-defined sports activities available
  - 💪 Musculation, 🥊 Boxe, 🥋 MMA, 🏋️ CrossFit
  - 🧘 Yoga, 🤸 Pilates, ❤️ Cardio, ⚡ HIIT
  - 🏊 Natation, 🏃 Fitness, ⚽ Préparation physique
  - 🥋 Sport de combat, 🤸 Stretching, 💪 Functional Training
  - 📉 Perte de poids, 🥗 Nutrition
- **Coach Cards Display**: Professional coach cards with complete information
  - 64px circular profile photo
  - Coach name with verified badge (✓) for certified coaches
  - Star rating (⭐) with review count
  - Specialty badges (max 3 displayed: musculation, cardio, yoga, etc.)
  - Associated gyms (max 2 shown + "+X" for additional)
  - Price per session with "Voir profil" button
- **Gym Cards Display**: Comprehensive gym information cards
  - Gym photo with gradient placeholder
  - Gym name and chain affiliation
  - Full address with 📍 icon
  - Opening hours with 🕐 icon
  - "Voir les coachs" button to view trainers at that gym
- **Advanced Filtering**: Three quick-filter buttons above results
  - "Aujourd'hui" - Show only coaches available today
  - "≤ 5 km" - Filter coaches within 5km radius
  - "Prix ≤ 50€" - Show coaches with sessions ≤50€
- **Multi-Criteria Sorting**: Sort selector with three options
  - "Pertinence" - Verified status > Rating > Review count (default)
  - "Note" - Pure rating-based sorting with review count tie-breaker
  - "Distance" - Geographic proximity using Haversine calculation
- **Search Logic**:
  - **Adresse seule** → Redirects to /gyms-map showing all gyms on Google Maps
  - **Spécialité seule** → Shows all coaches with that specialty
  - **Adresse + Spécialité** → Shows coaches in that area with that specialty
- **UI States Management**:
  - Skeleton loading state (6 animated placeholder cards)
  - Empty state with "Aucun résultat" message and retry options
  - Error state with retry button
  - Results grid with responsive layout
- **URL Parameter Support**: Shareable search URLs
  - `?city=Elancourt` - Search by city name
  - `?cp=78990` - Search by postal code
  - `?salle=basic-fit-elancourt` - Search by gym
  - Parameters persist on page reload
- **Data Structure**: Modular JSON-based data layer
  - `static/data/gyms.json` - 8 test gyms with full details
  - `static/data/coaches.json` - 8 test coaches with ratings, specialties, gym associations
  - `static/search-service.js` - Reusable search service with filtering, sorting, distance calculation
  - `static/search-app.js` - Main application logic with autocomplete, state management
  - Easy migration path to backend API (drop-in replacement architecture)

### Google Places API - Worldwide Gym Search
- **Global Gym Search**: Integration of Google Places API for worldwide gym discovery
- **New API Endpoint**: `/api/gyms/worldwide-search` for international gym autocomplete
- **Coach Onboarding Enhancement**: Coaches can now add any gym in the world to their profile (not just French gyms)
- **Text Search Integration**: Uses Google Places Text Search API for flexible query matching
- **Updated Coach Profile Setup**: Modified autocomplete to search globally with 3-character minimum
- **API Key Management**: Configured `GOOGLE_PLACES_API_KEY` for secure access to Google services
- **Flexible Radius Options**: Users can now search gyms with 5km, 10km, 25km, or 50km radius
- **Coach Intervention Radius**: Coaches can set their service area from 5km to 100km

## Recent Changes (September 2025)

### Client Dashboard Transformation
- **Modern Design**: Completely redesigned client home page with fitness-inspired gradient background
- **Motivational Elements**: Dynamic welcome message with rotating motivational quotes every 10 seconds
- **Progress Tracking**: Visual progress bar showing goal achievement (e.g., 60% progress toward 5kg weight loss)
- **Training Schedule**: Upcoming workout sessions with dates, times, and gym locations
- **Badge System**: Achievement badges with unlocked (✅) and locked (🔒) states
- **Action Buttons**: Prominent buttons for "Find a gym" and "Discover coaches" with hover animations

### Coach Onboarding System Implementation
- **Complete Onboarding Flow**: First-time coach users are automatically redirected to profile setup
- **Profile Completion Tracking**: Database field `profile_completed` tracks onboarding status
- **4-Section Setup Form**: Comprehensive profile configuration (basic info, zone, specialties, gym locations)
- **Gym Selection Autocomplete**: Real-time search across 5710+ French gyms via Data ES API
- **Redirect Logic**: Incomplete profiles automatically redirect to onboarding, completed profiles access dashboard
- **Profile Management**: "Gérer mon profil" button allows coaches to update their information anytime
- **Database Migration**: Persistent SQL migration ensures profile_completed field exists in all environments

### Worldwide Gym Database Implementation
- **Complete Database**: Supabase gyms table with geographic indexing and search capabilities
- **Global Coverage**: Support for 249 countries with ISO 3166-1 alpha-2 standardization  
- **Geographic Search**: Haversine distance calculations with radius filtering up to 100km
- **API Endpoints**: /api/gyms/countries, /api/gyms/worldwide (paginated), /api/gyms/near (geographic)
- **Search Interface**: Dedicated gym search page with OpenStreetMap geocoding integration

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: FastAPI for high-performance API development with automatic documentation
- **Template Engine**: Jinja2 for server-side HTML rendering
- **Static Files**: FastAPI StaticFiles for serving CSS/JS assets
- **Geographic Services**: Geopy with Nominatim geocoder for location-based searches
- **Distance Calculations**: Custom Haversine formula implementation for accurate geographic distance measurement

### Frontend Architecture
- **Styling**: Tailwind CSS for responsive, utility-first design
- **Template Structure**: Base template with block inheritance for consistent layout
- **Forms**: HTML forms with FastAPI form handling for user interactions
- **Responsive Design**: Mobile-first approach with grid layouts

### Data Architecture
- **Mock Data Layer**: Currently uses in-memory mock data for coaches and transformations
- **Prepared for Database**: Architecture ready for Supabase integration (referenced but not yet implemented)
- **Geographic Data**: Latitude/longitude coordinate storage for location-based queries

### Authentication & Authorization
- **Prepared Infrastructure**: Login/signup forms and routes planned
- **Role-Based Access**: Client and coach user roles defined
- **Session Management**: Framework in place for user authentication (not yet implemented)

### Search & Discovery System
- **Geographic Search**: City/postal code geocoding with configurable radius filtering
- **Specialty Filtering**: Coach specialization-based search (musculation, cardio, yoga, etc.)
- **Distance Ranking**: Results sorted by proximity to user location
- **Profile Management**: Coach portal for profile and transformation management

### Content Management
- **Coach Profiles**: Comprehensive coach information including bio, specialties, pricing, and social links
- **Transformation Showcase**: System for coaches to display client transformation results
- **Search Results**: Paginated, filterable coach listings with distance information

## External Dependencies

### Third-Party Services
- **Geopy**: Geographic location services using Nominatim geocoder for address-to-coordinate conversion
- **Supabase**: Planned backend-as-a-service for user authentication and data storage (configured but not yet implemented)

### Frontend Dependencies
- **Tailwind CSS**: Delivered via CDN for rapid UI development and responsive design

### Python Libraries
- **FastAPI**: Core web framework with built-in validation and documentation
- **Uvicorn**: ASGI server for FastAPI application deployment
- **Jinja2Templates**: Server-side template rendering
- **Geopy**: Geographic calculations and geocoding services

### Development Tools
- **Mock Data System**: Temporary data layer for development and testing before database integration
- **Form Handling**: FastAPI's built-in form processing capabilities
- **Static File Serving**: FastAPI's StaticFiles for asset delivery