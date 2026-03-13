# Python SCADA Application

A comprehensive Supervisory Control and Data Acquisition (SCADA) system developed in Python with PyQt for industrial automation applications.

## Version

**Current Version: 1.7**

## Features

- **PLC Connectivity**: Support for multiple PLC protocols (Modbus TCP/RTU, OPC UA, Simulated PLC)
- **HMI Designer**: Visual interface designer for creating human-machine interfaces
- **Real-time Monitoring**: Live data monitoring with configurable update intervals
- **Device Control**: Start/stop operations for motors, pumps, valves and other equipment
- **Data Management**: Tag-based data storage with historical trending
- **Variable Binding**: Connect HMI objects to PLC variables

## Architecture

The application follows a modular architecture:

- **Communication Layer** (`scada_app.comm`): Handles PLC connections and protocol implementations
- **Core Layer** (`scada_app.core`): Contains main application logic and data management
- **HMI Layer** (`scada_app.hmi`): Handles visualization and user interaction
- **Database Layer** (`scada_app.database`): Handles data storage and retrieval

## Installation

1. Clone or download the project
2. Install required dependencies:
   ```
   pip install PyQt5 pymodbus python-opcua
   ```

## Usage

Run the application:
```
python run_scada.py
```

Or directly:
```
python -c "from scada_app.hmi.main_window import main; main()"
```

## Key Components

### Main Window
- File menu for project management
- PLC menu for connection management
- HMI menu for interface design
- Real-time monitoring and control tabs
- Dockable panels for PLC connections and tags

### HMI Designer
- Drag-and-drop interface design
- Support for buttons, labels, gauges
- Variable binding to PLC tags
- Action configuration (start/stop/open/close)
- Property customization

### PLC Connection Manager
- Configure multiple PLC connections
- Support for different protocols
- Connection status monitoring
- Tag mapping

### Data Monitor
- Real-time tag value display
- Quality and timestamp indicators
- Historical data visualization

## Development

The application is designed to be extensible:
- Add new PLC protocol handlers
- Extend HMI object types
- Integrate with different databases
- Add new visualization components

## Version History

### Version 1.7
- Fixed screen switching issues with control crossover display
- Resolved "QGraphicsScene::addItem: item has already been added to this scene" warnings
- Added query mode for alarm history to prevent automatic refresh overwriting query results
- Added "Exit Query" button to manually exit query mode
- Fixed "alarm state object has no attribute get" error during alarm queries
- Added exception handling for alarm query operations to prevent crashes
- Improved graphics item tracking for all runtime widgets (Clock, Button, Switch, Light, Gauge)
- Fixed duplicate graphics item addition in button widgets

### Version 1.6
- Added alarm type management with configurable colors
- Implemented alarm buffer for storing alarm history
- Added alarm display widget with current/buffer/history modes
- Added alarm query functionality with time range and ID-based filtering

## Testing

Run component tests:
```
python test_components.py
```

The application includes a simulated PLC for testing without physical hardware.