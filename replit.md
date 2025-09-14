# Coach Fitness Platform

## Overview

Coach Fitness is a location-based fitness coach discovery platform built with FastAPI and Python. The application enables users to search for fitness coaches in their area based on specialties, location, and distance radius. It features a dual-sided marketplace where clients can find coaches and coaches can manage their profiles and showcase transformation results.

The platform uses geographic search capabilities with Haversine distance calculations to match users with nearby coaches, providing a personalized fitness coaching discovery experience.

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