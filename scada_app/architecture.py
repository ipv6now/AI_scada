"""
SCADA Application Architecture Design

This document outlines the architecture for a Python-based SCADA system that allows:
- PLC connection configuration
- HMI (Human Machine Interface) design
- PLC data monitoring
- Device start/stop operations

Architecture Overview:

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   HMI Layer     │    │  Core Services   │    │ Communication   │
│                 │    │                  │    │   Layer         │
│  - Main Window  │◄──►│  - Application   │◄──►│  - Modbus       │
│  - HMI Designer │    │  - Data Manager  │    │  - OPC UA       │
│  - Monitoring   │    │  - Event System  │    │  - Siemens Snap7│
│  - Controls     │    │  - Config Mgr    │    │  - Generic PLC  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer                              │
│  - Tag History Storage     - Alarm Log Storage                │
│  - Configuration Storage   - Trend Data                       │
└─────────────────────────────────────────────────────────────────┘

Components:

1. COMMUNICATION LAYER (scada_app.comm):
   - Protocol handlers (Modbus, OPC UA, Siemens, etc.)
   - Connection managers
   - Data polling mechanisms
   - Error handling and reconnection logic

2. CORE LAYER (scada_app.core):
   - Main application controller
   - Data management system
   - Tag definition and mapping
   - Event and alarm system
   - Configuration manager

3. HMI LAYER (scada_app.hmi):
   - Main application window
   - HMI designer interface
   - Real-time data visualization
   - Control panels and buttons
   - Trend and historical data display

4. DATABASE LAYER (scada_app.database):
   - Tag value history storage
   - Alarm and event logging
   - Configuration persistence
   - Trend data management

Dependencies:
- PyQt5/PySide2 for GUI
- pymodbus for Modbus communication
- python-opcua for OPC UA communication
- sqlite3 for local database
- snap7 for Siemens PLC communication (optional)
"""

from enum import Enum


class PLCProtocol(Enum):
    """Supported PLC protocols"""
    MODBUS_TCP = "Modbus TCP"
    MODBUS_RTU = "Modbus RTU"
    OPC_UA = "OPC UA"
    SIEMENS_S7 = "Siemens S7"
    GENERIC = "Generic"


class DataType(Enum):
    """Data types for PLC variables"""
    BOOL = "BOOL"
    INT = "INT"
    DINT = "DINT"
    REAL = "REAL"
    STRING = "STRING"


class TagType(Enum):
    """Types of tags in the SCADA system"""
    PLC = "PLC"          # PLC variable (read/write)
    INTERNAL = "INTERNAL"  # Internal variable (SCADA only)


class AlarmLevel(Enum):
    """Alarm severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    ALARM = "ALARM"
    CRITICAL = "CRITICAL"