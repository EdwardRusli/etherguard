# WiFi CSI Fall Detection Web Dashboard

Real-time monitoring dashboard for the WiFi CSI-based fall detection system.

## Features
- Real-time CSI data visualization
- Fall detection alerts
- Historical event log
- System status monitoring
- Activity classification display

## Setup
```bash
npm install
npm run dev
```

## API Endpoints
- GET /api/status - System status
- GET /api/detections - Detection history
- POST /api/config - Update configuration
- WebSocket /ws - Real-time updates
