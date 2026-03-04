/**
 * SCADA Web HMI Viewer
 * Real-time monitoring and control via WebSocket
 */

// Global state
let socket = null;
let currentScreen = null;
let screens = [];
let tagValues = {};
let screenObjects = [];

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initWebSocket();
    loadScreens();
});

// Initialize WebSocket connection
function initWebSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to SCADA server');
        updateConnectionStatus(true);
        
        // Subscribe to all tags - request all available tags
        console.log('Requesting all tags from server...');
        socket.emit('subscribe_tags', { tags: [] });
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from SCADA server');
        updateConnectionStatus(false);
    });
    
    socket.on('tags_update', function(data) {
        console.log('Tags update received:', Object.keys(data).length, 'tags');
        console.log('Tag values:', data);
        tagValues = data;
        updateTagDisplay();
        
        // If screenObjects is empty but we have a current screen, re-render it
        if (screenObjects.length === 0 && currentScreen) {
            console.log('ScreenObjects empty, reloading screen:', currentScreen);
            loadScreen(currentScreen);
        } else {
            updateScreenObjects();
        }
    });
    
    socket.on('write_result', function(data) {
        console.log('Write result:', data);
        if (!data.success) {
            alert('写入失败: ' + (data.error || '未知错误'));
        }
    });
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    const indicator = document.getElementById('ws-status');
    const text = document.getElementById('ws-text');
    
    if (connected) {
        indicator.classList.add('connected');
        text.textContent = '已连接';
    } else {
        indicator.classList.remove('connected');
        text.textContent = '断开';
    }
}

// Load screen list from server
function loadScreens() {
    console.log('Loading screens from server...');
    fetch('/api/screens')
        .then(response => response.json())
        .then(data => {
            console.log('Screens data:', data);
            if (data.success) {
                screens = data.screens;
                console.log('Loaded', screens.length, 'screens:', screens.map(s => s.name));
                renderScreenList();
                
                // Load first screen if available
                if (screens.length > 0) {
                    loadScreen(screens[0].name);
                } else {
                    console.log('No screens available');
                }
            } else {
                console.error('Failed to load screens:', data.error);
            }
        })
        .catch(error => {
            console.error('Error loading screens:', error);
        });
}

// Render screen list in sidebar
function renderScreenList() {
    const list = document.getElementById('screen-list');
    list.innerHTML = '';
    
    screens.forEach(screen => {
        const li = document.createElement('li');
        li.textContent = screen.name;
        li.onclick = () => loadScreen(screen.name);
        if (currentScreen === screen.name) {
            li.classList.add('active');
        }
        list.appendChild(li);
    });
}

// Load a specific screen
function loadScreen(screenName) {
    console.log('Loading screen:', screenName);
    currentScreen = screenName;
    renderScreenList();
    
    showLoading(true);
    
    fetch(`/api/screens/${encodeURIComponent(screenName)}`)
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            console.log('Screen data:', data);
            if (data.success) {
                console.log('Rendering screen with', data.screen.objects.length, 'objects');
                renderScreen(data.screen);
            } else {
                console.error('Failed to load screen:', data.error);
                alert('加载画面失败: ' + data.error);
            }
        })
        .catch(error => {
            showLoading(false);
            console.error('Error loading screen:', error);
            alert('加载画面失败');
        });
}

// Render HMI screen
function renderScreen(screen) {
    console.log('Rendering screen:', screen.name, 'with', screen.objects.length, 'objects');
    const canvas = document.getElementById('hmi-canvas');
    
    // Set canvas size
    canvas.style.width = screen.width + 'px';
    canvas.style.height = screen.height + 'px';
    canvas.style.backgroundColor = screen.background_color || '#FFFFFF';
    
    // Clear existing objects
    canvas.innerHTML = '';
    screenObjects = [];
    
    // Render objects
    screen.objects.forEach((obj, index) => {
        console.log('Creating object:', obj.name, 'type:', obj.type, 'variables:', obj.variables);
        const element = createObjectElement(obj, index);
        if (element) {
            canvas.appendChild(element);
            screenObjects.push({
                element: element,
                data: obj
            });
            console.log('Object added to screenObjects:', obj.name);
        }
    });
    
    console.log('Total screenObjects:', screenObjects.length);
}

// Create HTML element for HMI object
function createObjectElement(obj, index) {
    const div = document.createElement('div');
    div.className = 'hmi-object';
    div.style.left = obj.x + 'px';
    div.style.top = obj.y + 'px';
    div.style.width = obj.width + 'px';
    div.style.height = obj.height + 'px';
    
    const props = obj.properties || {};
    
    switch (obj.type) {
        case 'button':
            div.className += ' hmi-button';
            div.textContent = props.text || 'Button';
            div.style.backgroundColor = props.background_color || '#f5f7fa';
            div.style.color = props.text_color || '#000000';
            div.style.fontSize = (props.font_size || 14) + 'px';
            div.style.fontWeight = props.font_bold ? 'bold' : 'normal';
            div.style.fontStyle = props.font_italic ? 'italic' : 'normal';
            div.style.textDecoration = props.font_underline ? 'underline' : 'none';
            div.onclick = () => handleButtonClick(obj);
            break;
            
        case 'label':
            div.className += ' hmi-label';
            if (props.border) div.classList.add('with-border');
            div.textContent = props.text || '';
            div.style.backgroundColor = props.background_color || 'transparent';
            div.style.color = props.text_color || '#000000';
            div.style.fontSize = (props.font_size || 14) + 'px';
            div.style.fontWeight = props.font_bold ? 'bold' : 'normal';
            div.style.fontStyle = props.font_italic ? 'italic' : 'normal';
            div.style.textDecoration = props.font_underline ? 'underline' : 'none';
            div.style.justifyContent = props.h_align || 'center';
            div.style.alignItems = props.v_align || 'center';
            break;
            
        case 'light':
            div.className += ' hmi-light';
            // Set default color, will be updated by updateScreenObjects
            div.style.backgroundColor = props.off_color || '#808080';
            break;
            
        case 'switch':
            div.className += ' hmi-switch';
            // Set default state, will be updated by updateScreenObjects
            div.textContent = props.off_text || 'OFF';
            div.style.backgroundColor = '#FFB6C1';
            div.onclick = () => handleSwitchClick(obj);
            break;
            
        case 'gauge':
            div.className += ' hmi-gauge';
            // Create empty gauge, will be updated by updateScreenObjects
            div.innerHTML = `
                <svg width="100%" height="100%" viewBox="0 0 100 60">
                    <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#e0e0e0" stroke-width="8"/>
                    <path d="M 10 50 A 40 40 0 0 1 10 50" fill="none" stroke="#4CAF50" stroke-width="8"/>
                    <text x="50" y="50" text-anchor="middle" font-size="12" font-weight="bold">0.0</text>
                </svg>
            `;
            break;
            
        case 'progress':
            div.className += ' hmi-progress';
            // Create empty progress, will be updated by updateScreenObjects
            div.innerHTML = `
                <div class="progress-fill" style="width: 0%"></div>
                <div class="progress-text">0.0${props.show_percentage ? '%' : ''}</div>
            `;
            break;
            
        default:
            // Unknown object type
            div.style.border = '1px dashed #999';
            div.textContent = obj.type;
            break;
    }
    
    // Handle visibility
    if (obj.visibility && obj.visibility.control_variable) {
        const controlVar = obj.visibility.control_variable;
        const compareValue = obj.visibility.compare_value || '1';
        const showWhenTrue = obj.visibility.show_when_true !== false;
        
        const varValue = tagValues[controlVar]?.value;
        const conditionMet = String(varValue) === String(compareValue);
        
        if (showWhenTrue) {
            div.style.display = conditionMet ? 'block' : 'none';
        } else {
            div.style.display = conditionMet ? 'none' : 'block';
        }
    }
    
    return div;
}

// Get variable value for an object
function getVariableValue(obj) {
    if (obj.variables && obj.variables.length > 0) {
        const varName = obj.variables[0].name;
        const tagData = tagValues[varName];
        console.log('Getting value for', varName, ':', tagData);
        if (tagData && tagData.value !== undefined && tagData.value !== null) {
            // Handle bit offset
            const bitOffset = obj.variables[0].bit_offset;
            if (bitOffset !== null && bitOffset !== undefined) {
                const intValue = parseInt(tagData.value) || 0;
                return (intValue >> bitOffset) & 1;
            }
            const floatVal = parseFloat(tagData.value);
            console.log('Parsed value for', varName, ':', floatVal);
            return isNaN(floatVal) ? 0 : floatVal;
        } else {
            // Debug: log missing tag
            if (!tagData) {
                console.log('Tag not found:', varName, 'Available tags:', Object.keys(tagValues).slice(0, 10));
            } else {
                console.log('Tag data invalid for', varName, ':', tagData);
            }
        }
    }
    return 0;
}

// Update screen objects with new tag values
function updateScreenObjects() {
    console.log('updateScreenObjects called, screenObjects count:', screenObjects.length);
    screenObjects.forEach(({ element, data }) => {
        const props = data.properties || {};
        
        switch (data.type) {
            case 'label':
                // Update label with variable value if bound
                if (data.variables && data.variables.length > 0) {
                    const value = getVariableValue(data);
                    console.log('Updating label', data.name, 'with value:', value);
                    // Format based on data type or properties
                    let displayValue = value;
                    if (props.decimal_places !== undefined) {
                        displayValue = value.toFixed(props.decimal_places);
                    }
                    // If label has format string, use it
                    if (props.text && props.text.includes('{value}')) {
                        element.textContent = props.text.replace('{value}', displayValue);
                    } else if (props.show_value) {
                        element.textContent = displayValue;
                    } else {
                        // Default: append value to text or show value only
                        const baseText = props.text || data.name || '';
                        if (baseText) {
                            element.textContent = baseText + ': ' + displayValue;
                        } else {
                            element.textContent = String(displayValue);
                        }
                    }
                }
                break;
                
            case 'light':
                const lightValue = getVariableValue(data);
                const isOn = lightValue > 0;
                console.log('Light', data.name, 'value:', lightValue, 'isOn:', isOn, 'variables:', data.variables);
                element.style.backgroundColor = isOn ? (props.on_color || '#00FF00') : (props.off_color || '#808080');
                break;
                
            case 'switch':
                const switchOn = getVariableValue(data) > 0;
                element.textContent = switchOn ? (props.on_text || 'ON') : (props.off_text || 'OFF');
                element.style.backgroundColor = switchOn ? '#90EE90' : '#FFB6C1';
                break;
                
            case 'gauge':
                const gaugeValue = getVariableValue(data);
                const minVal = props.min_value || 0;
                const maxVal = props.max_value || 100;
                const percentage = Math.min(100, Math.max(0, (gaugeValue - minVal) / (maxVal - minVal) * 100));
                element.innerHTML = `
                    <svg width="100%" height="100%" viewBox="0 0 100 60">
                        <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#e0e0e0" stroke-width="8"/>
                        <path d="M 10 50 A 40 40 0 0 1 ${10 + percentage * 0.8} ${50 - Math.sin(percentage * Math.PI / 100) * 40}" 
                              fill="none" stroke="#4CAF50" stroke-width="8"/>
                        <text x="50" y="50" text-anchor="middle" font-size="12" font-weight="bold">${gaugeValue.toFixed(1)}</text>
                    </svg>
                `;
                break;
                
            case 'progress':
                const progressValue = getVariableValue(data);
                const progressMin = props.min_value || 0;
                const progressMax = props.max_value || 100;
                const progressPercent = Math.min(100, Math.max(0, (progressValue - progressMin) / (progressMax - progressMin) * 100));
                element.innerHTML = `
                    <div class="progress-fill" style="width: ${progressPercent}%"></div>
                    <div class="progress-text">${progressValue.toFixed(1)}${props.show_percentage ? '%' : ''}</div>
                `;
                break;
        }
        
        // Update visibility
        if (data.visibility && data.visibility.control_variable) {
            const controlVar = data.visibility.control_variable;
            const compareValue = data.visibility.compare_value || '1';
            const showWhenTrue = data.visibility.show_when_true !== false;
            
            const varValue = tagValues[controlVar]?.value;
            const conditionMet = String(varValue) === String(compareValue);
            
            if (showWhenTrue) {
                element.style.display = conditionMet ? 'block' : 'none';
            } else {
                element.style.display = conditionMet ? 'none' : 'block';
            }
        }
    });
}

// Handle button click
function handleButtonClick(obj) {
    console.log('Button clicked:', obj);
    
    // Handle variable operations
    if (obj.properties && obj.properties.action) {
        const action = obj.properties.action;
        const targetVar = obj.properties.target_variable;
        
        if (targetVar && socket) {
            let value = 0;
            
            switch (action) {
                case '置1':
                case '置位':
                    value = 1;
                    break;
                case '置0':
                case '复位':
                    value = 0;
                    break;
                case '取反':
                    const currentValue = tagValues[targetVar]?.value || 0;
                    value = currentValue > 0 ? 0 : 1;
                    break;
                case '加1':
                    value = (tagValues[targetVar]?.value || 0) + 1;
                    break;
                case '减1':
                    value = (tagValues[targetVar]?.value || 0) - 1;
                    break;
                default:
                    return;
            }
            
            socket.emit('write_tag', {
                tag_name: targetVar,
                value: value
            });
        }
    }
}

// Handle switch click
function handleSwitchClick(obj) {
    console.log('Switch clicked:', obj);
    
    if (obj.variables && obj.variables.length > 0 && socket) {
        const varName = obj.variables[0].name;
        const bitOffset = obj.variables[0].bit_offset;
        const currentValue = tagValues[varName]?.value || 0;
        const newValue = currentValue > 0 ? 0 : 1;
        
        console.log('Writing to', varName, 'bit_offset:', bitOffset, 'value:', newValue);
        
        socket.emit('write_tag', {
            tag_name: varName,
            value: newValue,
            bit_offset: bitOffset
        });
    }
}

// Update tag display in panel
function updateTagDisplay() {
    const tagList = document.getElementById('tag-list');
    
    let html = '';
    for (const [name, data] of Object.entries(tagValues)) {
        const quality = (data.quality || 'Unknown').toString();
        const qualityLower = quality.toLowerCase();
        const qualityColor = (qualityLower === 'good' || qualityLower === 'good') ? '#4CAF50' : '#ff4444';
        
        html += `
            <div class="tag-item">
                <div class="tag-name">${name}</div>
                <div class="tag-value">${data.value !== undefined && data.value !== null ? data.value : '-'}</div>
                <div class="tag-quality" style="color: ${qualityColor}">质量: ${quality}</div>
            </div>
        `;
    }
    
    tagList.innerHTML = html || '<div style="padding: 20px; text-align: center; color: #999;">暂无变量数据</div>';
}

// Toggle tag panel
function toggleTagPanel() {
    const panel = document.getElementById('tag-panel');
    panel.classList.toggle('open');
}

// Show/hide loading overlay
function showLoading(show) {
    const loading = document.getElementById('loading');
    if (show) {
        loading.classList.remove('hidden');
    } else {
        loading.classList.add('hidden');
    }
}
