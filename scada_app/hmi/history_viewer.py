"""
History Data Viewer - 历史数据查询和趋势显示模块

功能：
1. 按时间范围查询标签历史数据
2. 显示趋势曲线图
3. 导出数据到 CSV
4. 多标签同图对比显示
5. 缩放/平移交互功能
6. 数据统计（最大/最小/平均值）
7. 报表生成功能
"""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import csv
import os
import statistics
from collections import defaultdict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QComboBox, QDateTimeEdit, 
    QGroupBox, QSplitter, QFileDialog, QMessageBox, QSpinBox,
    QCheckBox, QTabWidget, QListWidget, QListWidgetItem, QFrame,
    QScrollArea, QGridLayout, QSizePolicy, QApplication, QProgressBar
)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QThread
from PyQt5.QtGui import QColor, QBrush, QFont, QPalette, QPainter

try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    from matplotlib.dates import DateFormatter, AutoDateLocator
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available, trend chart will be disabled")

COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
    '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
]


class StatisticsPanel(QWidget):
    """数据统计面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.stats_data = {}
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        title = QLabel("数据统计")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(title)
        
        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(5)
        
        self.labels = {}
        stats_items = [
            ("数据点数", "count"),
            ("最大值", "max"),
            ("最小值", "min"),
            ("平均值", "avg"),
            ("标准差", "std"),
            ("总和", "sum"),
            ("范围", "range")
        ]
        
        for row, (label_text, key) in enumerate(stats_items):
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("color: #666;")
            self.stats_layout.addWidget(label, row, 0)
            
            value_label = QLabel("-")
            value_label.setStyleSheet("font-weight: bold; color: #333;")
            self.stats_layout.addWidget(value_label, row, 1)
            self.labels[key] = value_label
        
        layout.addLayout(self.stats_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def update_statistics(self, data: List[float], tag_name: str = ""):
        """更新统计数据"""
        if not data:
            for key in self.labels:
                self.labels[key].setText("-")
            return
        
        try:
            count = len(data)
            max_val = max(data)
            min_val = min(data)
            avg_val = statistics.mean(data)
            std_val = statistics.stdev(data) if count > 1 else 0
            sum_val = sum(data)
            range_val = max_val - min_val
            
            self.labels["count"].setText(f"{count}")
            self.labels["max"].setText(f"{max_val:.4f}")
            self.labels["min"].setText(f"{min_val:.4f}")
            self.labels["avg"].setText(f"{avg_val:.4f}")
            self.labels["std"].setText(f"{std_val:.4f}")
            self.labels["sum"].setText(f"{sum_val:.4f}")
            self.labels["range"].setText(f"{range_val:.4f}")
            
            self.stats_data = {
                "count": count,
                "max": max_val,
                "min": min_val,
                "avg": avg_val,
                "std": std_val,
                "sum": sum_val,
                "range": range_val
            }
        except Exception as e:
            print(f"Statistics error: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计数据"""
        return self.stats_data.copy()
    
    def clear(self):
        """清除统计数据"""
        for key in self.labels:
            self.labels[key].setText("-")
        self.stats_data = {}


class MultiTagListWidget(QWidget):
    """多标签选择控件"""
    
    tags_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_tags = []
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        btn_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setFixedWidth(60)
        self.select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("全不选")
        self.deselect_all_btn.setFixedWidth(60)
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.MultiSelection)
        self.tag_list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tag_list)
        
        self.setLayout(layout)
    
    def set_tags(self, tags: List[str]):
        """设置可选标签列表"""
        self.tag_list.clear()
        self.all_tags = tags
        for tag in tags:
            item = QListWidgetItem(tag)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.tag_list.addItem(item)
    
    def get_selected_tags(self) -> List[str]:
        """获取选中的标签列表"""
        selected = []
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected
    
    def select_all(self):
        """全选"""
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            item.setCheckState(Qt.Checked)
    
    def deselect_all(self):
        """全不选"""
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            item.setCheckState(Qt.Unchecked)
    
    def _on_item_changed(self, item):
        """标签选择变化"""
        self.tags_changed.emit()


class TrendChartWidget(QWidget):
    """趋势曲线图控件 - 支持多标签、缩放、平移"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.multi_tag_data = {}
        self.current_statistics = {}
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        if MATPLOTLIB_AVAILABLE:
            self._setup_chinese_font()
            
            self.figure = Figure(figsize=(10, 6), dpi=100)
            self.figure.subplots_adjust(left=0.08, right=0.95, top=0.92, bottom=0.15)
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            
            self.toolbar = NavigationToolbar(self.canvas, self)
            self.toolbar.setStyleSheet("QToolBar { border: none; }")
            
            layout.addWidget(self.toolbar)
            layout.addWidget(self.canvas)
            
            self._connect_events()
        else:
            label = QLabel("趋势图功能需要安装 matplotlib\n请运行: pip install matplotlib")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
        
        self.setLayout(layout)
    
    def _setup_chinese_font(self):
        """配置 matplotlib 中文字体"""
        from matplotlib import rcParams
        
        chinese_fonts = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
        font_found = None
        
        for font in chinese_fonts:
            try:
                from matplotlib.font_manager import findfont, FontProperties
                findfont(FontProperties(family=font))
                font_found = font
                break
            except:
                continue
        
        if font_found:
            rcParams['font.sans-serif'] = [font_found, 'DejaVu Sans']
            rcParams['axes.unicode_minus'] = False
        else:
            print("Warning: No Chinese font found, using English labels for trend chart")
    
    def _connect_events(self):
        """连接鼠标事件"""
        if MATPLOTLIB_AVAILABLE:
            self.canvas.mpl_connect('scroll_event', self._on_scroll)
            self.canvas.mpl_connect('motion_notify_event', self._on_motion)
    
    def _on_scroll(self, event):
        """鼠标滚轮缩放"""
        if event.inaxes != self.ax:
            return
        
        scale_factor = 1.1 if event.button == 'down' else 0.9
        
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        x_center = event.xdata
        y_center = event.ydata
        
        new_xlim = [
            x_center - (x_center - xlim[0]) * scale_factor,
            x_center + (xlim[1] - x_center) * scale_factor
        ]
        new_ylim = [
            y_center - (y_center - ylim[0]) * scale_factor,
            y_center + (ylim[1] - y_center) * scale_factor
        ]
        
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.canvas.draw_idle()
    
    def _on_motion(self, event):
        """鼠标移动显示数值"""
        pass
    
    def plot_multi_data(self, data_dict: Dict[str, List[Tuple]], show_points: bool = True):
        """绘制多标签趋势曲线
        
        Args:
            data_dict: {tag_name: [(timestamp, value, quality), ...]}
            show_points: 是否显示数据点
        """
        if not MATPLOTLIB_AVAILABLE or not data_dict:
            return
        
        from matplotlib import rcParams
        has_chinese_font = any('CJK' in f or 'Hei' in f or 'YaHei' in f 
                               for f in rcParams.get('font.sans-serif', []))
        
        xlabel = '时间' if has_chinese_font else 'Time'
        ylabel = '数值' if has_chinese_font else 'Value'
        title = '多标签历史趋势对比' if has_chinese_font else 'Multi-Tag Trend Comparison'
        
        self.ax.clear()
        self.multi_tag_data = data_dict
        self.current_statistics = {}
        
        color_idx = 0
        for tag_name, data in data_dict.items():
            if not data:
                continue
            
            timestamps = []
            values = []
            
            for timestamp, value, quality in data:
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    except:
                        continue
                timestamps.append(timestamp)
                try:
                    values.append(float(value))
                except (ValueError, TypeError):
                    values.append(0)
            
            if not timestamps:
                continue
            
            color = COLORS[color_idx % len(COLORS)]
            
            self.ax.plot(timestamps, values, color=color, linewidth=1.5, 
                        label=tag_name, alpha=0.8)
            
            if show_points:
                self.ax.scatter(timestamps, values, c=color, s=15, alpha=0.6, zorder=5)
            
            if values:
                self.current_statistics[tag_name] = {
                    'count': len(values),
                    'max': max(values),
                    'min': min(values),
                    'avg': statistics.mean(values),
                    'std': statistics.stdev(values) if len(values) > 1 else 0,
                    'sum': sum(values)
                }
            
            color_idx += 1
        
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(title)
        self.ax.grid(True, alpha=0.3, linestyle='--')
        
        if color_idx > 0:
            self.ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
        
        self.ax.xaxis.set_major_formatter(DateFormatter('%m-%d %H:%M'))
        self.ax.xaxis.set_major_locator(AutoDateLocator())
        self.figure.autofmt_xdate()
        
        self.canvas.draw()
    
    def plot_data(self, data: List[Tuple], tag_name: str):
        """绘制单标签趋势曲线"""
        self.plot_multi_data({tag_name: data})
    
    def get_statistics(self) -> Dict[str, Dict]:
        """获取当前图表的统计数据"""
        return self.current_statistics.copy()
    
    def clear(self):
        """清除图表"""
        if MATPLOTLIB_AVAILABLE:
            self.ax.clear()
            self.multi_tag_data = {}
            self.current_statistics = {}
            self.canvas.draw()
    
    def save_chart(self, file_path: str):
        """保存图表到文件"""
        if MATPLOTLIB_AVAILABLE:
            self.figure.savefig(file_path, dpi=150, bbox_inches='tight',
                               facecolor='white', edgecolor='none')


class HistoryDataTable(QTableWidget):
    """历史数据表格显示"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["时间", "数值", "质量", "标签名"])
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        
        self.setSortingEnabled(True)
        
    def set_data(self, data: List[Tuple]):
        """设置表格数据"""
        self.setRowCount(len(data))
        
        for row, (timestamp, value, quality, tag_name) in enumerate(data):
            if isinstance(timestamp, str):
                time_str = timestamp
            else:
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            time_item = QTableWidgetItem(time_str)
            self.setItem(row, 0, time_item)
            
            value_item = QTableWidgetItem(str(value))
            self.setItem(row, 1, value_item)
            
            quality_item = QTableWidgetItem(quality)
            if quality == "GOOD":
                quality_item.setBackground(QBrush(QColor(200, 255, 200)))
            else:
                quality_item.setBackground(QBrush(QColor(255, 200, 200)))
            self.setItem(row, 2, quality_item)
            
            tag_item = QTableWidgetItem(tag_name)
            self.setItem(row, 3, tag_item)
    
    def set_multi_tag_data(self, data_dict: Dict[str, List[Tuple]]):
        """设置多标签表格数据"""
        all_data = []
        for tag_name, data_list in data_dict.items():
            for timestamp, value, quality in data_list:
                all_data.append((timestamp, value, quality, tag_name))
        
        all_data.sort(key=lambda x: x[0] if not isinstance(x[0], str) else x[0], reverse=True)
        self.set_data(all_data)


class ReportGenerator:
    """报表生成器"""
    
    @staticmethod
    def generate_html_report(data_dict: Dict[str, List[Tuple]], 
                            statistics: Dict[str, Dict],
                            time_range: Tuple[datetime, datetime],
                            chart_image_path: str = None) -> str:
        """生成HTML报表"""
        start_time, end_time = time_range
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>历史数据报表</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .info {{ background: #e8f5e9; padding: 15px; border-radius: 4px; margin: 20px 0; }}
        .info p {{ margin: 5px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr:hover {{ background: #f1f1f1; }}
        .stat-value {{ font-weight: bold; color: #2196F3; }}
        .chart-container {{ text-align: center; margin: 20px 0; }}
        .chart-container img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; text-align: center; }}
        .tag-section {{ margin-bottom: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>历史数据报表</h1>
        
        <div class="info">
            <p><strong>报表生成时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p><strong>查询时间范围:</strong> {start_time.strftime("%Y-%m-%d %H:%M:%S")} 至 {end_time.strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p><strong>标签数量:</strong> {len(data_dict)}</p>
        </div>
"""
        
        if chart_image_path and os.path.exists(chart_image_path):
            html += f"""
        <div class="chart-container">
            <h2>趋势曲线图</h2>
            <img src="{os.path.basename(chart_image_path)}" alt="趋势曲线图">
        </div>
"""
        
        html += """
        <h2>数据统计</h2>
        <table>
            <tr>
                <th>标签名称</th>
                <th>数据点数</th>
                <th>最大值</th>
                <th>最小值</th>
                <th>平均值</th>
                <th>标准差</th>
                <th>总和</th>
            </tr>
"""
        
        for tag_name, stats in statistics.items():
            html += f"""
            <tr>
                <td>{tag_name}</td>
                <td class="stat-value">{stats.get('count', '-')}</td>
                <td class="stat-value">{stats.get('max', 0):.4f}</td>
                <td class="stat-value">{stats.get('min', 0):.4f}</td>
                <td class="stat-value">{stats.get('avg', 0):.4f}</td>
                <td class="stat-value">{stats.get('std', 0):.4f}</td>
                <td class="stat-value">{stats.get('sum', 0):.4f}</td>
            </tr>
"""
        
        html += """
        </table>
        
        <h2>详细数据</h2>
"""
        
        for tag_name, data_list in data_dict.items():
            html += f"""
        <div class="tag-section">
            <h3>{tag_name}</h3>
            <table>
                <tr>
                    <th>时间</th>
                    <th>数值</th>
                    <th>质量</th>
                </tr>
"""
            for timestamp, value, quality in data_list[:100]:
                if isinstance(timestamp, datetime):
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = str(timestamp)
                html += f"""
                <tr>
                    <td>{time_str}</td>
                    <td>{value}</td>
                    <td>{quality}</td>
                </tr>
"""
            
            if len(data_list) > 100:
                html += f"""
                <tr><td colspan="3" style="text-align: center; color: #666;">... 共 {len(data_list)} 条记录，仅显示前100条 ...</td></tr>
"""
            
            html += """
            </table>
        </div>
"""
        
        html += f"""
        <div class="footer">
            <p>SCADA HMI 历史数据报表 | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    @staticmethod
    def generate_csv_report(data_dict: Dict[str, List[Tuple]], 
                           file_path: str) -> bool:
        """生成CSV报表"""
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["标签名", "时间", "数值", "质量"])
                
                all_data = []
                for tag_name, data_list in data_dict.items():
                    for timestamp, value, quality in data_list:
                        if isinstance(timestamp, datetime):
                            timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        all_data.append((tag_name, timestamp, value, quality))
                
                all_data.sort(key=lambda x: x[1], reverse=True)
                
                for row in all_data:
                    writer.writerow(row)
            
            return True
        except Exception as e:
            print(f"CSV report error: {e}")
            return False


class HistoryViewerWidget(QWidget):
    """历史数据查询主控件 - 增强版"""
    
    data_exported = pyqtSignal(str)
    
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.current_data = []
        self.current_multi_data = {}
        self.current_statistics = {}
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        query_group = QGroupBox("查询条件")
        query_layout = QVBoxLayout()
        
        row1_layout = QHBoxLayout()
        
        row1_layout.addWidget(QLabel("标签选择:"))
        
        self.single_tag_radio = QCheckBox("单标签模式")
        self.single_tag_radio.setChecked(True)
        self.single_tag_radio.stateChanged.connect(self._toggle_tag_mode)
        row1_layout.addWidget(self.single_tag_radio)
        
        self.tag_combo = QComboBox()
        self.tag_combo.setMinimumWidth(200)
        self.tag_combo.setEditable(True)
        self._populate_tag_combo()
        row1_layout.addWidget(self.tag_combo)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.setToolTip("刷新标签列表")
        self.refresh_btn.clicked.connect(self._populate_tag_combo)
        row1_layout.addWidget(self.refresh_btn)
        
        row1_layout.addSpacing(20)
        
        row1_layout.addWidget(QLabel("开始时间:"))
        self.start_time = QDateTimeEdit()
        self.start_time.setCalendarPopup(True)
        self.start_time.setDateTime(QDateTime.currentDateTime().addDays(-1))
        row1_layout.addWidget(self.start_time)
        
        row1_layout.addWidget(QLabel("结束时间:"))
        self.end_time = QDateTimeEdit()
        self.end_time.setCalendarPopup(True)
        self.end_time.setDateTime(QDateTime.currentDateTime())
        row1_layout.addWidget(self.end_time)
        
        row1_layout.addWidget(QLabel("最大条数:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 50000)
        self.limit_spin.setValue(5000)
        self.limit_spin.setSingleStep(500)
        row1_layout.addWidget(self.limit_spin)
        
        row1_layout.addStretch()
        query_layout.addLayout(row1_layout)
        
        row2_layout = QHBoxLayout()
        
        row2_layout.addWidget(QLabel("快速选择:"))
        self.quick_1h = QPushButton("1小时")
        self.quick_1h.clicked.connect(lambda: self._set_time_range(1))
        row2_layout.addWidget(self.quick_1h)
        
        self.quick_6h = QPushButton("6小时")
        self.quick_6h.clicked.connect(lambda: self._set_time_range(6))
        row2_layout.addWidget(self.quick_6h)
        
        self.quick_24h = QPushButton("24小时")
        self.quick_24h.clicked.connect(lambda: self._set_time_range(24))
        row2_layout.addWidget(self.quick_24h)
        
        self.quick_7d = QPushButton("7天")
        self.quick_7d.clicked.connect(lambda: self._set_time_range(24*7))
        row2_layout.addWidget(self.quick_7d)
        
        self.quick_30d = QPushButton("30天")
        self.quick_30d.clicked.connect(lambda: self._set_time_range(24*30))
        row2_layout.addWidget(self.quick_30d)
        
        row2_layout.addStretch()
        
        row2_layout.addWidget(QLabel("显示选项:"))
        self.show_points_cb = QCheckBox("显示数据点")
        self.show_points_cb.setChecked(True)
        row2_layout.addWidget(self.show_points_cb)
        
        self.show_grid_cb = QCheckBox("显示网格")
        self.show_grid_cb.setChecked(True)
        row2_layout.addWidget(self.show_grid_cb)
        
        query_layout.addLayout(row2_layout)
        
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        self.multi_tag_widget = MultiTagListWidget()
        self.multi_tag_widget.setMaximumHeight(150)
        self.multi_tag_widget.setVisible(False)
        self.multi_tag_widget.tags_changed.connect(self._on_tags_changed)
        layout.addWidget(self.multi_tag_widget)
        
        btn_layout = QHBoxLayout()
        
        self.query_btn = QPushButton("🔍 查询")
        self.query_btn.setFixedHeight(32)
        self.query_btn.clicked.connect(self._execute_query)
        btn_layout.addWidget(self.query_btn)
        
        self.export_csv_btn = QPushButton("📥 导出CSV")
        self.export_csv_btn.setFixedHeight(32)
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.export_csv_btn.setEnabled(False)
        btn_layout.addWidget(self.export_csv_btn)
        
        self.export_chart_btn = QPushButton("🖼️ 保存图表")
        self.export_chart_btn.setFixedHeight(32)
        self.export_chart_btn.clicked.connect(self._export_chart)
        self.export_chart_btn.setEnabled(False)
        btn_layout.addWidget(self.export_chart_btn)
        
        self.report_btn = QPushButton("📊 生成报表")
        self.report_btn.setFixedHeight(32)
        self.report_btn.clicked.connect(self._generate_report)
        self.report_btn.setEnabled(False)
        btn_layout.addWidget(self.report_btn)
        
        self.clear_btn = QPushButton("🗑️ 清除")
        self.clear_btn.setFixedHeight(32)
        self.clear_btn.clicked.connect(self._clear_data)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        
        self.status_label = QLabel("就绪")
        btn_layout.addWidget(self.status_label)
        
        layout.addLayout(btn_layout)
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        left_splitter = QSplitter(Qt.Vertical)
        
        self.data_table = HistoryDataTable()
        left_splitter.addWidget(self.data_table)
        
        self.trend_chart = TrendChartWidget()
        left_splitter.addWidget(self.trend_chart)
        
        left_splitter.setSizes([300, 400])
        
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        self.statistics_panel = StatisticsPanel()
        self.statistics_panel.setMaximumWidth(200)
        right_layout.addWidget(self.statistics_panel)
        
        self.multi_stats_panel = QWidget()
        multi_stats_layout = QVBoxLayout()
        multi_stats_layout.setContentsMargins(0, 0, 0, 0)
        
        multi_stats_title = QLabel("多标签统计")
        multi_stats_title.setFont(QFont("Arial", 10, QFont.Bold))
        multi_stats_layout.addWidget(multi_stats_title)
        
        self.multi_stats_table = QTableWidget()
        self.multi_stats_table.setColumnCount(4)
        self.multi_stats_table.setHorizontalHeaderLabels(["标签", "最大", "最小", "平均"])
        self.multi_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.multi_stats_table.setMaximumHeight(200)
        multi_stats_layout.addWidget(self.multi_stats_table)
        
        self.multi_stats_panel.setLayout(multi_stats_layout)
        right_layout.addWidget(self.multi_stats_panel)
        
        right_layout.addStretch()
        
        right_panel.setLayout(right_layout)
        right_panel.setMaximumWidth(250)
        
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_panel)
        
        main_splitter.setSizes([800, 200])
        
        layout.addWidget(main_splitter)
        
        self.setLayout(layout)
    
    def _toggle_tag_mode(self, state):
        """切换单/多标签模式"""
        is_single = state == Qt.Checked
        self.tag_combo.setVisible(is_single)
        self.multi_tag_widget.setVisible(not is_single)
        
        if not is_single:
            self._populate_multi_tag_list()
    
    def _populate_tag_combo(self):
        """填充标签下拉框"""
        current_text = self.tag_combo.currentText()
        self.tag_combo.clear()
        
        tag_names = self._get_available_tags()
        
        if tag_names:
            self.tag_combo.addItems(tag_names)
            if current_text and current_text in tag_names:
                self.tag_combo.setCurrentText(current_text)
        else:
            self.tag_combo.addItem("(无标签)")
    
    def _populate_multi_tag_list(self):
        """填充多标签列表"""
        tag_names = self._get_available_tags()
        self.multi_tag_widget.set_tags(tag_names)
    
    def _get_available_tags(self) -> List[str]:
        """获取可用标签列表"""
        tag_names = []
        
        try:
            from scada_app.core.data_storage_manager import data_storage_manager
            
            storage = data_storage_manager._storage
            
            if hasattr(storage, 'db_path'):
                db_path = storage.db_path
                if db_path:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT tag_name FROM data_logs ORDER BY tag_name")
                    tag_names = [row[0] for row in cursor.fetchall()]
                    conn.close()
            elif hasattr(storage, 'base_dir'):
                import glob
                import os
                pattern = os.path.join(storage.base_dir, "data_logs_*.csv")
                csv_files = glob.glob(pattern)
                for csv_file in csv_files:
                    try:
                        with open(csv_file, 'r', encoding='utf-8-sig') as f:
                            import csv
                            reader = csv.DictReader(f)
                            for row in reader:
                                tag_name = row.get('tag_name', '')
                                if tag_name and tag_name not in tag_names:
                                    tag_names.append(tag_name)
                    except:
                        pass
                tag_names.sort()
            elif hasattr(storage, 'sql_manager'):
                if storage.sql_manager.connection:
                    cursor = storage.sql_manager.connection.cursor()
                    cursor.execute("SELECT DISTINCT tag_name FROM data_logs ORDER BY tag_name")
                    tag_names = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error reading tags from data_storage_manager: {e}")
        
        if not tag_names and self.data_manager:
            if hasattr(self.data_manager, 'tags') and self.data_manager.tags:
                tag_names = sorted(self.data_manager.tags.keys())
        
        return tag_names
    
    def _set_time_range(self, hours: int):
        """设置快速时间范围"""
        end = datetime.now()
        start = end - timedelta(hours=hours)
        self.start_time.setDateTime(QDateTime(start))
        self.end_time.setDateTime(QDateTime(end))
    
    def _on_tags_changed(self):
        """标签选择变化"""
        pass
    
    def _execute_query(self):
        """执行历史数据查询"""
        start_dt = self.start_time.dateTime().toPyDateTime()
        end_dt = self.end_time.dateTime().toPyDateTime()
        limit = self.limit_spin.value()
        
        if start_dt >= end_dt:
            QMessageBox.warning(self, "警告", "开始时间必须早于结束时间")
            return
        
        is_single_mode = self.single_tag_radio.isChecked()
        
        if is_single_mode:
            tag_name = self.tag_combo.currentText()
            if not tag_name:
                QMessageBox.warning(self, "警告", "请选择要查询的标签")
                return
            tags_to_query = [tag_name]
        else:
            tags_to_query = self.multi_tag_widget.get_selected_tags()
            if not tags_to_query:
                QMessageBox.warning(self, "警告", "请至少选择一个标签")
                return
        
        self.status_label.setText("正在查询...")
        QApplication.processEvents()
        
        try:
            self.current_multi_data = {}
            all_data = []
            
            for tag in tags_to_query:
                results = self._query_database(tag, start_dt, end_dt, limit)
                if results:
                    self.current_multi_data[tag] = [
                        (timestamp, value, quality) 
                        for value, timestamp, quality in results
                    ]
                    for value, timestamp, quality in results:
                        all_data.append((timestamp, value, quality, tag))
            
            if not self.current_multi_data:
                self.status_label.setText("未找到数据")
                QMessageBox.information(self, "提示", "未找到指定时间范围内的数据")
                return
            
            self.current_data = all_data
            
            self.data_table.set_multi_tag_data(self.current_multi_data)
            
            self.trend_chart.plot_multi_data(
                self.current_multi_data, 
                self.show_points_cb.isChecked()
            )
            
            self.current_statistics = self.trend_chart.get_statistics()
            self._update_statistics_display()
            
            record_count = sum(len(d) for d in self.current_multi_data.values())
            self.status_label.setText(f"查询完成: {len(tags_to_query)} 个标签, {record_count} 条记录")
            
            self.export_csv_btn.setEnabled(True)
            self.export_chart_btn.setEnabled(True)
            self.report_btn.setEnabled(True)
            
        except Exception as e:
            self.status_label.setText("查询失败")
            QMessageBox.critical(self, "错误", f"查询失败: {str(e)}")
    
    def _update_statistics_display(self):
        """更新统计显示"""
        if len(self.current_statistics) == 1:
            tag_name = list(self.current_statistics.keys())[0]
            stats = self.current_statistics[tag_name]
            
            data = []
            if tag_name in self.current_multi_data:
                for _, value, _ in self.current_multi_data[tag_name]:
                    try:
                        data.append(float(value))
                    except:
                        pass
            
            self.statistics_panel.update_statistics(data, tag_name)
            self.multi_stats_panel.setVisible(False)
        else:
            self.statistics_panel.clear()
            self.multi_stats_panel.setVisible(True)
            
            self.multi_stats_table.setRowCount(len(self.current_statistics))
            for row, (tag_name, stats) in enumerate(self.current_statistics.items()):
                self.multi_stats_table.setItem(row, 0, QTableWidgetItem(tag_name))
                self.multi_stats_table.setItem(row, 1, QTableWidgetItem(f"{stats.get('max', 0):.4f}"))
                self.multi_stats_table.setItem(row, 2, QTableWidgetItem(f"{stats.get('min', 0):.4f}"))
                self.multi_stats_table.setItem(row, 3, QTableWidgetItem(f"{stats.get('avg', 0):.4f}"))
    
    def _query_database(self, tag_name: str, start_dt: datetime, end_dt: datetime, limit: int):
        """从数据库查询历史数据"""
        try:
            from scada_app.core.data_storage_manager import data_storage_manager
            
            results = data_storage_manager.query_logs(tag_name, start_dt, end_dt, limit)
            
            if results:
                return [(r['tag_value'], r['timestamp'], r.get('quality', 'GOOD')) for r in results]
        except Exception as e:
            print(f"Query error: {e}")
        
        return []
    
    def _export_csv(self):
        """导出数据到 CSV 文件"""
        if not self.current_multi_data:
            QMessageBox.warning(self, "警告", "没有数据可导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出历史数据",
            f"history_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            if ReportGenerator.generate_csv_report(self.current_multi_data, file_path):
                self.status_label.setText(f"已导出: {os.path.basename(file_path)}")
                self.data_exported.emit(file_path)
                QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")
            else:
                raise Exception("CSV生成失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def _export_chart(self):
        """保存图表到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存趋势图",
            f"trend_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            try:
                self.trend_chart.save_chart(file_path)
                self.status_label.setText(f"图表已保存: {os.path.basename(file_path)}")
                QMessageBox.information(self, "成功", f"图表已保存到:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def _generate_report(self):
        """生成报表"""
        if not self.current_multi_data:
            QMessageBox.warning(self, "警告", "没有数据可生成报表")
            return
        
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择报表保存目录",
            ""
        )
        
        if not folder_path:
            return
        
        try:
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            chart_path = os.path.join(folder_path, f"chart_{timestamp_str}.png")
            self.trend_chart.save_chart(chart_path)
            
            start_dt = self.start_time.dateTime().toPyDateTime()
            end_dt = self.end_time.dateTime().toPyDateTime()
            
            html_content = ReportGenerator.generate_html_report(
                self.current_multi_data,
                self.current_statistics,
                (start_dt, end_dt),
                chart_path
            )
            
            report_path = os.path.join(folder_path, f"report_{timestamp_str}.html")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            csv_path = os.path.join(folder_path, f"data_{timestamp_str}.csv")
            ReportGenerator.generate_csv_report(self.current_multi_data, csv_path)
            
            self.status_label.setText(f"报表已生成")
            QMessageBox.information(
                self, "成功", 
                f"报表已生成:\n\nHTML报表: {report_path}\n数据文件: {csv_path}\n图表文件: {chart_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"报表生成失败: {str(e)}")
    
    def _clear_data(self):
        """清除显示的数据"""
        self.current_data = []
        self.current_multi_data = {}
        self.current_statistics = {}
        self.data_table.setRowCount(0)
        self.trend_chart.clear()
        self.statistics_panel.clear()
        self.multi_stats_table.setRowCount(0)
        self.status_label.setText("就绪")
        self.export_csv_btn.setEnabled(False)
        self.export_chart_btn.setEnabled(False)
        self.report_btn.setEnabled(False)
    
    def refresh_tags(self):
        """刷新标签列表"""
        self._populate_tag_combo()
        if not self.single_tag_radio.isChecked():
            self._populate_multi_tag_list()
