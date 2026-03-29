# AutoCare ONE - Agentic AI Predictive Maintenance System

A Flutter prototype app for intelligent vehicle maintenance with predictive diagnostics, autonomous scheduling, RCA/CAPA insights, voice engagement, and UEBA-based safety.

## Features

### 🟥 Dashboard Screen
- **Red Alert Box**: Critical issue detection with blinking animation
- **Live Telemetry KPIs**: Speed, RPM, DTC Count, Coolant, Intake, Load, GPS Fix, Satellites
- **Real-time Charts**: Speed, RPM, and temperature visualizations
- **Vehicle Route Map**: GPS tracking with risk-colored segments
- **Event Timeline**: Misfire patterns, temperature spikes, vibration anomalies
- **UEBA Status**: Agent security monitoring

### 🟦 Sidebar
- **Stop/Start Agent Toggle**: Control Agentic AI system
- **Logout**: User authentication

### 🟧 Service Screen
- **Last Service Card**: Previous maintenance summary
- **Recommended Service Center**: Distance, load, and risk-based recommendations
- **Auto-Booking Card**: Transparent auto-booking with cancellation countdown
- **Smart Scheduler**: Calendar, time slots, pickup/drop service
- **Booking History**: Timeline of appointments
- **Emergency Service**: Unsafe-to-drive event handling

### 🟩 Voice Agent Screen
- **Conversational Interface**: Voice and text input
- **Persuasive AI**: Human-like conversations with safety recommendations
- **Post-Service Feedback**: Star rating, comments, voice feedback

### 🟥 Profile & RCA Screen
- **Vehicle Profile**: Owner, model, VIN, warranty, odometer, last service
- **Active Issues**: Expandable cards with detailed RCA
- **RCA (Root Cause Analysis)**:
  - Root cause summary
  - Evidence (DTC codes, sensor correlations, telemetry)
  - Confidence scores
- **CAPA (Corrective & Preventive Actions)**:
  - Corrective actions
  - Preventive actions
- **Manufacturing Insights**: Feedback loop to manufacturing team
- **UEBA Security Layer**: Agent action monitoring and blocking

## Setup Instructions

1. **Install Flutter dependencies:**
   ```bash
   flutter pub get
   ```

2. **Run the app:**
   ```bash
   flutter run
   ```

## Dependencies

- `provider`: State management
- `fl_chart`: Charts and graphs
- `google_maps_flutter`: Map integration (optional for prototype)
- `lottie`: Animations (optional for prototype)
- `flutter_animate`: Animation utilities
- `intl`: Internationalization and date formatting

## Architecture

- **Master-Worker Agentic Architecture**: Master Agent orchestrates Worker Agents
- **Worker Agents**:
  - Data Analysis Agent
  - Diagnosis Agent
  - Customer Engagement Agent
  - Scheduling Agent
  - Feedback Agent
  - Manufacturing Insights Agent
- **UEBA**: User and Entity Behavior Analytics for agent security

## Notes

- This is a **prototype** with hardcoded data
- Visual design prioritized over perfect implementation
- All telemetry data is simulated
- Maps use placeholder UI (can be integrated with Google Maps API)

## Screenshots

The app includes 4 main screens accessible via bottom navigation:
1. Dashboard - Real-time monitoring
2. Service - Auto-booking and scheduling
3. Voice Agent - Conversational AI
4. Profile & RCA - Root cause analysis and insights
"# AutoCareOne" 
