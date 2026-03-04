"""
PLC Connection Configuration Dialog
Allows users to configure PLC connections
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QPushButton, QLineEdit, QComboBox, QLabel, 
                             QDialogButtonBox, QGroupBox, QSpinBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox)
from PyQt5.QtCore import Qt
from .plc_manager import PLCProtocol
import serial.tools.list_ports


def get_available_serial_ports():
    """Get list of available serial ports on the system"""
    try:
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    except Exception as e:
        print(f"Error getting serial ports: {e}")
        return []


class ConnectionConfigDialog(QDialog):
    def __init__(self, parent=None, connection_data=None):
        super().__init__(parent)
        self.connection_data = connection_data or {}
        self.setWindowTitle("Configure PLC Connection")
        self.setGeometry(300, 300, 400, 350)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Protocol selection
        protocol_group = QGroupBox("Protocol Settings")
        protocol_layout = QFormLayout()
        
        self.protocol_combo = QComboBox()
        available_protocols = [protocol.value for protocol in PLCProtocol if protocol.value != 'Simulated']
        self.protocol_combo.addItems(available_protocols)
        protocol_layout.addRow("Protocol:", self.protocol_combo)
        
        # Connection details
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.connection_data.get('name', ''))
        protocol_layout.addRow("Connection Name:", self.name_edit)
        
        # IP Address / Serial Port field
        self.address_edit = QLineEdit()
        self.address_edit.setText(self.connection_data.get('address', 'localhost'))
        self.address_label = QLabel("IP Address:")
        protocol_layout.addRow(self.address_label, self.address_edit)
        
        # Serial Port selection combo (for Modbus RTU)
        self.serial_port_combo = QComboBox()
        self.serial_port_combo.setEditable(True)  # Allow manual entry
        available_ports = get_available_serial_ports()
        if available_ports:
            self.serial_port_combo.addItems(available_ports)
        else:
            # Add common default ports if none detected
            import sys
            if sys.platform.startswith('win'):
                self.serial_port_combo.addItems(['COM1', 'COM2', 'COM3', 'COM4', 'COM5'])
            else:
                self.serial_port_combo.addItems(['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyS0'])
        # Set current value if exists
        current_address = self.connection_data.get('address', '')
        if current_address:
            idx = self.serial_port_combo.findText(current_address)
            if idx >= 0:
                self.serial_port_combo.setCurrentIndex(idx)
            else:
                self.serial_port_combo.setCurrentText(current_address)
        self.serial_port_label = QLabel("Serial Port:")
        protocol_layout.addRow(self.serial_port_label, self.serial_port_combo)
        
        # Port field
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self.connection_data.get('port', 502))
        self.port_label = QLabel("Port:")
        protocol_layout.addRow(self.port_label, self.port_spin)
        
        # Slave ID field
        self.slave_id_spin = QSpinBox()
        self.slave_id_spin.setRange(0, 255)
        self.slave_id_spin.setValue(self.connection_data.get('slave_id', 1))
        self.slave_id_label = QLabel("Slave ID:")
        protocol_layout.addRow(self.slave_id_label, self.slave_id_spin)
        
        # S7 specific fields
        self.rack_spin = QSpinBox()
        self.rack_spin.setRange(0, 255)
        self.rack_spin.setValue(self.connection_data.get('rack', 0))
        self.rack_label = QLabel("Rack:")
        protocol_layout.addRow(self.rack_label, self.rack_spin)
        
        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(0, 255)
        self.slot_spin.setValue(self.connection_data.get('slot', 1))
        self.slot_label = QLabel("Slot:")
        protocol_layout.addRow(self.slot_label, self.slot_spin)
        
        # Modbus RTU specific fields
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200'])
        self.baudrate_combo.setCurrentText(str(self.connection_data.get('baudrate', 9600)))
        self.baudrate_label = QLabel("Baud Rate:")
        protocol_layout.addRow(self.baudrate_label, self.baudrate_combo)
        
        self.databits_combo = QComboBox()
        self.databits_combo.addItems(['7', '8'])
        self.databits_combo.setCurrentText(str(self.connection_data.get('databits', 8)))
        self.databits_label = QLabel("Data Bits:")
        protocol_layout.addRow(self.databits_label, self.databits_combo)
        
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(['None', 'Even', 'Odd'])
        parity_map = {'N': 'None', 'E': 'Even', 'O': 'Odd'}
        current_parity = self.connection_data.get('parity', 'N')
        self.parity_combo.setCurrentText(parity_map.get(current_parity, 'None'))
        self.parity_label = QLabel("Parity:")
        protocol_layout.addRow(self.parity_label, self.parity_combo)
        
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(['1', '2'])
        self.stopbits_combo.setCurrentText(str(self.connection_data.get('stopbits', 1)))
        self.stopbits_label = QLabel("Stop Bits:")
        protocol_layout.addRow(self.stopbits_label, self.stopbits_combo)
        
        # Initially hide S7-specific and RTU-specific fields
        self.rack_label.setVisible(False)
        self.rack_spin.setVisible(False)
        self.slot_label.setVisible(False)
        self.slot_spin.setVisible(False)
        self.baudrate_label.setVisible(False)
        self.baudrate_combo.setVisible(False)
        self.databits_label.setVisible(False)
        self.databits_combo.setVisible(False)
        self.parity_label.setVisible(False)
        self.parity_combo.setVisible(False)
        self.stopbits_label.setVisible(False)
        self.stopbits_combo.setVisible(False)
        # Initially hide serial port combo, show address edit
        self.serial_port_label.setVisible(False)
        self.serial_port_combo.setVisible(False)
        
        protocol_group.setLayout(protocol_layout)
        layout.addWidget(protocol_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        self.setLayout(layout)
        
        # Set up event handlers first
        self.protocol_combo.currentTextChanged.connect(self.on_protocol_changed)
        
        # Set the protocol in the combo box
        protocol_val = self.connection_data.get('protocol', 'Modbus TCP')
        idx = self.protocol_combo.findText(protocol_val)
        if idx >= 0:
            self.protocol_combo.setCurrentIndex(idx)
            # Manually trigger the protocol change handler after setting the value
            self.on_protocol_changed(protocol_val)
        else:
            # If protocol not found, use the first available and call handler
            if self.protocol_combo.count() > 0:
                default_protocol = self.protocol_combo.itemText(0)
                self.on_protocol_changed(default_protocol)
        
    def on_protocol_changed(self, protocol):
        """Handle protocol change"""
        # Adjust UI based on protocol
        if protocol == 'Modbus TCP':
            # Modbus TCP needs IP address, port, and slave ID
            self.address_label.setText("IP Address:")
            self.address_label.setVisible(True)
            self.address_edit.setVisible(True)
            self.serial_port_label.setVisible(False)
            self.serial_port_combo.setVisible(False)
            self.port_label.setVisible(True)
            self.port_spin.setVisible(True)
            self.slave_id_label.setVisible(True)
            self.slave_id_spin.setVisible(True)
            # Hide S7-specific and RTU-specific fields
            self.rack_label.setVisible(False)
            self.rack_spin.setVisible(False)
            self.slot_label.setVisible(False)
            self.slot_spin.setVisible(False)
            self.baudrate_label.setVisible(False)
            self.baudrate_combo.setVisible(False)
            self.databits_label.setVisible(False)
            self.databits_combo.setVisible(False)
            self.parity_label.setVisible(False)
            self.parity_combo.setVisible(False)
            self.stopbits_label.setVisible(False)
            self.stopbits_combo.setVisible(False)
        elif protocol == 'Modbus RTU':
            # Modbus RTU needs serial port, slave ID, and serial parameters
            self.address_label.setText("Serial Port:")
            self.address_label.setVisible(False)  # Hide the label, use serial_port_label instead
            self.address_edit.setVisible(False)   # Hide the edit, use serial_port_combo instead
            self.serial_port_label.setVisible(True)
            self.serial_port_combo.setVisible(True)
            # Refresh available ports when showing
            self.refresh_serial_ports()
            self.port_label.setVisible(False)
            self.port_spin.setVisible(False)
            self.slave_id_label.setVisible(True)
            self.slave_id_spin.setVisible(True)
            # Hide S7-specific fields
            self.rack_label.setVisible(False)
            self.rack_spin.setVisible(False)
            self.slot_label.setVisible(False)
            self.slot_spin.setVisible(False)
            # Show RTU-specific fields
            self.baudrate_label.setVisible(True)
            self.baudrate_combo.setVisible(True)
            self.databits_label.setVisible(True)
            self.databits_combo.setVisible(True)
            self.parity_label.setVisible(True)
            self.parity_combo.setVisible(True)
            self.stopbits_label.setVisible(True)
            self.stopbits_combo.setVisible(True)
        elif protocol == 'OPC UA':
            # OPC UA needs IP address and port
            self.address_label.setVisible(True)
            self.address_edit.setVisible(True)
            self.port_label.setVisible(True)
            self.port_spin.setVisible(True)
            self.slave_id_label.setVisible(False)
            self.slave_id_spin.setVisible(False)
            # Hide S7-specific and RTU-specific fields
            self.rack_label.setVisible(False)
            self.rack_spin.setVisible(False)
            self.slot_label.setVisible(False)
            self.slot_spin.setVisible(False)
            self.baudrate_label.setVisible(False)
            self.baudrate_combo.setVisible(False)
            self.databits_label.setVisible(False)
            self.databits_combo.setVisible(False)
            self.parity_label.setVisible(False)
            self.parity_combo.setVisible(False)
            self.stopbits_label.setVisible(False)
            self.stopbits_combo.setVisible(False)
            # Hide serial port combo
            self.serial_port_label.setVisible(False)
            self.serial_port_combo.setVisible(False)
        elif protocol == 'Siemens S7':
            # S7 needs IP address, port, rack, and slot (no slave ID)
            self.address_label.setText("IP Address:")
            self.address_label.setVisible(True)
            self.address_edit.setVisible(True)
            self.serial_port_label.setVisible(False)
            self.serial_port_combo.setVisible(False)
            self.port_label.setVisible(True)
            self.port_spin.setVisible(True)
            self.slave_id_label.setVisible(False)
            self.slave_id_spin.setVisible(False)
            # Show S7-specific fields
            self.rack_label.setVisible(True)
            self.rack_spin.setVisible(True)
            self.slot_label.setVisible(True)
            self.slot_spin.setVisible(True)
            # Hide RTU-specific fields
            self.baudrate_label.setVisible(False)
            self.baudrate_combo.setVisible(False)
            self.databits_label.setVisible(False)
            self.databits_combo.setVisible(False)
            self.parity_label.setVisible(False)
            self.parity_combo.setVisible(False)
            self.stopbits_label.setVisible(False)
            self.stopbits_combo.setVisible(False)
        else:
            # Generic/default - show IP, port, slave ID
            self.address_label.setText("IP Address:")
            self.address_label.setVisible(True)
            self.address_edit.setVisible(True)
            self.serial_port_label.setVisible(False)
            self.serial_port_combo.setVisible(False)
            self.port_label.setVisible(True)
            self.port_spin.setVisible(True)
            self.slave_id_label.setVisible(True)
            self.slave_id_spin.setVisible(True)
            # Hide S7-specific and RTU-specific fields
            self.rack_label.setVisible(False)
            self.rack_spin.setVisible(False)
            self.slot_label.setVisible(False)
            self.slot_spin.setVisible(False)
            self.baudrate_label.setVisible(False)
            self.baudrate_combo.setVisible(False)
            self.databits_label.setVisible(False)
            self.databits_combo.setVisible(False)
            self.parity_label.setVisible(False)
            self.parity_combo.setVisible(False)
            self.stopbits_label.setVisible(False)
            self.stopbits_combo.setVisible(False)
    
    def refresh_serial_ports(self):
        """Refresh the list of available serial ports"""
        current_text = self.serial_port_combo.currentText()
        self.serial_port_combo.clear()
        available_ports = get_available_serial_ports()
        if available_ports:
            self.serial_port_combo.addItems(available_ports)
        else:
            # Add common default ports if none detected
            import sys
            if sys.platform.startswith('win'):
                self.serial_port_combo.addItems(['COM1', 'COM2', 'COM3', 'COM4', 'COM5'])
            else:
                self.serial_port_combo.addItems(['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyS0'])
        # Restore previous selection if still available
        idx = self.serial_port_combo.findText(current_text)
        if idx >= 0:
            self.serial_port_combo.setCurrentIndex(idx)
        else:
            self.serial_port_combo.setCurrentText(current_text)
            
    def get_connection_data(self):
        """Get the connection configuration data"""
        protocol = self.protocol_combo.currentText()
        
        # Get address based on protocol
        if protocol == 'Modbus RTU':
            address = self.serial_port_combo.currentText()
        else:
            address = self.address_edit.text()
        
        data = {
            'name': self.name_edit.text(),
            'protocol': protocol,
            'address': address,
            'port': self.port_spin.value()
        }
        
        # Add protocol-specific parameters
        if protocol == 'Modbus TCP':
            data['slave_id'] = self.slave_id_spin.value()
        elif protocol == 'Modbus RTU':
            data['slave_id'] = self.slave_id_spin.value()
            # RTU serial parameters
            data['baudrate'] = int(self.baudrate_combo.currentText())
            data['databits'] = int(self.databits_combo.currentText())
            parity_map = {'None': 'N', 'Even': 'E', 'Odd': 'O'}
            data['parity'] = parity_map.get(self.parity_combo.currentText(), 'N')
            data['stopbits'] = int(self.stopbits_combo.currentText())
        elif protocol == 'Siemens S7':
            data['rack'] = self.rack_spin.value()
            data['slot'] = self.slot_spin.value()
        elif protocol == 'OPC UA':
            # OPC UA doesn't need additional parameters in this implementation
            pass
        else:
            # Generic/default
            data['slave_id'] = self.slave_id_spin.value()
        
        return data


class ConnectionManagerDialog(QDialog):
    def __init__(self, parent=None, plc_manager=None):
        super().__init__(parent)
        self.plc_manager = plc_manager
        self.setWindowTitle("PLC Connection Manager")
        self.setGeometry(200, 200, 800, 500)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("PLC Connection Configuration")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Connection table
        self.connection_table = QTableWidget()
        self.connection_table.setColumnCount(5)
        self.connection_table.setHorizontalHeaderLabels(["Name", "Protocol", "Address", "Port", "Status"])
        header = self.connection_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(QLabel("Configured Connections:"))
        layout.addWidget(self.connection_table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("Add Connection")
        self.add_btn.clicked.connect(self.add_connection)
        btn_layout.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("Edit Connection")
        self.edit_btn.clicked.connect(self.edit_connection)
        btn_layout.addWidget(self.edit_btn)
        
        self.remove_btn = QPushButton("Remove Connection")
        self.remove_btn.clicked.connect(self.remove_connection)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addLayout(btn_layout)
        
        # Connect/disconnect buttons
        connect_layout = QHBoxLayout()
        
        self.connect_all_btn = QPushButton("Connect All")
        self.connect_all_btn.clicked.connect(self.connect_all)
        connect_layout.addWidget(self.connect_all_btn)
        
        self.disconnect_all_btn = QPushButton("Disconnect All")
        self.disconnect_all_btn.clicked.connect(self.disconnect_all)
        connect_layout.addWidget(self.disconnect_all_btn)
        
        layout.addLayout(connect_layout)
        
        # OK/Cancel
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        self.setLayout(layout)
        
        # Load existing connections
        self.load_connections()
        
    def load_connections(self):
        """Load existing connections into the table"""
        self.connection_table.setRowCount(0)  # Clear existing rows
        
        if self.plc_manager:
            row = 0
            for name, conn in self.plc_manager.connections.items():
                self.connection_table.insertRow(row)
                
                # Name
                name_item = QTableWidgetItem(conn.name)
                self.connection_table.setItem(row, 0, name_item)
                
                # Protocol - make it editable
                protocol_item = QTableWidgetItem(conn.protocol.value)
                self.connection_table.setItem(row, 1, protocol_item)
                
                # Address - make it editable
                address_item = QTableWidgetItem(conn.address)
                self.connection_table.setItem(row, 2, address_item)
                
                # Port - make it editable
                port_item = QTableWidgetItem(str(conn.port))
                self.connection_table.setItem(row, 3, port_item)
                
                # Status
                status = "Connected" if conn.connected else "Disconnected"
                
                # Store extra parameters in the item's data
                status_item = QTableWidgetItem(status)
                status_item.setData(Qt.UserRole, conn.extra_params)
                self.connection_table.setItem(row, 4, status_item)
                
                row += 1
                
    def add_connection(self):
        """Add a new connection"""
        dialog = ConnectionConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_connection_data()
            
            from .plc_manager import PLCConnection, PLCProtocol
            try:
                protocol_enum = PLCProtocol(data['protocol'])
                # Handle additional parameters for specific protocols
                extra_params = {}
                if protocol_enum == PLCProtocol.SIEMENS_S7:
                    extra_params['rack'] = data.get('rack', 0)
                    extra_params['slot'] = data.get('slot', 1)
                    
                new_conn = PLCConnection(
                    name=data['name'],
                    protocol=protocol_enum,
                    address=data['address'],
                    port=data['port'],
                    slave_id=data.get('slave_id', 1),
                    extra_params=extra_params
                )
                
                # Add protocol-specific parameters to extra_params
                if protocol_enum == PLCProtocol.SIEMENS_S7:
                    new_conn.extra_params['rack'] = data.get('rack', 0)
                    new_conn.extra_params['slot'] = data.get('slot', 1)
                
                if self.plc_manager:
                    # Check if name already exists
                    if data['name'] in self.plc_manager.connections:
                        QMessageBox.warning(self, "Duplicate Name", 
                                          f"A connection with name '{data['name']}' already exists.")
                        return
                        
                    self.plc_manager.add_connection(new_conn)
                    
                self.load_connections()
            except ValueError:
                QMessageBox.critical(self, "Invalid Protocol", 
                                   f"The protocol '{data['protocol']}' is not valid.")
                
    def edit_connection(self):
        """Edit selected connection"""
        current_row = self.connection_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "No Selection", "Please select a connection to edit.")
            return
            
        # Get the current values from the table
        name_item = self.connection_table.item(current_row, 0)
        protocol_item = self.connection_table.item(current_row, 1)
        address_item = self.connection_table.item(current_row, 2)
        port_item = self.connection_table.item(current_row, 3)
        
        if not all([name_item, protocol_item, address_item, port_item]):
            return
            
        conn_name = name_item.text()
        
        if self.plc_manager and conn_name in self.plc_manager.connections:
            # Get the current connection
            current_conn = self.plc_manager.connections[conn_name]
            
            # Create connection data for dialog
            conn_data = {
                'name': current_conn.name,
                'protocol': current_conn.protocol.value,
                'address': current_conn.address,
                'port': current_conn.port,
                'slave_id': getattr(current_conn, 'slave_id', 1)  # Handle if not present
            }
            
            dialog = ConnectionConfigDialog(self, conn_data)
            if dialog.exec_() == QDialog.Accepted:
                # Get updated data
                new_data = dialog.get_connection_data()
                
                try:
                    # Create updated connection
                    from .plc_manager import PLCConnection, PLCProtocol
                    # Handle additional parameters for specific protocols
                    extra_params = {}
                    if PLCProtocol(new_data['protocol']) == PLCProtocol.SIEMENS_S7:
                        extra_params['rack'] = new_data.get('rack', 0)
                        extra_params['slot'] = new_data.get('slot', 1)
                    
                    updated_conn = PLCConnection(
                        name=new_data['name'],
                        protocol=PLCProtocol(new_data['protocol']),
                        address=new_data['address'],
                        port=new_data['port'],
                        slave_id=new_data.get('slave_id', 1),
                        extra_params=extra_params
                    )
                    
                    # Replace in plc manager
                    if self.plc_manager:
                        self.plc_manager.remove_connection(conn_name)
                        self.plc_manager.add_connection(updated_conn)
                        
                    self.load_connections()
                except ValueError:
                    QMessageBox.critical(self, "Invalid Protocol", 
                                       f"The protocol '{new_data['protocol']}' is not valid.")
        else:
            QMessageBox.information(self, "Connection Not Found", 
                                  f"Connection '{conn_name}' not found in manager.")
                
    def remove_connection(self):
        """Remove selected connection"""
        current_row = self.connection_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "No Selection", "Please select a connection to remove.")
            return
            
        name_item = self.connection_table.item(current_row, 0)
        if name_item:
            conn_name = name_item.text()
            
            # Confirm deletion
            reply = QMessageBox.question(self, "Confirm Deletion", 
                                      f"Are you sure you want to remove connection '{conn_name}'?",
                                      QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                if self.plc_manager:
                    self.plc_manager.remove_connection(conn_name)
                    self.load_connections()
            
    def connect_all(self):
        """Connect to all configured PLCs"""
        if self.plc_manager:
            self.plc_manager.connect_all()
            self.load_connections()
            QMessageBox.information(self, "Connection Status", "All configured PLCs connected.")
            
    def disconnect_all(self):
        """Disconnect from all PLCs"""
        if self.plc_manager:
            self.plc_manager.disconnect_all()
            self.load_connections()
            QMessageBox.information(self, "Connection Status", "All PLCs disconnected.")