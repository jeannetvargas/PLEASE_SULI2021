"""PLEASE - The Python Low-energy Electron Analysis SuitE.

Author: Maxwell Grady
Affiliation: University of New Hampshire Department of Physics Pohl group
Version 1.0.0
Date: May, 2017

PLEASE provides a convienient Graphical User Interface for exploration and
analysis of Low Energy Electron Microscopy and Diffraction data sets.
Specifically, emphasis is placed on visualization of Intensity-Voltage data
sets and providing an easy popint and click method for extracting I(V) curves.

Analysis of LEEM-I(V) and LEED-I(V) data sets provides inisght with atomic
scale resolution to the surface structure of a wide array of materials from
semiconductors to metals in bulk or thin film as well as single layer 2D materials.
"""

"""*** PLEASE - UPDATE ***
-- Jeannet Vargas
Brookhaven National Lab: SULI summer 2021

Changes made that allow for user input for patch size, rather than the default of rad 8 for circles,
This allows for the user to input an even integer in the configuration file for the patch width,
and with that account for small selection areas for enhanced data extraction.

Patch size was successfully changed for user input, and image adjustment is currently in progress: need to determine
functions to add a contrast change to loaded image once it is loaded as a 3D numpy array, and open
the loaded images in menu bar along with a scroll bar (opencv trackbar) with the contrast change values to adjust
the image. Other functions, like brightness change can later be made once algorithm for changes in numpy array are
determined.

These are first limited to LEEM functions in PLEASE program - Would only work under the LEEM tab in PLEASE
once completed, image adjustment will be extended to LEED data sets. Since LEED data uses window extraction rather
than circular patches, changes were not made.

Code Changes made in: class Patchsize, def setupMenu, def initConfigTab, def validatePatchWidth,  def load_experiment,
def handleLEEMClick, def adjustLoadedImage
"""
# Stdlib and Scientific Stack imports
import os
import sys
import yaml
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

# local project imports
import LEEMFUNCTIONS as LF
from bline import bline
from colors import Palette
from data import LeedData, LeemData
from experiment import Experiment
from qthreads import WorkerThread
from terminal import MessageConsole
from yamloutput import ExperimentYAMLOutput
from adjimage import ImageAdjust

__Version = '1.0.0'


class ExtendedCrossHair(QtCore.QObject):
    """Set of perpindicular InfiniteLines tracking mouse postion."""

    def __init__(self, pen=None):
        """."""
        super(ExtendedCrossHair, self).__init__()

        self.hline = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        self.vline = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self.curPos = (0, 0)  # store (x, y) mouse position

    def setLineWidth(self, w):
        """Set line width for self.hline and self.vline."""
        color = pg.mkColor('y')
        pen = pg.mkPen(color=color, width=w)
        self.hline.pen = pen
        self.vline.pen = pen
        self.hline.currentPen = pen
        self.vline.currentPen = pen
        self.hline.update()
        self.vline.update()


class PatchSize(QtCore.QObject):#create new class to validate the setPatchWidth
    #create circle patches and set colors and radius to user input
    def setPatchWidth(self, pw, event):
        self.LEEMclicks = 0
        self.qcolors = Palette().qcolors
        self.LEEMcircs = []
        self.LEEMimageplotwidget = pg.PlotWidget()

        pos = event.pos()
        brush = QtGui.QBrush(self.qcolors[self.LEEMclicks - 1])
        rad = pw
        x = pos.x() - rad/2
        y = pos.y() - rad/2
        circ = self.LEEMimageplotwidget.scene().addEllipse(x, y, rad, rad, brush=brush)
        self.LEEMcircs.append(circ)


class MainWindow(QtWidgets.QMainWindow):
    """Top level conatiner to wrap Viewer object.

    Provides dockable interface.
    Provides Menubar
    """

    def __init__(self, v=None):
        """Parameter v tracks the current PLEASE version number."""
        super(QtWidgets.QMainWindow, self).__init__()
        if v is not None:
            self.setWindowTitle("PLEASE v. {}".format(v))
        else:
            self.setWindowTitle("PLEASE")
        self.viewer = Viewer(parent=self)
        self.setCentralWidget(self.viewer)

        self.menubar = self.menuBar()
        self.setupMenu()

        self.setupDockableWidgets()
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.dockwidget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.bottomdock)

    def setupDockableWidgets(self):
        """Dock control and information widgets to main window."""
        # Leftside button widgets
        self.dockwidget = QtWidgets.QDockWidget(self)

        # setup pushbutton functions
        self.groupbox = QtWidgets.QGroupBox()
        self.buttonboxlayout = QtWidgets.QVBoxLayout()
        self.loadexperimentbutton = QtWidgets.QPushButton("Load Experiment")
        self.loadexperimentbutton.clicked.connect(self.viewer.load_experiment)
        self.outputLEEMbutton = QtWidgets.QPushButton("Output LEEM Data")
        self.outputLEEDbutton = QtWidgets.QPushButton("Output LEED Data")
        self.outputLEEMbutton.clicked.connect(lambda: self.viewer.outputIV(datatype='LEEM'))
        self.outputLEEDbutton.clicked.connect(lambda: self.viewer.outputIV(datatype='LEED'))
        self.quitbutton = QtWidgets.QPushButton("Quit")
        self.quitbutton.clicked.connect(self.quit)
        self.buttonboxlayout.addWidget(self.loadexperimentbutton)
        self.buttonboxlayout.addWidget(self.outputLEEMbutton)
        self.buttonboxlayout.addWidget(self.outputLEEDbutton)
        self.buttonboxlayout.addStretch()
        self.buttonboxlayout.addWidget(self.quitbutton)
        self.groupbox.setLayout(self.buttonboxlayout)

        self.dockwidget.setWidget(self.groupbox)

        # bottom message console
        self.bottomdock = QtWidgets.QDockWidget(self)
        self.console = MessageConsole()  # intercepts messges from sys.stdout
        self.bottomdock.setWidget(self.console)

    def setupMenu(self):
        """Set Menu actions for LEEM and LEED."""
        fileMenu = self.menubar.addMenu("File")
        LEEMMenu = self.menubar.addMenu("LEEM")
        LEEDMenu = self.menubar.addMenu("LEED")
        helpMenu = self.menubar.addMenu("Help")
        imageMenu = self.menubar.addMenu("Image") ###new menu bar for image adjustment

        # File menu
        self.createYAMLAction = QtWidgets.QAction("Generate Experiment Config File", self)
        self.createYAMLAction.triggered.connect(self.viewer.createExperimentConfigFile)
        fileMenu.addAction(self.createYAMLAction)

        self.exitAction = QtWidgets.QAction("Exit", self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(self.quit)
        fileMenu.addAction(self.exitAction)

        # LEEM menu
        self.outputLEEMAction = QtWidgets.QAction("Output I(V)", self)
        self.outputLEEMAction.triggered.connect(lambda: self.viewer.outputIV(datatype='LEEM'))
        LEEMMenu.addAction(self.outputLEEMAction)

        self.clearLEEMAction = QtWidgets.QAction("Clear I(V)", self)
        self.clearLEEMAction.triggered.connect(self.viewer.clearLEEMIV)
        LEEMMenu.addAction(self.clearLEEMAction)

        rectMenu = LEEMMenu.addMenu("Window Extraction")
        self.enableLEEMRectAction = QtWidgets.QAction("Enable LEEM Window Extraction", self)
        self.enableLEEMRectAction.triggered.connect(self.viewer.enableLEEMWindow)
        rectMenu.addAction(self.enableLEEMRectAction)

        self.disableLEEMRectAction = QtWidgets.QAction("Disable LEEM Window Extraction", self)
        self.disableLEEMRectAction.triggered.connect(self.viewer.disableLEEMWindow)
        rectMenu.addAction(self.disableLEEMRectAction)

        self.clearWindowsAction = QtWidgets.QAction("Clear Windows", self)
        self.clearWindowsAction.triggered.connect(self.viewer.clearLEEMWindows)
        rectMenu.addAction(self.clearWindowsAction)

        self.extractLEEMWindowAction = QtWidgets.QAction("Extract I(V) from Windows", self)
        self.extractLEEMWindowAction.triggered.connect(self.viewer.extractLEEMWindows)
        self.extractLEEMWindowAction.setEnabled(self.viewer.LEEMRectWindowEnabled)
        rectMenu.addAction(self.extractLEEMWindowAction)

        lineprofileMenu = LEEMMenu.addMenu("Line Profile Analysis")
        self.enableLEEMLinesAction = QtWidgets.QAction("Enable LEEM Line Profile", self)
        self.enableLEEMLinesAction.triggered.connect(self.viewer.enableLEEMLineProfile)
        lineprofileMenu.addAction(self.enableLEEMLinesAction)

        self.disableLEEMLinesAction = QtWidgets.QAction("Disable LEEM Line Profile", self)
        self.disableLEEMLinesAction.triggered.connect(self.viewer.disableLEEMLineProfile)
        lineprofileMenu.addAction(self.disableLEEMLinesAction)

        self.clearLEEMLineProfileAction = QtWidgets.QAction("Clear Line Profiles", self)
        self.clearLEEMLineProfileAction.triggered.connect(self.viewer.clearLEEMLines)
        lineprofileMenu.addAction(self.clearLEEMLineProfileAction)

        self.extractLEEMLineProfileAction = QtWidgets.QAction("Extract Line Profile", self)
        self.extractLEEMLineProfileAction.triggered.connect(self.viewer.extractLEEMLineProfiles)
        self.extractLEEMLineProfileAction.setEnabled(self.viewer.LEEMLineProfileEnabled)
        lineprofileMenu.addAction(self.extractLEEMLineProfileAction)

        self.toggleLEEMReflectivityAction = QtWidgets.QAction("Toggle Reflectivty", self)
        self.toggleLEEMReflectivityAction.triggered.connect(lambda: self.viewer.toggleReflectivity(data="LEEM"))
        LEEMMenu.addAction(self.toggleLEEMReflectivityAction)

        # LEED menu
        self.extractAction = QtWidgets.QAction("Extract I(V)", self)
        # extractAction.setShortcut("Ctrl-E")
        self.extractAction.triggered.connect(self.viewer.processLEEDIV)
        LEEDMenu.addAction(self.extractAction)

        self.clearAction = QtWidgets.QAction("Clear I(V)", self)
        self.clearAction.triggered.connect(self.viewer.clearLEEDIV)
        LEEDMenu.addAction(self.clearAction)

        self.averageIVAction = QtWidgets.QAction("Average IV", self)
        self.averageIVAction.triggered.connect(self.viewer.averageLEEDIV)
        LEEDMenu.addAction(self.averageIVAction)

        self.autoBackground = QtWidgets.QAction("Auto Background Selection", self)
        self.autoBackground.triggered.connect(self.viewer.LEEDAutoBackgroundSelection2)
        LEEDMenu.addAction(self.autoBackground)

        self.undoSelection = QtWidgets.QAction("Undo Selection", self)
        self.undoSelection.triggered.connect(self.viewer.undoLEEDSelection)
        LEEDMenu.addAction(self.undoSelection)

        self.toggleLEEDReflectivityAction = QtWidgets.QAction("Toggle Reflectivty", self)
        self.toggleLEEDReflectivityAction.triggered.connect(lambda: self.viewer.toggleReflectivity(data="LEED"))
        # LEEDMenu.addAction(self.toggleLEEDReflectivityAction)  # TODO: If this feature is added; enable menu action

        # Help menu
        self.genConfigInfoFileAction = QtWidgets.QAction("Generate User Config File", self)
        self.genConfigInfoFileAction.triggered.connect(self.viewer.generateConfigInfo)
        helpMenu.addAction(self.genConfigInfoFileAction)


        #### Image menu ######
        self.adjustAction = QtWidgets.QAction("Adjust Loaded Image", self)
        self.adjustAction.triggered.connect(self.viewer.adjustLoadedImage)
        imageMenu.addAction(self.adjustAction)



    @staticmethod
    def quit():
        """."""
        QtWidgets.QApplication.instance().quit()


class Viewer(QtWidgets.QWidget):
    """Main Container for Viewing LEEM and LEED data."""


    def __init__(self, parent=None):
        """Initialize main LEEM and LEED data stucts.

        Setup Tab structure
        Connect key/mouse event hooks to image plot widgets
        """
        super(QtWidgets.QWidget, self).__init__(parent=parent)
        self.initData()
        self.layout = QtWidgets.QVBoxLayout()

        self.tabs = QtWidgets.QTabWidget()
        self.LEEMTab = QtWidgets.QWidget()
        self.LEEDTab = QtWidgets.QWidget()
        self.ConfigTab = QtWidgets.QWidget()
        self.initLEEMTab()
        self.initLEEDTab()
        self.initConfigTab()
        self.tabs.addTab(self.LEEMTab, "LEEM-I(V)")
        self.initLEEMEventHooks()
        self.initLEEDEventHooks()
        self.tabs.addTab(self.LEEDTab, "LEED-I(V)")
        self.tabs.addTab(self.ConfigTab, "Config")

        self

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)
        self.show()

    def initData(self):
        """Specific initialization.

        Certain attributes require initialization so that their signals
        can be accessed. Others need to be initialized since many methods
        rely on checking if certain structures contain data.
        """
        self.staticLEEMplot = pg.PlotWidget()  # not displayed until User clicks LEEM image
        self.staticLEEMplot.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # container for circular patches indicating locations of User clicks in LEEM image
        self.LEEMcircs = []
        self.LEEMclicks = 0

        # container for QRectF patches to be drawn atop LEEDimage
        self.LEEDrects = []  # stored as tuple (rect, pen)
        self.LEEDclicks = 0
        self.LEEDclickpos = []  # container for position of LEED clicks in array coordinate system
        self.boxrad = 20  # USER configurable setting for LEED integration window: 2*boxrad x 2*boxrad

        self.threads = []  # container for QThread objects used for outputting files

        self.colors = Palette().color_palette
        self.qcolors = Palette().qcolors
        self.leemdat = LeemData()
        self.leeddat = LeedData()
        self.LEEMselections = []  # store coords of leem clicks in array coordinates
        self.LEEDclickpos = []  # store coords of leed clicks in array coordinates
        self.LEEMRects = []
        self.LEEMRectWindowEnabled = False
        self.LEEMLineProfileEnabled = False
        self.LEEMLines = []  # container for QGraphicsLineItem objects

        self.smoothLEEDplot = False
        self.smoothLEEMplot = False
        self.smoothLEEDoutput = False
        self.smoothLEEMoutput = False
        self.LEEDWindowType = 'flat'
        self.LEEMWindowType = 'flat'
        self.LEEDWindowLen = 4
        self.LEEMWindowLen = 4

        # I(V) plot default values
        self.LEEM_Linewidth = 4  # default value
        self.LEED_Linewidth = 4  # default value

        self.LEEDAverageIV = []
        self.outputLEEDAverage = False

        self.LEEDBackgroundrects = []
        self.LEEDBackgroundcenters = []  # container of tuples (xa, ya) in array coordinates
        self.num_background_per_beam = 6

        self.exp = None  # overwritten on load with Experiment object
        self.hasdisplayedLEEMdata = False
        self.hasdisplayedLEEDdata = False
        self.LEEM_tab_is_PEEM = False  # flag to indicate display of PEEM instead of LEEM data
        self.LEED_tab_active_exp = None
        self.LEEM_tab_active_exp = None

        self.currentLEEMTime = False  # flag for plotting LEEM I(t) instead of I(V)
        self.currentLEEDTime = False  # flag for plotting LEED I(t) instead of I(V)

        # flags for plotting reflectivty rathet than intensity
        self.rescaleLEEMIntensity = False
        self.rescaleLEEDIntensity = False
        self.curLEEMIndex = 0
        self.curLEEDIndex = 0
        dummydata = np.zeros((10, 10))
        self.LEEMimage = pg.ImageItem(dummydata)  # required for signal hook
        self.LEEDimage = pg.ImageItem(dummydata)
        # self.LEEDimage = pg.ImageItem(dummydata)  # required for signal hook
        self.labelStyle = {'color': '#FFFFFF',
                           'font-size': '16pt'}
        self.boxrad = 20

    def initLEEMTab(self):
        """Setup Layout of LEEM Tab."""
        self.LEEMTabLayout = QtWidgets.QHBoxLayout()
        imvbox = QtWidgets.QVBoxLayout()
        imtitlehbox = QtWidgets.QHBoxLayout()

        self.LEEMimtitle = QtWidgets.QLabel("LEEM Real Space Image")
        imtitlehbox.addStretch()
        imtitlehbox.addWidget(self.LEEMimtitle)
        imtitlehbox.addStretch()
        imvbox.addLayout(imtitlehbox)
        self.LEEMimageplotwidget = pg.PlotWidget()
        # disable mouse pan on left click
        self.LEEMimageplotwidget.getPlotItem().getViewBox().setMouseEnabled(x=False, y=False)

        self.LEEMimageplotwidget.hideAxis("bottom")
        self.LEEMimageplotwidget.hideAxis("left")
        # self.LEEMimageplotwidget.setTitle("LEEM Real Space Image",
        #                                  size='18pt', color='#FFFFFF')
        imvbox.addWidget(self.LEEMimageplotwidget)
        self.LEEMTabLayout.addLayout(imvbox)

        ivvbox = QtWidgets.QVBoxLayout()
        titlehbox = QtWidgets.QHBoxLayout()
        self.LEEMIVTitle = QtWidgets.QLabel("LEEM-I(V)")
        titlehbox.addStretch()
        titlehbox.addWidget(self.LEEMIVTitle)
        titlehbox.addStretch()
        ivvbox.addLayout(titlehbox)

        self.LEEMivplotwidget = pg.PlotWidget()
        self.LEEMivplotwidget.setLabel('bottom',
                                       'Energy', units='eV',
                                       **self.labelStyle)
        self.LEEMivplotwidget.setLabel('left',
                                       'Intensity', units='arb units',
                                       **self.labelStyle)
        yaxis = self.LEEMivplotwidget.getAxis("left")
        # y axis is 'arbitrary units'; we don't want kilo or mega arbitrary units etc...
        yaxis.enableAutoSIPrefix(False)

        self.LEEMimageplotwidget.addItem(self.LEEMimage)
        ivvbox.addWidget(self.LEEMivplotwidget)
        self.LEEMTabLayout.addLayout(ivvbox)
        self.LEEMTab.setLayout(self.LEEMTabLayout)

    def initConfigTab(self):
        """Setup Layout of Config Tab."""
        configTabVBox = QtWidgets.QVBoxLayout()

        # smooth settings
        smoothLEEDVBox = QtWidgets.QVBoxLayout()
        smoothColumn = QtWidgets.QHBoxLayout()
        # smoothGroupBox = QtWidgets.QGroupBox()

        # LEED
        self.LEEDSettingsLabel = QtWidgets.QLabel("LEED Data Smoothing Settings")
        smoothLEEDVBox.addWidget(self.LEEDSettingsLabel)

        self.smoothLEEDCheckBox = QtWidgets.QCheckBox()
        self.smoothLEEDCheckBox.setText("Enable Smoothing")
        self.smoothLEEDCheckBox.stateChanged.connect(lambda: self.smoothing_statechange(data='LEED'))
        smoothLEEDVBox.addWidget(self.smoothLEEDCheckBox)

        window_LEED_hbox = QtWidgets.QHBoxLayout()
        self.LEED_window_label = QtWidgets.QLabel("Select Window Type")
        self.smooth_LEED_window_type_menu = QtWidgets.QComboBox()
        self.smooth_LEED_window_type_menu.addItem("Flat")
        self.smooth_LEED_window_type_menu.addItem("Hanning")
        self.smooth_LEED_window_type_menu.addItem("Hamming")
        self.smooth_LEED_window_type_menu.addItem("Bartlett")
        self.smooth_LEED_window_type_menu.addItem("Blackman")
        window_LEED_hbox.addWidget(self.LEED_window_label)
        window_LEED_hbox.addWidget(self.smooth_LEED_window_type_menu)
        smoothLEEDVBox.addLayout(window_LEED_hbox)

        LEED_window_len_box = QtWidgets.QHBoxLayout()
        self.LEED_window_len_label = QtWidgets.QLabel("Enter Window Length [even integer]")
        self.LEED_window_len_entry = QtWidgets.QLineEdit()

        LEED_window_len_box.addWidget(self.LEED_window_len_label)
        LEED_window_len_box.addWidget(self.LEED_window_len_entry)
        smoothLEEDVBox.addLayout(LEED_window_len_box)

        self.apply_settings_LEED_button = QtWidgets.QPushButton("Apply Smoothing Settings", self)
        self.apply_settings_LEED_button.clicked.connect(lambda: self.validate_smoothing_settings(but='LEED'))
        smoothLEEDVBox.addWidget(self.apply_settings_LEED_button)

        smoothColumn.addLayout(smoothLEEDVBox)
        smoothColumn.addStretch()
        smoothColumn.addWidget(self.v_line())
        smoothColumn.addStretch()

        # LEEM
        smooth_LEEM_vbox = QtWidgets.QVBoxLayout()
        smooth_group = QtWidgets.QGroupBox()

        self.LEEM_settings_label = QtWidgets.QLabel("LEEM Data Smoothing Settings")
        smooth_LEEM_vbox.addWidget(self.LEEM_settings_label)

        self.smoothLEEMCheckBox = QtWidgets.QCheckBox()
        self.smoothLEEMCheckBox.setText("Enable Smoothing")
        self.smoothLEEMCheckBox.stateChanged.connect(lambda: self.smoothing_statechange(data='LEEM'))
        smooth_LEEM_vbox.addWidget(self.smoothLEEMCheckBox)

        window_LEEM_hbox = QtWidgets.QHBoxLayout()
        self.LEEM_window_label = QtWidgets.QLabel("Select Window Type")
        self.smooth_LEEM_window_type_menu = QtWidgets.QComboBox()
        self.smooth_LEEM_window_type_menu.addItem("Flat")
        self.smooth_LEEM_window_type_menu.addItem("Hanning")
        self.smooth_LEEM_window_type_menu.addItem("Hamming")
        self.smooth_LEEM_window_type_menu.addItem("Bartlett")
        self.smooth_LEEM_window_type_menu.addItem("Blackman")
        window_LEEM_hbox.addWidget(self.LEEM_window_label)
        window_LEEM_hbox.addWidget(self.smooth_LEEM_window_type_menu)
        smooth_LEEM_vbox.addLayout(window_LEEM_hbox)

        LEEM_window_len_box = QtWidgets.QHBoxLayout()
        self.LEEM_window_len_label = QtWidgets.QLabel("Enter Window Length [even integer]")
        self.LEEM_window_len_entry = QtWidgets.QLineEdit()

        LEEM_window_len_box.addWidget(self.LEEM_window_len_label)
        LEEM_window_len_box.addWidget(self.LEEM_window_len_entry)
        smooth_LEEM_vbox.addLayout(LEEM_window_len_box)

        self.apply_settings_LEEM_button = QtWidgets.QPushButton("Apply Smoothing Settings", self)
        self.apply_settings_LEEM_button.clicked.connect(lambda: self.validate_smoothing_settings(but="LEEM"))
        smooth_LEEM_vbox.addWidget(self.apply_settings_LEEM_button)

        smoothColumn.addLayout(smooth_LEEM_vbox)
        smooth_group.setLayout(smoothColumn)

        configTabVBox.addWidget(smooth_group)
        configTabVBox.addWidget(self.h_line())
        """
        # LEED rect  size settings
        RectSettingGroupBox = QtWidgets.QGroupBox()
        LEEDRectSettingHBox = QtWidgets.QHBoxLayout()
        LEEDRectSettingVBox = QtWidgets.QVBoxLayout()
        RectSettingLabel = QtWidgets.QLabel("Enter LEED Window Side Length [even integer]")
        LEEDRectSettingVBox.addWidget(RectSettingLabel)
        self.LEEDRectEntry = QtWidgets.QLineEdit()
        self.LEEDRectEntry.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                         QtWidgets.QSizePolicy.Minimum)
        entryHBox = QtWidgets.QHBoxLayout()
        entryHBox.addWidget(self.LEEDRectEntry)
        entryHBox.addStretch()
        self.LEEDRectApplyButton = QtWidgets.QPushButton("Apply Window Size", self)
        self.LEEDRectApplyButton.clicked.connect(self.apply_LEED_window_size)
        RectButtonHBox = QtWidgets.QHBoxLayout()
        RectButtonHBox.addWidget(self.LEEDRectApplyButton)
        RectButtonHBox.addStretch()

        LEEDRectSettingVBox.addLayout(entryHBox)
        LEEDRectSettingVBox.addLayout(RectButtonHBox)

        LEEDRectSettingHBox.addLayout(LEEDRectSettingVBox)
        LEEDRectSettingHBox.addStretch()

        RectSettingGroupBox.setLayout(LEEDRectSettingHBox)
        configTabVBox.addWidget(RectSettingGroupBox)

        # LEED Average Settings
        AverageSettingGroupBox = QtWidgets.QGroupBox()
        LEEDAverageSettingHBox = QtWidgets.QHBoxLayout()
        LEEDAverageSettingVBox = QtWidgets.QVBoxLayout()
        AverageSettingLabel = QtWidgets.QLabel("Enable LEED Average for File Output")
        LEEDAverageSettingVBox.addWidget(AverageSettingLabel)
        self.LEEDAverageToggleBox = QtWidgets.QCheckBox()
        self.LEEDAverageToggleBox.stateChanged.connect(self.averageStateChanged)
        LEEDAverageSettingVBox.addWidget(self.LEEDAverageToggleBox)
        LEEDAverageSettingHBox.addLayout(LEEDAverageSettingVBox)
        LEEDAverageSettingHBox.addStretch()
        AverageSettingGroupBox.setLayout(LEEDAverageSettingHBox)
        """

        # LEED Rect Size and File Output settings
        LEED_settings_groupbox = QtWidgets.QGroupBox()
        LEED_settings_hbox = QtWidgets.QHBoxLayout()

        LEED_window_size_vbox = QtWidgets.QVBoxLayout()
        LEED_file_output_vbox = QtWidgets.QVBoxLayout()

        LEED_rect_setting_label = QtWidgets.QLabel("Enter LEED Window Side Length [even integer]")
        LEED_window_size_vbox.addWidget(LEED_rect_setting_label)
        self.LEED_rect_setting_entry = QtWidgets.QLineEdit()
        self.LEED_rect_setting_entry.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                                   QtWidgets.QSizePolicy.Minimum)
        LEED_window_size_vbox.addWidget(self.LEED_rect_setting_entry)
        self.LEED_rect_setting_button = QtWidgets.QPushButton("Apply Window Size", self)
        self.LEED_rect_setting_button.clicked.connect(self.apply_LEED_window_size)
        LEED_window_size_vbox.addWidget(self.LEED_rect_setting_button)

        LEED_settings_hbox.addLayout(LEED_window_size_vbox)
        LEED_settings_hbox.addStretch()
        LEED_settings_hbox.addWidget(self.v_line())
        LEED_settings_hbox.addStretch()

        LEED_file_output_label = QtWidgets.QLabel("Enable LEED Average for File Output")
        LEED_file_output_vbox.addWidget(LEED_file_output_label)
        self.LEED_file_output_checkbox = QtWidgets.QCheckBox()
        self.LEED_file_output_checkbox.stateChanged.connect(self.averageStateChanged)
        LEED_file_output_vbox.addWidget(self.LEED_file_output_checkbox)
        LEED_settings_hbox.addLayout(LEED_file_output_vbox)
        LEED_settings_groupbox.setLayout(LEED_settings_hbox)

        configTabVBox.addWidget(LEED_settings_groupbox)
        configTabVBox.addWidget(self.h_line())
        """
        # crosshair settings
        crosshairSettingsGroupBox = QtWidgets.QGroupBox()
        crosshairHBox = QtWidgets.QHBoxLayout()
        crosshairVBox = QtWidgets.QVBoxLayout()
        crosshairLabel = QtWidgets.QLabel("Enter LEEM crosshair line width [int]")
        crosshairVBox.addWidget(crosshairLabel)
        self.crosshairText = QtWidgets.QLineEdit()
        self.crosshairText.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                         QtWidgets.QSizePolicy.Minimum)
        crosshairVBox.addWidget(self.crosshairText)
        buttonHbox = QtWidgets.QHBoxLayout()
        self.apply_settings_crosshair_button = QtWidgets.QPushButton("Apply Settings", self)
        self.apply_settings_crosshair_button.clicked.connect(self.validateWidth)
        buttonHbox.addWidget(self.apply_settings_crosshair_button)
        crosshairVBox.addLayout(buttonHbox)
        crosshairHBox.addLayout(crosshairVBox)
        crosshairHBox.addStretch()
        crosshairSettingsGroupBox.setLayout(crosshairHBox)

        configTabVBox.addWidget(crosshairSettingsGroupBox)
        configTabVBox.addWidget(self.h_line())

        LEEM_Linewidth_GroupBox = QtWidgets.QGroupBox()
        LEEM_Linewidth_HBox = QtWidgets.QHBoxLayout()
        LEEM_Linewidth_VBox = QtWidgets.QVBoxLayout()
        LEEM_Linewidth_Label = QtWidgets.QLabel("Enter LEEM I(V) plot linewidth [int]")
        LEEM_Linewidth_VBox.addWidget(LEEM_Linewidth_Label)
        self.LEEM_Linewidth_Text = QtWidgets.QLineEdit()
        self.LEEM_Linewidth_Text.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                               QtWidgets.QSizePolicy.Minimum)
        LEEM_Linewidth_VBox.addWidget(self.LEEM_Linewidth_Text)
        LEEM_Linewidth_Button_HBox = QtWidgets.QHBoxLayout()
        self.LEEM_Linewidth_Button = QtWidgets.QPushButton("Apply Settings", self)
        self.LEEM_Linewidth_Button.clicked.connect(self.validateLEEMLinewidth)
        LEEM_Linewidth_Button_HBox.addWidget(self.LEEM_Linewidth_Button)
        LEEM_Linewidth_VBox.addLayout(LEEM_Linewidth_Button_HBox)
        LEEM_Linewidth_HBox.addLayout(LEEM_Linewidth_VBox)
        LEEM_Linewidth_HBox.addStretch()
        LEEM_Linewidth_GroupBox.setLayout(LEEM_Linewidth_HBox)
        configTabVBox.addWidget(LEEM_Linewidth_GroupBox)
        """
        # Misc LEEM Settings
        LEEM_settings_groupbox = QtWidgets.QGroupBox()
        LEEM_settings_hbox = QtWidgets.QHBoxLayout()
        LEEM_crosshair_vbox = QtWidgets.QVBoxLayout()

        crosshair_label = QtWidgets.QLabel("Enter LEEM crosshair line width [int]")
        LEEM_crosshair_vbox.addWidget(crosshair_label)
        self.crosshair_text = QtWidgets.QLineEdit()
        self.crosshair_text.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                          QtWidgets.QSizePolicy.Minimum)
        LEEM_crosshair_vbox.addWidget(self.crosshair_text)
        self.apply_settings_crosshair_button = QtWidgets.QPushButton("Apply Settings", self)
        self.apply_settings_crosshair_button.clicked.connect(self.validateWidth)
        LEEM_crosshair_vbox.addWidget(self.apply_settings_crosshair_button)
        LEEM_settings_hbox.addLayout(LEEM_crosshair_vbox)
        LEEM_settings_hbox.addStretch()
        LEEM_settings_hbox.addWidget(self.v_line())
        LEEM_settings_hbox.addStretch()

        LEEM_plot_settings_vbox = QtWidgets.QVBoxLayout()
        LEEM_IV_plot_linewidth_label = QtWidgets.QLabel("Enter LEEM I(V) plot linewidth [int]")
        LEEM_plot_settings_vbox.addWidget(LEEM_IV_plot_linewidth_label)
        self.LEEM_linewidth_text = QtWidgets.QLineEdit()
        self.LEEM_linewidth_text.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                               QtWidgets.QSizePolicy.Minimum)
        LEEM_plot_settings_vbox.addWidget(self.LEEM_linewidth_text)
        self.LEEM_linewidth_button = QtWidgets.QPushButton("Apply Settings", self)
        self.LEEM_linewidth_button.clicked.connect(self.validateLEEMLinewidth)
        LEEM_plot_settings_vbox.addWidget(self.LEEM_linewidth_button)
        LEEM_settings_hbox.addLayout(LEEM_plot_settings_vbox)
        LEEM_settings_groupbox.setLayout(LEEM_settings_hbox)

        configTabVBox.addWidget(LEEM_settings_groupbox)
        configTabVBox.addWidget(self.h_line())
        configTabVBox.addStretch()


#start of patch config settings -- add settings into config tab and connect 
        #want a input text box for int
        LEEM_patch_settings_groupbox = QtWidgets.QGroupBox()#create group area for new settings
        LEEM_patch_settings_hbox = QtWidgets.QHBoxLayout()
        LEEM_patch_vbox = QtWidgets.QVBoxLayout()#apply vbox into hbox settings later

        patch_label = QtWidgets.QLabel("Enter LEEM patch width [even int]")
        LEEM_patch_vbox.addWidget(patch_label)# add label 
        self.patch_text = QtWidgets.QLineEdit()#text box
        self.patch_text.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                      QtWidgets.QSizePolicy.Minimum)
        LEEM_patch_vbox.addWidget(self.patch_text)#adds widget to show on gui
        #button
        self.apply_patch_settings_button = QtWidgets.QPushButton("Apply Patch Settings", self)
        self.apply_patch_settings_button.clicked.connect(self.validatePatchWidth)
        #call def validatePatchWidth - line 800s
        LEEM_patch_vbox.addWidget(self.apply_patch_settings_button)#^ apply settings button

        LEEM_patch_settings_hbox.addLayout(LEEM_patch_vbox)#adds patch settings on config area
        LEEM_patch_settings_hbox.addStretch()
        LEEM_patch_settings_hbox.addWidget(self.v_line())# vertical line
        LEEM_patch_settings_hbox.addStretch()
        LEEM_patch_settings_groupbox.setLayout(LEEM_patch_settings_hbox)# have to connect hbox to
        #settings and vbox to hbox^ this sets the layout for everything ** but leaves long text box
        
        configTabVBox.addWidget(LEEM_patch_settings_groupbox)
        self.ConfigTab.setLayout(configTabVBox)


    def initLEEDTab(self):
        """Setup Layout of LEED Tab."""
        self.LEEDTabLayout = QtWidgets.QHBoxLayout()

        self.imvbox = QtWidgets.QVBoxLayout()
        self.ivvbox = QtWidgets.QVBoxLayout()

        imtitlehbox = QtWidgets.QHBoxLayout()
        self.LEEDTitle = QtWidgets.QLabel("Reciprocal Space LEED Image")
        imtitlehbox.addStretch()
        imtitlehbox.addWidget(self.LEEDTitle)
        imtitlehbox.addStretch()
        self.imvbox.addLayout(imtitlehbox)

        self.LEEDimagewidget = pg.PlotWidget()
        # disable mouse pan on left click
        self.LEEDimagewidget.getPlotItem().getViewBox().setMouseEnabled(x=False, y=False)
        self.LEEDimagewidget.hideAxis("bottom")
        self.LEEDimagewidget.hideAxis("left")
        self.LEEDimagewidget.addItem(self.LEEDimage)  # dummy data
        self.imvbox.addWidget(self.LEEDimagewidget)
        self.LEEDTabLayout.addLayout(self.imvbox)

        ivtitlehbox = QtWidgets.QHBoxLayout()
        ivtitlehbox.addStretch()
        self.LEEDIVTitle = QtWidgets.QLabel("LEED-I(V)")
        ivtitlehbox.addWidget(self.LEEDIVTitle)
        ivtitlehbox.addStretch()
        self.ivvbox.addLayout(ivtitlehbox)
        self.LEEDivplotwidget = pg.PlotWidget()
        self.LEEDivplotwidget.setLabel('bottom',
                                       'Energy', units='eV',
                                       **self.labelStyle)
        self.LEEDivplotwidget.setLabel('left',
                                       'Intensity', units='arb units',
                                       **self.labelStyle)
        yaxis = self.LEEDivplotwidget.getAxis("left")
        # y axis is 'arbitrary units'; we don't want kilo or mega arbitrary units etc...
        yaxis.enableAutoSIPrefix(False)

        self.ivvbox.addWidget(self.LEEDivplotwidget)
        self.LEEDTabLayout.addLayout(self.ivvbox)
        self.LEEDTab.setLayout(self.LEEDTabLayout)

    def initLEEMEventHooks(self):
        """Setup event hooks for mouse click and mouse move.

        Signals beginning with 'sig' are defined by pyqtgraph
        as opposed to being defined in Qt.
        """
        # LEEM #
        # signals
        self.sigmcLEEM = self.LEEMimage.scene().sigMouseClicked
        self.sigmmvLEEM = self.LEEMimage.scene().sigMouseMoved

        self.sigmcLEEM.connect(self.handleLEEMClick)
        self.sigmmvLEEM.connect(self.handleLEEMMouseMoved)

    def initLEEDEventHooks(self):
        """Setup event hooks for mouse click in LEEDimagewidget."""
        self.sigmcLEED = self.LEEDimage.scene().sigMouseClicked
        self.sigmcLEED.connect(self.handleLEEDClick)

    @staticmethod
    def h_line():
        """Convienience to quickly add UI separators."""
        f = QtWidgets.QFrame()
        f.setFrameShape(QtWidgets.QFrame.HLine)
        f.setFrameShadow(QtWidgets.QFrame.Sunken)
        return f

    @staticmethod
    def v_line():
        """Convienience to quickly add UI separators."""
        f = QtWidgets.QFrame()
        f.setFrameShape(QtWidgets.QFrame.VLine)
        f.setFrameShadow(QtWidgets.QFrame.Sunken)
        return f

    def generateConfigInfo(self):
        """Call configinfo.output_environment_config() but push output to separate thread."""
        self.thread = WorkerThread(task="GEN_CONFIG_INFO")
        try:
            self.thread.disconnect()
        except TypeError:
            # nothing to disconnect
            pass
        self.thread.start()


    def validateWidth(self):
        """Check user input and set crosshair line width."""
        w = self.crosshair_text.text()
        try:
            w = int(w)
        except ValueError:
            print("Error: line width must be entered as an integer > 0.")
            return
        if w <= 0:
            print("Error: line width must be entered as an integer > 0.")
            return
        else:
            try:
                self.crosshair.setLineWidth(w)
            except AttributeError:
                # have not instantiated crosshair yet
                self.crosshair = ExtendedCrossHair()
                self.crosshair.setLineWidth(w)
                self.LEEMimageplotwidget.addItem(self.crosshair.hline,
                                                 ignoreBounds=True)
                self.LEEMimageplotwidget.addItem(self.crosshair.vline,
                                                 ignoreBounds=True)

    def validateLEEMLinewidth(self):
        """Ensure user input for line width is positive integer."""
        lw = self.LEEM_linewidth_text.text()
        try:
            lw = int(lw)
        except ValueError:
            print("Error: line width must be entered as an integer > 0.")
            return
        if lw <= 0:
            print("Error: line width must be entered as an integer > 0.")
            return
        if lw > 10:
            print("Warning: Setting plot linewidth > 10 may cause visibility problems. Defaulting to 10.")
            lw = 10
        self.LEEM_Linewidth = lw


# define self.validatepatch -- print errors if not decimal- instantiation of self.validatepatch
    def validatePatchWidth(self,event):
        """Ensure user input for patch width positive int"""
        pw = self.patch_text.text()
        try:
            pw = int(pw)
        except ValueError:
            print("ERROR: patch width must be entered as an integer > 0")
            return
        if pw %2 != 0:
            print("ERROR: patch width must be even for circular selection area")
            return
        if pw <=0:
            print("ERROR: patch width must be entered as an integer > 0")
            return
        else:
            try:
                self.patch.setPatchWidth(pw)
            except AttributeError:#patch size not instantiated - default to 8
                self.handleLEEMClick
        print ("Patch Width set to ", pw)

                
    def createExperimentConfigFile(self):
        """Get User settings and generate a .yaml file."""
        self.yamlwidget = ExperimentYAMLOutput()
        self.yamlwidget.userData.connect(self.recieveYAMLSettings)


    @QtCore.pyqtSlot(object)
    def recieveYAMLSettings(self, settings):
        """Recieve user settings from YAML widget."""
        # self.userYAMLSettings = settings
        # print(settings)
        print("Recieved user Experiment settings.")
        self.thread = WorkerThread(task="CREATE_YAML", settings=settings)
        try:
            self.thread.disconnect()
        except TypeError:
            pass
        self.thread.yamlFileOutput.connect(self.experimentConfigWritten)
        self.thread.start()

    @staticmethod
    @QtCore.pyqtSlot(bool)
    def experimentConfigWritten(output):
        """Signal successful file write."""
        if output:
            print("Experiment configuration file successfully output.")
        else:
            print("Failed to write YAML file.")

    def load_experiment(self):
        """Query User for YAML config file to load experiment settings.

        Adapted from my other project https://www.github.com/mgrady3/pLEASE
        """
        yamlFilter = "YAML (*.yaml);;YML (*.yml);;All Files (*)"
        homeDir = os.getenv("HOME")
        caption = "Select YAML Experiment Config File"
        fileName = QtWidgets.QFileDialog.getOpenFileName(self, caption,
                                                     directory=homeDir,
                                                     filter=yamlFilter)
        ###^^ fileName was QtGui.QFileDialog but wasnt working so changed to widgets- success
        if isinstance(fileName, str):
            config = fileName  # string path to .yaml or .yml config file
        elif isinstance(fileName, tuple):
            try:
                config = fileName[0]
            except IndexError:
                print('No Config file found.')
                print('Please Select a directory with a .yaml file.')
                print('Loading Canceled ...')
                return
        else:
            print('No Config file found.')
            print('Please Select a directory with a .yaml file.')
            print('Loading Canceled ...')
            return
        if config == '':
            print("Loading canceled")
            return

        if self.exp is not None:
            # already loaded an experiment; save old experiment then load new
            self.prev_exp = self.exp

        self.exp = Experiment()
        # path_to_config = os.path.join(new_dir, config)
        self.exp.fromFile(config)
        print("New Data Path loaded from file: {}".format(self.exp.path))
        print("Loaded the following settings:")

        yaml.dump(self.exp.loaded_settings, stream=sys.stdout)

        if self.exp.exp_type == 'LEEM':
            self.load_LEEM_experiment()
        elif self.exp.exp_type == 'LEED':
            self.load_LEED_experiment()
        elif self.exp.exp_type == 'PEEM':
            self.load_PEEM_experiment()
        else:
            print("Error: Unrecognized Experiment Type in YAML Config file")
            print("Valid Experiment Types for LiveViewer are LEEM, LEED")
            print("Please refer to Experiment.yaml for documentation.")
            return

    def load_LEEM_experiment(self):
        """Load LEEM data from settings described by YAML config file."""
        if self.exp is None:
            return
        self.LEEM_tab_active_exp = self.exp
        self.tabs.setCurrentIndex(0)
        if str(self.LEEMimtitle.text) != "LEEM Real Space Image":
            # reset title if it was changed from PEEM data
            self.LEEMimtitle.setText("LEEM Real Space Image")

        if self.LEEM_tab_active_exp.time:
            self.LEEMIVTitle.setText("LEEM I(t)")
        else:
            self.LEEMIVTitle.setText("LEEM I(V)")

        if self.hasdisplayedLEEMdata:
            # clear old data - This fixes bug witih loading data with different sizes.
            self.LEEMimageplotwidget.clear()
            self.LEEMivplotwidget.clear()
        if self.exp.time:
            # This is an I(t) data set
            print("Loading data as Time Series")
            self.LEEMivplotwidget.setLabel('bottom', 'Time', units='s', **self.labelStyle)
            self.currentLEEMTime = True
        else:
            self.LEEMivplotwidget.setLabel('bottom', 'Energy', units='eV', **self.labelStyle)
            self.currentLEEMTime = False

        if self.exp.data_type.lower() == 'raw':
            try:
                # use settings from self.sexp
                self.thread = WorkerThread(task='LOAD_LEEM',
                                           path=str(self.exp.path),
                                           imht=self.exp.imh,
                                           imwd=self.exp.imw,
                                           bits=self.exp.bit,
                                           byte=self.exp.byte_order)
                try:
                    self.thread.disconnect()
                except TypeError:
                    pass  # no signals connected, that's OK, continue as needed
                self.thread.connectOutputSignal(self.retrieve_LEEM_data)
                self.thread.finished.connect(self.update_LEEM_img_after_load)
                self.thread.start()
            except ValueError:
                print("Error loading LEEM Experiment:")
                print("Please Verify Experiment Config Settings.")
                return

        elif self.exp.data_type.lower() == 'image':
            try:
                self.thread = WorkerThread(task='LOAD_LEEM_IMAGES',
                                           path=self.exp.path,
                                           ext=self.exp.ext)
                try:
                    self.thread.disconnect()
                except TypeError:
                    pass  # no signals connected, that's OK, continue as needed
                self.thread.connectOutputSignal(self.retrieve_LEEM_data)
                self.thread.finished.connect(self.update_LEEM_img_after_load)
                self.thread.start()
            except ValueError:
                print('Error loading LEEM data from images.')
                print('Please check YAML experiment config file')
                print('Required parameters: path, ext')
                print('Check for valid data path')
                print('Check file extensions: \'.tif\' and \'.png\'.')
                return

    def load_LEED_experiment(self):
        """Load LEED data from settings described by YAML config file."""
        if self.exp is None:
            return
        self.LEED_tab_active_exp = self.exp
        self.tabs.setCurrentIndex(1)

        if self.hasdisplayedLEEDdata:
            # self.LEEDimageplotwidget.getPlotItem().clear()
            self.LEEDivplotwidget.getPlotItem().clear()
            self.LEEDimagewidget.clear()
        if self.exp.time:
            # This is an I(t) data set
            print("Loading data as Time Series")
            self.LEEDivplotwidget.setLabel('bottom', 'Time', units='s', **self.labelStyle)
            self.currentLEEDTime = True
        if self.exp.data_type.lower() == 'raw':
            try:
                # use settings from self.exp
                self.thread = WorkerThread(task='LOAD_LEED',
                                           path=str(self.exp.path),
                                           imht=self.exp.imh,
                                           imwd=self.exp.imw,
                                           bits=self.exp.bit,
                                           byte=self.exp.byte_order)
                try:
                    self.thread.disconnect()
                except TypeError:
                    # no signal connections - this is OK
                    pass
                self.thread.connectOutputSignal(self.retrieve_LEED_data)
                self.thread.finished.connect(self.update_LEED_img_after_load)
                self.thread.start()
            except ValueError:
                print('Error Loading LEED Data: Please Recheck YAML Settings')
                return

        elif self.exp.data_type.lower() == 'image':
            try:
                self.thread = WorkerThread(task='LOAD_LEED_IMAGES',
                                           ext=self.exp.ext,
                                           path=self.exp.path,
                                           byte=self.exp.byte_order)
                try:
                    self.thread.disconnect()
                except TypeError:
                    # no signals were connected - this is OK
                    pass
                self.thread.connectOutputSignal(self.retrieve_LEED_data)
                self.thread.finished.connect(self.update_LEED_img_after_load)
                self.thread.start()
            except ValueError:
                print('Error Loading LEED Experiment from image files.')
                print('Please Check YAML settings in experiment config file')
                print('Required parameters: data path and data extension.')
                print('Valid data extenstions: \'.tif\', \'.png\', \'.jpg\'')
                return

    def load_PEEM_experiment(self):
        """Shim function to load PEEM images as ``LEEM'' data."""
        self.load_LEEM_experiment()
        if str(self.LEEMimtitle.text) != "PEEM Real Space Image":
            # set title to display PEEM data
            self.LEEMimtitle.setText("PEEM Real Space Image")
            if self.LEEM_tab_active_exp.time:
                self.LEEMIVTitle.setText("PEEM I(t)")
            else:
                self.LEEMIVTitle.setText("PEEM I(V)")

    def outputIV(self, datatype=None):
        """Output current I(V) plots as tab delimited text files.

        :param: datatype- String desginating either 'LEEM' or 'LEED' data to output
        """
        if datatype is None:
            return
        elif datatype == 'LEEM' and self.hasdisplayedLEEMdata and self.LEEMselections:
            outdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                                                options=QtWidgets.QFileDialog.ShowDirsOnly)
            try:
                outdir = outdir[0]
            except IndexError:
                print("Error selecting output file directory.")
                return
            outdir = str(outdir)  # cast from QString to string

            # Query User for output file name
            msg = "Enter name for output file(s)."
            outname = QtWidgets.QFileDialog.getSaveFileName(self, msg)

            try:
                outname = outname[0]
            except IndexError:
                print("Error getting output file name.")
                return
            outname = str(outname)  # cast from QString ot string
            if not outname:
                return  # User clicked cancel

            outfile = os.path.join(outdir, outname)
            if self.threads:
                # there are still thread objects in the container
                for thread in self.threads:
                    if not thread.isFinished():
                        print("Error: One or more threads has not finished file I/O ...")
                        return
            self.threads = []
            for idx, tup in enumerate(self.LEEMselections):
                outfile = os.path.join(outdir, outname+str(idx)+'.txt')
                x = tup[0]
                y = tup[1]
                ilist = self.leemdat.dat3d[y, x, :]
                if self.smoothLEEMoutput:
                    ilist = LF.smooth(ilist,
                                      window_len=self.LEEMWindowLen,
                                      window_type=self.LEEMWindowType)
                thread = WorkerThread(task='OUTPUT_TO_TEXT',
                                           elist=self.leemdat.elist,
                                           ilist=ilist,
                                           name=outfile)
                thread.finished.connect(self.output_complete)
                self.threads.append(thread)
                thread.start()

        elif datatype == 'LEED' and self.hasdisplayedLEEDdata and self.LEEDclickpos:
            if self.outputLEEDAverage and not self.LEEDAverageIV:
                # no average I(V) to output
                print("Warning: Configuration Setting to Output Average I(V) is enabled.")
                print("However, no average has been calculated.")
                print("Please disable averaging or average current I(V) curves.")
                return
            # Query User for output directory
            # PyQt5 - This method now returns a tuple - we want only the first element
            outdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                                                options=QtWidgets.QFileDialog.ShowDirsOnly)
            try:
                outdir = outdir[0]
            except IndexError:
                print("Error selecting output file directory.")
                return
            outdir = str(outdir)  # cast from QString to string

            # Query User for output file name
            msg = "Enter name for output file(s)."
            outname = QtWidgets.QFileDialog.getSaveFileName(self, msg)

            try:
                outname = outname[0]
            except IndexError:
                print("Error getting output file name.")
                return
            outname = str(outname)  # cast from QString ot string
            if not outname:
                return  # User clicked cancel

            outfile = os.path.join(outdir, outname)
            if self.threads:
                # there are still thread objects in the container
                for thread in self.threads:
                    if not thread.isFinished():
                        print("Error: One or more threads has not finished file I/O ...")
                        return
            self.threads = []
            if self.outputLEEDAverage and self.LEEDAverageIV:
                # output single curve
                outfile = os.path.join(outdir, outname+'.txt')
                if self.smoothLEEDoutput:
                    ilist = LF.smooth(self.LEEDAverageIV,
                                      window_len=self.LEEDWindowLen,
                                      window_type=self.LEEDWindowType)
                else:
                    ilist = self.LEEDAverageIV
                thread = WorkerThread(task='OUTPUT_TO_TEXT',
                                           elist=self.leeddat.elist,
                                           ilist=ilist,
                                           name=outfile)
                thread.finished.connect(self.output_complete)
                self.threads.append(thread)
                thread.start()
            else:
                # output multiple curves
                if len(self.LEEDrects) != len(self.LEEDclickpos):
                    print("Error: number of LEED widnows does not match number of Click coordinates.")
                    return
                if self.LEEDBackgroundrects and \
                   len(self.LEEDBackgroundcenters) != len(self.LEEDBackgroundrects):
                    print("Error: Mismatch in number of background selections.")
                    return

                if self.LEEDBackgroundrects and \
                   len(self.LEEDBackgroundrects) != 6 * len(self.LEEDrects):
                    print("Error: Mismatch between number of beam selections and number of background selections.")
                    return

                if self.LEEDBackgroundrects:
                    # There are background curves to output and all sizes match
                    for beam_idx, tup in enumerate(self.LEEDclickpos):
                        outfile = os.path.join(outdir, outname+'beam_'+str(beam_idx)+'.txt')
                        rad = int(self.LEEDrects[beam_idx][3])
                        x = int(tup[0])
                        y = int(tup[1])
                        int_window = self.leeddat.dat3d[y - rad:y + rad + 1,
                                                        x - rad:x + rad + 1, :]
                        # get average intensity per window
                        ilist = [img.sum()/(2*rad*2*rad) for img in np.rollaxis(int_window, 2)]
                        if self.smoothLEEDoutput:
                            ilist = LF.smooth(ilist,
                                              window_len=self.LEEDWindowLen,
                                              window_type=self.LEEDWindowType)
                        thread = WorkerThread(task='OUTPUT_TO_TEXT',
                                                   elist=self.leeddat.elist,
                                                   ilist=ilist,
                                                   name=outfile)
                        thread.finished.connect(self.output_complete)
                        self.threads.append(thread)
                        thread.start()
                        for idx, tup in enumerate(self.LEEDBackgroundcenters[beam_idx:
                                                                             beam_idx+self.num_background_per_beam]):
                            outfile = os.path.join(outdir, outname+'beam_'+str(beam_idx)+'bkgd_'+str(idx)+'.txt')
                            rad = int(self.LEEDBackgroundrects[idx][3])
                            x = int(tup[0])
                            y = int(tup[1])
                            int_window = self.leeddat.dat3d[y - rad:y + rad + 1,
                                                            x - rad:x + rad + 1, :]
                            # get average intensity per window
                            ilist = [img.sum()/(2*rad*2*rad) for img in np.rollaxis(int_window, 2)]
                            if self.smoothLEEDoutput:
                                ilist = LF.smooth(ilist,
                                                  window_len=self.LEEDWindowLen,
                                                  window_type=self.LEEDWindowType)
                            thread = WorkerThread(task='OUTPUT_TO_TEXT',
                                                       elist=self.leeddat.elist,
                                                       ilist=ilist,
                                                       name=outfile)
                            thread.finished.connect(self.output_complete)
                            self.threads.append(thread)
                            thread.start()
                else:
                    # There are no background curves to output
                    for idx, tup in enumerate(self.LEEDclickpos):
                        outfile = os.path.join(outdir, outname+str(idx)+'.txt')
                        rad = int(self.LEEDrects[idx][3])
                        x = int(tup[0])
                        y = int(tup[1])
                        int_window = self.leeddat.dat3d[y - rad:y + rad + 1,
                                                        x - rad:x + rad + 1, :]
                        # get average intensity per window
                        ilist = [img.sum()/(2*rad*2*rad) for img in np.rollaxis(int_window, 2)]
                        if self.smoothLEEDoutput:
                            ilist = LF.smooth(ilist,
                                              window_len=self.LEEDWindowLen,
                                              window_type=self.LEEDWindowType)
                        thread = WorkerThread(task='OUTPUT_TO_TEXT',
                                                   elist=self.leeddat.elist,
                                                   ilist=ilist,
                                                   name=outfile)
                        thread.finished.connect(self.output_complete)
                        self.threads.append(thread)
                        thread.start()


#validate settings

    def validate_smoothing_settings(self, but=None):
        """Validate User input from Config Tab smoothing settings."""
        if but is None:
            return
        elif but == 'LEED':
            window_type = str(self.smooth_LEED_window_type_menu.currentText())
            window_len = str(self.LEED_window_len_entry.text())
        elif but == 'LEEM':
            window_type = str(self.smooth_LEEM_window_type_menu.currentText())
            window_len = str(self.LEEM_window_len_entry.text())
        else:
            print("Error: Invalid button label passed to validate_smoothing_settings().")
            return
        print("Currently selected smoothing settings: {0} {1} {2}".format(but + ":", window_type, window_len))
        try:
            window_len = int(window_len)
        except TypeError:
            print("Error: Window Length setting must be entered as an even integer")
            return
        if window_len <= 0:
            print("Error: Window Length mut be positive even integer")
            return
        elif window_len % 2 != 0:
            print("Warning: Window Length was odd. Using next highest even integer")
            window_len += 1
        if window_type.lower() not in ['flat', 'hanning',
                                       'hamming', 'bartlett',
                                       'blackman']:
            print("Error: Invalid Window Type for data smoothing.")
            return
        if but == "LEED":
            self.LEEDWindowType = window_type.lower()
            self.LEEDWindowLen = window_len
        else:
            self.LEEMWindowType = window_type.lower()
            self.LEEMWindowLen = window_len
            # Changing the LEEM smoothing settings means we need to
            # reset our position mask array which declared if we had
            # previously calculated the smoothed data for a given point (x, y)
            if self.hasdisplayedLEEMdata:
                # if we haven't displayed data yet, don't bother with this step.
                self.leemdat.posMask.fill(0)
        return


    def toggleReflectivity(self, data=None):
        """Swap boolean flag for plotting Reflectivity instead of Intensity."""
        if data is None:
            return
        if data == "LEEM":
            self.rescaleLEEMIntensity = not self.rescaleLEEMIntensity
            self.LEEMivplotwidget.setLabel("left", "Reflectivity")
        if data == "LEED":
            pass  # TODO: decide if we want this as a feature

    def apply_LEED_window_size(self):
        """Set side length for Rectangular integration window from User input."""
        userinput = str(self.LEED_rect_setting_entry.text())
        try:
            userinput = int(userinput)
        except TypeError:
            print("Error: LEED Window Side length must be entered as an even integer")
            return
        if userinput % 2 != 0:
            print("Warning: Window side Length was odd. Using next highest even integer")
            userinput += 1
        self.boxrad = userinput / 2
        print("Setting LEED Window size to {0}x{1} ...".format(userinput, userinput))
        return


    @QtCore.pyqtSlot()
    def smoothing_statechange(self, data=None):
        """Toggle LEED smoothing option."""
        if data is None:
            return
        elif data == 'LEED':
            if self.smoothLEEDCheckBox.isChecked():
                self.smoothLEEDplot = True
                self.smoothLEEDoutput = True
            else:
                self.smoothLEEDplot = False
                self.smoothLEEDoutput = False
            return
        elif data == 'LEEM':
            if self.smoothLEEMCheckBox.isChecked():
                self.smoothLEEMplot = True
                self.smoothLEEMoutput = True
            else:
                self.smoothLEEMplot = False
                self.smoothLEEMoutput = False
            return

    @QtCore.pyqtSlot()
    def averageStateChanged(self):
        """Toggle boolean flag for outputting average LEED IV."""
        if self.LEED_file_output_checkbox.isChecked():
            self.outputLEEDAverage = True
        else:
            self.outputLEEDAverage = False

    @staticmethod
    @QtCore.pyqtSlot()
    def output_complete():
        """Recieved a finished() SIGNAL from a QThread object."""
        print('File output successfully')

    @QtCore.pyqtSlot(np.ndarray)
    def retrieve_LEEM_data(self, data):########## This loads the image I think 
        """Grab the 3d numpy array emitted from the data loading I/O thread."""
        self.leemdat.dat3d = data
        self.leemdat.dat3ds = data.copy()
        self.leemdat.posMask = np.zeros((self.leemdat.dat3d.shape[0],
                                         self.leemdat.dat3d.shape[1]))
        if self.currentLEEMTime:
            # populate self.leemdat.timelist via settings from self.exp
            try:
                time_step = self.exp.time_step
            except AttributeError:
                print("Error: No Time Step setting found in loaded experiment settings.")
                print("Defaulting to 1.0s per image.")
                time_step = 1.0
            print("Creating LEEM time series ...")
            self.leemdat.timelist = [k * time_step for k in range(self.leemdat.dat3d.shape[2])]
        return

    @QtCore.pyqtSlot(np.ndarray)
    def retrieve_LEED_data(self, data):
        """Grab the numpy array emitted from the data loading I/O thread."""
        # data = [np.fliplr(np.rot90(np.rot90(img))) for img in np.rollaxis(data, 2)]
        # data = np.dstack(data)
        self.leeddat.dat3d = data
        self.leeddat.dat3ds = data.copy()
        self.leeddat.posMask = np.zeros((self.leeddat.dat3d.shape[0],
                                         self.leeddat.dat3d.shape[1]))
        if self.currentLEEDTime:
            # populate self.leeddat.timelist via settings from self.exp
            try:
                time_step = self.exp.time_step
            except AttributeError:
                print("Error: No Time Step setting found in loaded experiment settings.")
                print("Defaulting to 1.0s per image.")
                time_step = 1.0
            print("Creating LEED time series ...")
            self.leeddat.timelist = [k * time_step for k in range(self.leeddat.dat3d.shape[2])]
        return

######
    @QtCore.pyqtSlot()
    def update_LEEM_img_after_load(self):
        """Called upon data loading I/O thread emitting finished signal."""
        # print("QThread has finished execution ...")

        # Check that data was actually loaded
        if self.leemdat.dat3d is None:
            return

        if self.hasdisplayedLEEMdata:
            self.LEEMimageplotwidget.getPlotItem().clear()

        self.curLEEMIndex = 0

        # pyqtgraph displays the array rotated 90 degrees CCW. To force the display to match the original array we
        # display a rotated + flipped array so that the image is displayed correctly
        # see the following discussion on the pyqtgraph forum for more information
        # https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!msg/pyqtgraph/aMQW16vF9Os/mmILDzCyCAAJ
        # Pyqtgraph interprets array data as [width, height]. So we apply a horizontal flip via [::-1, :]
        # then transpose the flipped array. This is equivalent to a 90 degree rotation in the CCW direction.

        self.LEEMimage = pg.ImageItem(self.leemdat.dat3d[::-1, :, self.curLEEMIndex].T)
        self.LEEMimageplotwidget.addItem(self.LEEMimage)
        self.LEEMimageplotwidget.hideAxis('bottom')
        self.LEEMimageplotwidget.hideAxis('left')

        if not hasattr(self, 'crosshair'):
            pen = pg.mkPen(color=pg.mkColor('y'), width=2)
            self.crosshair = ExtendedCrossHair(pen)
        # If self.crosshair already existed, we remove the lines and re-add them to the scene
        # this forces them to be on top of the displayed image.
        self.LEEMimageplotwidget.removeItem(self.crosshair.hline)
        self.LEEMimageplotwidget.addItem(self.crosshair.hline,
                                         ignoreBounds=True)
        self.LEEMimageplotwidget.removeItem(self.crosshair.vline)
        self.LEEMimageplotwidget.addItem(self.crosshair.vline,
                                         ignoreBounds=True)

        self.leemdat.elist = [self.exp.mine]
        while len(self.leemdat.elist) < self.leemdat.dat3d.shape[2]:
            nextEnergy = self.leemdat.elist[-1] + self.exp.stepe
            self.leemdat.elist.append(round(nextEnergy, 2))
        self.checkDataSize(datatype="LEEM")
        self.hasdisplayedLEEMdata = True

        energy = LF.filenumber_to_energy(self.leemdat.elist, self.curLEEMIndex)
        title = "Real Space {0} Image: {1} {2}"
        if self.currentLEEMTime:
            energy = self.leemdat.timelist[self.curLEEMIndex]
            unit = "s"
        else:
            unit = "eV"

        # if self.currentLEEMTime:
        #    title = "Real Space LEEM Image: {} s".format(self.leemdat.timelist[self.curLEEMIndex])
        # else:
        #    title = "Real Space LEEM Image: {} eV".format(energy)

        self.LEEMimtitle.setText(title.format(self.LEEM_tab_active_exp.exp_type,
                                              energy,
                                              unit))
        self.LEEMimageplotwidget.setFocus()


    def adjustLoadedImage(self):
        self.imageAdjustWidget = ImageAdjust()


    @QtCore.pyqtSlot()
    def update_LEED_img_after_load(self):
        """Called upon data loading I/O thread emitting finished signal."""
        # if self.hasdisplayedLEEDdata:
        #     self.LEEDimageplotwidget.getPlotItem().clear()

        # check that data was actually loaded
        if self.leeddat.dat3d is None:
            return

        self.curLEEDIndex = 0

        # pyqtgraph displays the array rotated 90 degrees CCW. To force the display to match the original array we
        # display a rotated + flipped array so that the image is displayed correctly
        # see the following discussion on the pyqtgraph forum for more information
        # https://groups.google.com/forum/?utm_medium=email&utm_source=footer#!msg/pyqtgraph/aMQW16vF9Os/mmILDzCyCAAJ
        # Pyqtgraph interprets array data as [width, height]. So we apply a horizontal flip via [::-1, :]
        # then transpose the flipped array. This is equivalent to a 90 degree rotation in the CCW direction.

        self.LEEDimage = pg.ImageItem(self.leeddat.dat3d[::-1, :, self.curLEEDIndex].T)
        self.LEEDimagewidget.addItem(self.LEEDimage)
        self.LEEDimagewidget.hideAxis('bottom')
        self.LEEDimagewidget.hideAxis('left')

        self.leeddat.elist = [self.exp.mine]
        while len(self.leeddat.elist) < self.leeddat.dat3d.shape[2]:
            newEnergy = self.leeddat.elist[-1] + self.exp.stepe
            self.leeddat.elist.append(round(newEnergy, 2))
        self.hasdisplayedLEEDdata = True
        title = "Reciprocal Space LEED Image: {} eV"
        energy = LF.filenumber_to_energy(self.leeddat.elist, self.curLEEDIndex)
        self.LEEDTitle.setText(title.format(energy))
        self.LEEDimagewidget.setFocus()

    def checkDataSize(self, datatype=None):
        """Ensure helper array sizes all match main data array size."""
        if datatype is None:
            return
        elif datatype == 'LEEM':
            mainshape = self.leemdat.dat3d.shape
            if self.leemdat.dat3ds.shape != mainshape:
                self.leemdat.dat3ds = np.zeros(mainshape)
            if self.leemdat.posMask.shape != (mainshape[0], mainshape[1]):
                self.leemdat.posMask = np.zeros((mainshape[0], mainshape[1]))
        elif datatype == 'LEED':
            pass
        else:
            return

    def enableLEEMWindow(self):
        """Enable I(V) extraction from rectangular window.

        Default is single pixel extraction.
        """
        if self.LEEMRectWindowEnabled:
            return
        # disable mouse movement tracking
        # reroute mouse click signal to new handle
        try:
            self.sigmmvLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok. Here we just want to disable mousemovement tracking
            pass
        try:
            self.sigmcLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok. Here we just want to disable the default mouse click behaviour
            pass

        self.sigmcLEEM.connect(self.handleLEEMWindow)

        # move cropsshair away from image area
        self.crosshair.vline.setPos(0)
        self.crosshair.hline.setPos(0)

        # remove any current LEEM clicks
        self.LEEMclicks = 0
        if self.LEEMcircs:
            for circ in self.LEEMcircs:
                self.LEEMimageplotwidget.scene().removeItem(circ)
        self.LEEMcircs = []
        self.LEEMselections = []
        self.LEEMRectCount = 0
        self.LEEMRects = []

        self.LEEMRectWindowEnabled = True
        self.parentWidget().extractLEEMWindowAction.setEnabled(True)

    def disableLEEMWindow(self):
        """Disable I(V) extraction from rectangular window.

        Reinstate default behavior: single pixel extraction.
        """
        if not self.LEEMRectWindowEnabled:
            return
        try:
            self.sigmmvLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok, and we can continue to reconnect this signal to the
            # LEEM mouse movement tracking handler
            pass
        try:
            self.sigmcLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok, and we can continue to reconnect this signal to the
            # LEEM mouse click handler
            pass

        # delete current rect windows and reset click count
        for tup in self.LEEMRects:
            self.LEEMimageplotwidget.scene().removeItem(tup[0])
        self.LEEMclicks = 0
        self.LEEMcircs = []
        self.LEEMselections = []
        self.LEEMRectCount = 0
        self.LEEMRects = []
        # Reset Mouse event signals to default behaviour
        self.sigmcLEEM.connect(self.handleLEEMClick)
        self.sigmmvLEEM.connect(self.handleLEEMMouseMoved)
        self.LEEMRectWindowEnabled = False
        self.parentWidget().extractLEEMWindowAction.setEnabled(False)


    def handleLEEMWindow(self, event):
        """Use mouse mouse clicks to generate rectangular window for I(V) extraction."""
        if not self.hasdisplayedLEEMdata or event.currentItem is None or event.button() == 2:
            return
        if event.button() == 2:
            return  # filter out right click events
        if len(self.qcolors) <= len(self.LEEMRects):
            print("Maximum number of LEEM Selections reached. Please clear current selection.")
            return

        if self.LEEMclicks == 0:
            # this was the first click

            brush = QtGui.QBrush(self.qcolors[len(self.LEEMRects)])
            pos = event.pos()
            rad = 8
            # account for offset in patch location from QRectF
            x = pos.x() - rad/2
            y = pos.y() - rad/2
            # create circular patch
            circ = self.LEEMimageplotwidget.scene().addEllipse(x, y, rad, rad, brush=brush)
            self.LEEMcircs.append(circ)
            self.firstclick = (x, y)  # position of center of patch for first clicks
            # mapped coordinates for first click:
            vb = self.LEEMimageplotwidget.getPlotItem().getViewBox()
            mappedclick = vb.mapSceneToView(event.scenePos())
            xmp = int(mappedclick.x())
            ymp = self.leemdat.dat3d.shape[0] - 1 - int(mappedclick.y())
            self.firstclickmap = (xmp, ymp)  # location of first click in array coordinates
            self.LEEMclicks += 1
            return

        elif self.LEEMclicks == 1:
            # this is the second click
            self.secondclick = (event.pos().x(), event.pos().y())
            vb = self.LEEMimageplotwidget.getPlotItem().getViewBox()
            mappedclick = vb.mapSceneToView(event.scenePos())
            xmp = int(mappedclick.x())
            ymp = self.leemdat.dat3d.shape[0] - 1 - int(mappedclick.y())
            self.secondclickmap = (xmp, ymp)  # location of second click in array coordinates

            rectcoords = LF.getRectCorners(self.firstclick, self.secondclick)
            rectcoordsmap = LF.getRectCorners(self.firstclickmap, self.secondclickmap)
            topleft = rectcoords[0]  # scene coordinates
            topleftmap = rectcoordsmap[0]  # array coordinates
            bottomright = rectcoords[1]  # scene coordinates
            bottomrightmap = rectcoordsmap[1]  # array coordinates
            width = bottomright[0] - topleft[0]
            height = bottomright[1] - topleft[1]
            rect = QtCore.QRectF(topleft[0], topleft[1], width, height)
            self.LEEMRectCount += 1
            pen = QtGui.QPen()
            pen.setStyle(QtCore.Qt.SolidLine)
            pen.setWidth(4)
            # pen.setBrush(QtCore.Qt.red)
            pen.setColor(self.qcolors[self.LEEMRectCount - 1])
            rectitem = self.LEEMimageplotwidget.scene().addRect(rect, pen=pen)
            self.LEEMRects.append((rectitem, rect, pen, topleftmap, bottomrightmap))
            self.LEEMclicks = 0
            for circ in self.LEEMcircs:
                self.LEEMimageplotwidget.scene().removeItem(circ)
            self.LEEMcircs = []


    def extractLEEMWindows(self):
        """Extract I(V) from User defined rectangular windows and Plot in main IV area."""
        if not self.hasdisplayedLEEMdata or not self.LEEMRects or self.LEEMRectCount == 0:
            return
        self.LEEMivplotwidget.clear()
        for tup in self.LEEMRects:
            topleft = tup[3]
            bottomright = tup[4]
            xtl = int(topleft[0])
            ytl = int(topleft[1])
            width = int(bottomright[0] - xtl)
            height = int(bottomright[1] - ytl)
            # print("Topleft: {}".format(topleft))
            # print("Bottomright: {}".format(bottomright))
            print("Window Selected: X={0}, Y={1}, Width={2}, Height={3}".format(xtl, ytl, width, height))
            window = self.leemdat.dat3d[ytl:ytl + height + 1,
                                        xtl:xtl + width + 1, :]
            ilist = [img.sum()/(width*height) for img in np.rollaxis(window, 2)]
            if self.smoothLEEMplot:
                ilist = LF.smooth(ilist, window_len=self.LEEMWindowLen, window_type=self.LEEMWindowType)
            if self.currentLEEMTime:
                xdata = self.leemdat.timelist
            else:
                xdata = self.leemdat.elist
            self.LEEMivplotwidget.plot(xdata,
                                       ilist,
                                       pen=pg.mkPen(tup[2].color(), width=self.LEEM_Linewidth))

    def enableLEEMLineProfile(self):
        """Enable fixed energy contrast analysis along a straight line segment.

        Disable/reroute current LEEM mouse behavaiour to stop tracking mouse motion and implement a new click hadler.
        """
        try:
            self.sigmmvLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok. Here we just want to disable mousemovement tracking
            pass
        try:
            self.sigmcLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok. Here we just want to disable the default mouse click behaviour
            pass

        self.sigmcLEEM.connect(self.handleLEEMLineProfile)

        # move cropsshair away from image area
        self.crosshair.vline.setPos(0)
        self.crosshair.hline.setPos(0)

        # remove any current LEEM clicks
        self.LEEMclicks = 0
        if self.LEEMcircs:
            for circ in self.LEEMcircs:
                self.LEEMimageplotwidget.scene().removeItem(circ)
        self.LEEMcircs = []
        self.LEEMselections = []
        self.LEEMRectCount = 0
        if self.LEEMRects:
            for item in self.LEEMRects:
                self.LEEMimageplotwidget.scene().removeItem(item[0])
        self.LEEMRects = []
        self.LEEMLineProfileEnabled = True
        self.parentWidget().extractLEEMLineProfileAction.setEnabled(self.LEEMLineProfileEnabled)

    def disableLEEMLineProfile(self):
        """Disable fixed energy contrast analysis.

        Reinstate default mouse click and movement behaviour.
        """
        try:
            self.sigmmvLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok, and we can continue to reconnect this signal to the
            # LEEM mouse movement tracking handler
            pass
        try:
            self.sigmcLEEM.disconnect()
        except:
            # If sigmvLEEM is not connected to anything, an exception is raised
            # This is ok, and we can continue to reconnect this signal to the
            # LEEM mouse click handler
            pass
        for item in self.LEEMLines:
            self.LEEMimageplotwidget.scene().removeItem(item[0])
        self.LEEMLines = []
        self.LEEMivplotwidget.clear()
        self.LEEMivplotwidget.setLabel('bottom', 'Energy', units='eV', **self.labelStyle)
        # Reset Mouse event signals to default behaviour
        self.sigmcLEEM.connect(self.handleLEEMClick)
        self.sigmmvLEEM.connect(self.handleLEEMMouseMoved)
        self.LEEMLineProfileEnabled = False
        self.parentWidget().extractLEEMLineProfileAction.setEnabled(self.LEEMLineProfileEnabled)


    def handleLEEMLineProfile(self, event):
        """Create QGraphicsLineItem objects from user click positions."""
        if not self.hasdisplayedLEEMdata:
            return
        if event.button() == 2:
            return  # filter out right click events
        if len(self.qcolors) <= len(self.LEEMLines):
            print("Maximum number of LEEM Line Selection reached. Please clear current selections.")
            return
        if self.LEEMclicks == 0:
            # This was the first click
            brush = QtGui.QBrush(self.qcolors[len(self.LEEMLines)])
            pos = event.pos()
            rad = 8
            # account for offset in patch location from QRectF
            x = pos.x() - rad/2
            y = pos.y() - rad/2
            # create circular patch
            circ = self.LEEMimageplotwidget.scene().addEllipse(x, y, rad, rad, brush=brush)
            self.LEEMcircs.append(circ)
            self.firstclick = (x, y)  # position of center of patch for first clicks
            # mapped coordinates for first click:
            vb = self.LEEMimageplotwidget.getPlotItem().getViewBox()
            mappedclick = vb.mapSceneToView(event.scenePos())
            xmp = int(mappedclick.x())
            ymp = self.leemdat.dat3d.shape[0] - 1 - int(mappedclick.y())
            self.firstclickmap = (xmp, ymp)  # location of first click in array coordinates
            self.LEEMclicks += 1
            return
        elif self.LEEMclicks == 1:
            # This is the second click
            pos = event.pos()
            self.secondclick = (pos.x(), pos.y())  # scene position
            vb = self.LEEMimageplotwidget.getPlotItem().getViewBox()
            mappedclick = vb.mapSceneToView(event.scenePos())
            xmp = int(mappedclick.x())
            ymp = self.leemdat.dat3d.shape[0] - 1 - int(mappedclick.y())
            self.secondclickmap = (xmp, ymp)  # array coordinates
            pen = QtGui.QPen()
            pen.setStyle(QtCore.Qt.SolidLine)
            pen.setWidth(4)
            # pen.setBrush(QtCore.Qt.red)
            pen.setColor(self.qcolors[len(self.LEEMLines)])
            line = self.LEEMimageplotwidget.scene().addLine(self.firstclick[0], self.firstclick[1],
                                                            self.secondclick[0], self.secondclick[1], pen=pen)

            self.LEEMLines.append((line, self.firstclickmap, self.secondclickmap))

            if self.LEEMcircs:
                for circ in self.LEEMcircs:
                    self.LEEMimageplotwidget.scene().removeItem(circ)
            self.LEEMcircs = []
            self.LEEMclicks = 0

    def extractLEEMLineProfiles(self):
        """Use Bressenham Algorithm to get all array points along the User selected lines."""
        if not self.hasdisplayedLEEMdata or not self.LEEMLineProfileEnabled:
            return
        self.LEEMivplotwidget.clear()
        for idx, item in enumerate(self.LEEMLines):
            pt1 = item[1]
            pt2 = item[2]
            points = bline(pt1[0], pt1[1], pt2[0], pt2[1])
            ilist = []
            for point in points:
                ilist.append(self.leemdat.dat3d[point[1], point[0], self.curLEEMIndex])
            if self.smoothLEEMplot:
                ilist = LF.smooth(ilist, window_len=self.LEEMWindowLen, window_type=self.LEEMWindowType)
            pen = pg.mkPen(self.qcolors[idx], width=self.LEEM_Linewidth)
            pdi = pg.PlotDataItem(list(range(len(points))), ilist, pen=pen)
            self.LEEMivplotwidget.addItem(pdi)
            self.LEEMivplotwidget.setLabel('bottom', 'Distance Along Line', units='[arb. units]', **self.labelStyle)


#mouse click** rad = size of circle - default is 8- this has original circ info
    def handleLEEMClick(self, event):
        """User click registered in LEEMimage area.

        Handles offset for QRectF drawn for circular patch to ensure that
        the circle is drawn directly below the mouse pointer.

        Appends I(V) curve from clicked location to alternate plot window so
        as to not interfere with the live tracking plot.


        Update Jeannet 2021: change radius of appended circle from default 8 to pw - user input 
        """
        if not self.hasdisplayedLEEMdata:
            return

        if event.button() == 2:
            return  # filter out 'right click' events

        # clicking outside image area may cause event.currentItem
        # to be None. This would then raise an error when trying to
        # call event.pos()
        if event.currentItem is None:
            return

        if len(self.qcolors) <= self.LEEMclicks:
            print("Maximum number of LEEM selections. Please clear current selections.")
            return
        self.LEEMclicks += 1

        pos = event.pos()
        mappedPos = self.LEEMimage.mapFromScene(pos)
        xmapfs = int(mappedPos.x())
        ymapfs = int(mappedPos.y())

        if xmapfs < 0 or \
           xmapfs > self.leemdat.dat3d.shape[1] or \
           ymapfs < 0 or \
           ymapfs > self.leemdat.dat3d.shape[0]:
            return  # discard click events originating outside the image

        if self.currentLEEMPos is not None:
            try:
                # mouse position
                xmp = self.currentLEEMPos[0]
                ymp = self.currentLEEMPos[1]  # x and y in array coordinates (top edge is y=0)
            except IndexError:
                return
        else:
            print("Error: Failed to get currentLEEMPos for LEEMClick().")
            return
        xdata = self.leemdat.elist
        ydata = self.leemdat.dat3d[ymp, xmp, :]
        if self.smoothLEEMplot:
            ydata = LF.smooth(ydata, window_len=self.LEEMWindowLen, window_type=self.LEEMWindowType)

        brush = QtGui.QBrush(self.qcolors[self.LEEMclicks - 1])

        pw = self.patch_text.text()#repeat from validate patch width method -- this comes with diff value error: that
        #there is no input yet. --> print an error message for user to input a value first, then patches would show
        try:
            pw = int(pw)
        except ValueError:
            print("Error: patch width must first be entered in Config Tab")
            print ("Default patch width is: 8")
            rad = 8
            return
        if pw <=0:
            print("ERROR: patch width must be entered as an integer > 0")
            return
        elif pw is None:
            print("Please enter a patch width in ConfigTab")
            return
        rad = pw
        x = pos.x() - rad/2  # offset for QRectF
        y = pos.y() - rad/2  # offset for QRectF

        circ = self.LEEMimageplotwidget.scene().addEllipse(x, y, rad, rad, brush=brush)
        # print("Click at x={0}, y={1}".format(x, y))
        self.LEEMcircs.append(circ)
        self.LEEMselections.append((xmp, ymp))  # (x, y format)

        pen = pg.mkPen(self.qcolors[self.LEEMclicks - 1], width=self.LEEM_Linewidth)
        pdi = pg.PlotDataItem(xdata, ydata, pen=pen)

        yaxis = self.staticLEEMplot.getAxis("left")
        # y axis is 'arbitrary units'; we don't want kilo or mega arbitrary units etc...
        yaxis.enableAutoSIPrefix(False)

        self.staticLEEMplot.addItem(pdi)
        self.staticLEEMplot.setTitle("LEEM-I(V)")
        self.staticLEEMplot.setLabel('bottom', 'Energy', units='eV', **self.labelStyle)
        self.staticLEEMplot.setLabel('left', 'Intensity', units='a.u.', **self.labelStyle)

        if not self.staticLEEMplot.isVisible():
            self.staticLEEMplot.show()

    def handleLEEMMouseMoved(self, pos):
        """Track mouse movement within LEEM image area and display I(V) from mouse location."""
        if not self.hasdisplayedLEEMdata:
            return
        if isinstance(pos, tuple):
            try:
                # if pos a tuple containing a QPointF object
                pos = pos[0]
            except IndexError:
                # empty tuple
                return
        # else pos is a QPointF object which can be mapped directly

        mappedPos = self.LEEMimage.mapFromScene(pos)
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())
        if xmp < 0 or \
           xmp > self.leemdat.dat3d.shape[1] - 1 or \
           ymp < 0 or \
           ymp > self.leemdat.dat3d.shape[0] - 1:
            return  # discard  movement events originating outside the image

        # update crosshair
        self.crosshair.curPos = (xmp, ymp)  # place cross hair with y coordinate in reference to bottom edge as y=0
        self.crosshair.vline.setPos(xmp)
        self.crosshair.hline.setPos(ymp)

        # convert to array (numpy) y coordinate by inverting the y value
        ymp = self.leemdat.dat3d.shape[0] - 1 - ymp
        self.currentLEEMPos = (xmp, ymp)  # used for handleLEEMClick()
        # print("Mouse moved to: {0}, {1}".format(xmp, ymp))  # array coordinates

        # update IV plot
        if self.currentLEEMTime:
            xdata = self.leemdat.timelist
        else:
            xdata = self.leemdat.elist
        ydata = self.leemdat.dat3d[ymp, xmp, :]  # raw unsmoothed data

        if self.rescaleLEEMIntensity:
            ydata = [point/float(max(ydata)) for point in ydata]
        if self.smoothLEEMplot and not self.leemdat.posMask[ymp, xmp]:
            # We want to plot smoothed dat but the I(V) of the current pixel position
            # has not yet been smoothed
            ydata = LF.smooth(ydata, window_type=self.LEEMWindowType, window_len=self.LEEMWindowLen)
            self.leemdat.dat3ds[ymp, xmp, :] = ydata
            self.leemdat.posMask[ymp, xmp] = 1

        elif self.smoothLEEMplot and self.leemdat.posMask[ymp, xmp]:
            # We want to plot smoothed data and have already calculated it for this pixel position
            ydata = self.leemdat.dat3ds[ymp, xmp, :]

        pen = pg.mkPen(self.qcolors[0], width=self.LEEM_Linewidth)
        pdi = pg.PlotDataItem(xdata, ydata, pen=pen)
        self.LEEMivplotwidget.getPlotItem().clear()
        self.LEEMivplotwidget.getPlotItem().addItem(pdi, clear=True)


    def handleLEEDClick(self, event):
        """User click registered in LEEDimage area."""
        if not self.hasdisplayedLEEDdata or event.currentItem is None:
            return

        if event.button() == 2:
            return  # filter out 'right click' events

        # Ensure number of LEED windows remains less than the max colors
        if len(self.qcolors) <= self.LEEDclicks:
            print("Maximum number of LEED Windows Reached. Please clear current selections.")
            return

        self.LEEDclicks += 1
        pos = event.pos()  # scene position
        x = int(pos.x())
        y = int(pos.y())

        viewbox = self.LEEDimagewidget.getPlotItem().getViewBox()
        mappedPos = viewbox.mapSceneToView(event.scenePos())  # position in array coordinates
        xmp = int(mappedPos.x())
        ymp = int(mappedPos.y())

        # pyqtgraph uses bottom edge as y=0; this converts the coordinate to the numpy system
        ymp = (self.leeddat.dat3d.shape[0] - 1) - ymp

        # check to see if click is too close to edge
        if (xmp - self.boxrad < 0 or xmp + self.boxrad >= self.leeddat.dat3d.shape[1] or
           ymp - self.boxrad < 0 or ymp + self.boxrad >= self.leeddat.dat3d.shape[0]):
            print("Error: Click registered too close to image edge.")
            print("Reduce window size or choose alternate extraction point")
            self.LEEDclicks -= 1
            return

        if xmp >= 0 and xmp < self.leeddat.dat3d.shape[1] - 1 and \
           ymp >= 0 and ymp < self.leeddat.dat3d.shape[0] - 1:
            # valid array coordinates

            # QGraphicsRectItem is drawn using the scene coordinates (x, y)
            topleftcorner = QtCore.QPointF(x - self.boxrad,
                                           y - self.boxrad)
            rect = QtCore.QRectF(topleftcorner.x(), topleftcorner.y(),
                                 2*self.boxrad, 2*self.boxrad)
            pen = QtGui.QPen()
            pen.setStyle(QtCore.Qt.SolidLine)
            pen.setWidth(6)  # Changed for image clarity - set to 4 or below if too thick
            # pen.setBrush(QtCore.Qt.red)
            pen.setColor(self.qcolors[self.LEEDclicks - 1])
            rectitem = self.LEEDimage.scene().addRect(rect, pen=pen)  # QGraphicsRectItem

            # We need access to the QGraphicsRectItem inorder to later call
            # removeItem(). However, we also need access to the QRectF object
            # in order to get coordinates. Thus we store a reference to both along
            # with the pen used for coloring the Rect.
            # Finally, we need to keep track of the window side length for each selections
            # as it is user configurable
            self.LEEDrects.append((rectitem, rect, pen, self.boxrad))
            self.LEEDclickpos.append((xmp, ymp))  # store x, y coordinate of mouse click in array coordinates
            # print("Click registered at array coordinates: x={0}, y={1}".format(xmp, ymp))

    def LEEDAutoBackgroundSelection(self):
        """Automate background selection based on User beam selection."""
        if (not self.hasdisplayedLEEDdata or
                not self.LEEDrects or
                not self.LEEDclickpos):
            return

        # Background Selection Automation Config Settings

        buf = 5  # set small pixel buffer around User rect so that background boxes don't overlap user selection.

        # side length of beam box = beam_to_background_ratio * side length of background box (see for loop)
        beam_to_background_ratio = 3

        gap_size_ratio = 4  # adjust the gap offset for side boxes from center horizontal line (see for loop)

        self.LEEDBackgroundrects = []
        self.LEEDBackgroundcenters = []
        for idx, item in enumerate(self.LEEDrects):
            rect = item[1]
            size = 2*item[3]
            if size % 2 != 0:
                size += 1
            if size < 10:
                print("Warning: One or more Beam Selection boxes is smaller than 10 x 10.")
                print("Use larger selection box in order to make use of automated background selection.")
                return
            r1 = int(size / 2)

            backgroundsize = size // beam_to_background_ratio
            print("Selection size: {0}, Background size: {1}".format(size, backgroundsize))
            r2 = int(backgroundsize / 2)

            gap = int((size - 2*backgroundsize) / gap_size_ratio)

            x0 = int(rect.center().x())  # scene coordinates
            y0 = int(rect.center().y())  # scene coordinates
            xa = self.LEEDclickpos[idx][0]  # array coordinates
            ya = self.LEEDclickpos[idx][1]  # array cooridnates

            pen = QtGui.QPen()
            pen.setStyle(QtCore.Qt.SolidLine)
            pen.setWidth(4)
            pen.setBrush(QtCore.Qt.white)

            # Create Rectangular patches and add to scene

            top_center = (xa, ya - r1 - buf - r2)  # array coordinates
            if top_center[0] + r2 >= self.leeddat.dat3d.shape[1] or \
               top_center[0] - r2 <= 0 or \
               top_center[1] - r2 <= 0 or \
               top_center[1] + r2 >= self.leeddat.dat3d.shape[0]:
                print("Warning: One or more beams is located too close to image edge.")
                print("Can't perform Auto Background Selection near edge.")
                return
            topbox_topleftcorner = QtCore.QPointF(x0 - r2, y0 - r1 - buf - 2*r2)
            top_box = QtCore.QRectF(topbox_topleftcorner, QtCore.QSizeF(backgroundsize, backgroundsize))
            top_box_item = self.LEEDimage.scene().addRect(top_box, pen)

            bottom_center = (xa, ya + r1 + buf + r2)  # array coordinates
            if bottom_center[0] + r2 >= self.leeddat.dat3d.shape[1] or \
               bottom_center[0] - r2 <= 0 or \
               bottom_center[1] - r2 <= 0 or \
               bottom_center[1] + r2 >= self.leeddat.dat3d.shape[0]:
                print("Warning: One or more beams is located too close to image edge.")
                print("Can't perform Auto Background Selection near edge.")
                return
            bottombox_topleftcorner = QtCore.QPointF(x0 - r2, y0 + r1 + buf)
            bottom_box = QtCore.QRectF(bottombox_topleftcorner, QtCore.QSizeF(backgroundsize, backgroundsize))
            bottom_box_item = self.LEEDimage.scene().addRect(bottom_box, pen)

            righttop_center = (xa + r1 + buf + r2, ya - gap - r2)
            if righttop_center[0] + r2 >= self.leeddat.dat3d.shape[1] or \
               righttop_center[0] - r2 <= 0 or \
               righttop_center[1] - r2 <= 0 or \
               righttop_center[1] + r2 >= self.leeddat.dat3d.shape[0]:
                print("Warning: One or more beams is located too close to image edge.")
                print("Can't perform Auto Background Selection near edge.")
                return
            righttopbox_tlc = QtCore.QPointF(x0 + r1 + buf, y0 - gap - 2*r2)
            righttop_box = QtCore.QRectF(righttopbox_tlc, QtCore.QSizeF(backgroundsize, backgroundsize))
            righttop_box_item = self.LEEDimage.scene().addRect(righttop_box, pen)

            rightbottom_center = (xa + r1 + buf + r2, ya + gap + r2)
            if rightbottom_center[0] + r2 >= self.leeddat.dat3d.shape[1] or \
               rightbottom_center[0] - r2 <= 0 or \
               rightbottom_center[1] - r2 <= 0 or \
               rightbottom_center[1] + r2 >= self.leeddat.dat3d.shape[0]:
                print("Warning: One or more beams is located too close to image edge.")
                print("Can't perform Auto Background Selection near edge.")
                return
            rightbottom_tlc = QtCore.QPointF(x0 + r1 + buf, y0 + gap)
            rightbottom_box = QtCore.QRectF(rightbottom_tlc, QtCore.QSizeF(backgroundsize, backgroundsize))
            rightbottom_box_item = self.LEEDimage.scene().addRect(rightbottom_box, pen)

            lefttop_center = (xa - r1 - buf - r2, ya - gap - r2)
            if lefttop_center[0] + r2 >= self.leeddat.dat3d.shape[1] or \
               lefttop_center[0] - r2 <= 0 or \
               lefttop_center[1] - r2 <= 0 or \
               lefttop_center[1] + r2 >= self.leeddat.dat3d.shape[0]:
                print("Warning: One or more beams is located too close to image edge.")
                print("Can't perform Auto Background Selection near edge.")
                return
            lefttopbox_tlc = QtCore.QPointF(x0 - r1 - buf - 2*r2, y0 - gap - 2*r2)
            lefttop_box = QtCore.QRectF(lefttopbox_tlc, QtCore.QSizeF(backgroundsize, backgroundsize))
            lefttop_box_item = self.LEEDimage.scene().addRect(lefttop_box, pen)

            leftbottom_center = (xa - r1 - buf - r2, ya + gap + r2)
            if leftbottom_center[0] + r2 >= self.leeddat.dat3d.shape[1] or \
               leftbottom_center[0] - r2 <= 0 or \
               leftbottom_center[1] - r2 <= 0 or \
               leftbottom_center[1] + r2 >= self.leeddat.dat3d.shape[0]:
                print("Warning: One or more beams is located too close to image edge.")
                print("Can't perform Auto Background Selection near edge.")
                return
            leftbottom_tlc = QtCore.QPointF(x0 - r1 - buf - 2*r2, y0 + gap)
            leftbottom_box = QtCore.QRectF(leftbottom_tlc, QtCore.QSizeF(backgroundsize, backgroundsize))
            leftbottom_box_item = self.LEEDimage.scene().addRect(leftbottom_box, pen)

            # Add patches to container for plotting

            self.LEEDBackgroundrects.append((top_box_item, top_box, pen, r2))
            self.LEEDBackgroundcenters.append(top_center)

            self.LEEDBackgroundrects.append((bottom_box_item, bottom_box, pen, r2))
            self.LEEDBackgroundcenters.append(bottom_center)

            self.LEEDBackgroundrects.append((righttop_box_item, righttop_box, pen, r2))
            self.LEEDBackgroundcenters.append(righttop_center)

            self.LEEDBackgroundrects.append((rightbottom_box_item, rightbottom_box, pen, r2))
            self.LEEDBackgroundcenters.append(rightbottom_center)

            self.LEEDBackgroundrects.append((lefttop_box_item, lefttop_box, pen, r2))
            self.LEEDBackgroundcenters.append(lefttop_center)

            self.LEEDBackgroundrects.append((leftbottom_box_item, leftbottom_box, pen, r2))
            self.LEEDBackgroundcenters.append(leftbottom_center)

    def LEEDAutoBackgroundSelection2(self):
        """Rewrite using circular generation of points."""
        if (not self.hasdisplayedLEEDdata or
                not self.LEEDrects or
                not self.LEEDclickpos):
            return

        # Background Selection Automation Config Settings

        buf = 10  # set small pixel buffer around User rect so that background boxes don't overlap user selection.

        # side length of beam box = beam_to_background_ratio * side length of background box (see for loop)
        beam_to_background_ratio = 3

        self.LEEDBackgroundrects = []
        self.LEEDBackgroundcenters = []
        phi0 = np.pi/2  # start with first box aligned on the y axis.
        angles = [phi0 + k*np.pi/3 for k in range(6)]  # separate boxes by 60 degrees equally spaced on a circle

        for idx, item in enumerate(self.LEEDrects):
            rect = item[1]
            size = 2*item[3]
            if size % 2 != 0:
                size += 1
            if size < 10:
                print("Warning: One or more Beam Selection boxes is smaller than 10 x 10.")
                print("Use larger selection box in order to make use of automated background selection.")
                return
            r1 = int(size / 2)

            backgroundsize = size // beam_to_background_ratio
            print("Selection size: {0}, Background size: {1}".format(size, backgroundsize))
            r2 = int(backgroundsize / 2)

            # gap = int((size - 2*backgroundsize) / gap_size_ratio)

            x0 = int(rect.center().x())  # scene coordinates
            y0 = int(rect.center().y())  # scene coordinates
            xa = self.LEEDclickpos[idx][0]  # array coordinates
            ya = self.LEEDclickpos[idx][1]  # array cooridnates

            pen = QtGui.QPen()
            pen.setStyle(QtCore.Qt.SolidLine)
            pen.setWidth(4)
            pen.setBrush(QtCore.Qt.white)

            radius_to_center = r1 + buf + r2

            points = [(x0 + radius_to_center*np.cos(phi), y0 + radius_to_center*np.sin(phi)) for phi in angles]

            centers = [(int(xa + radius_to_center*np.cos(phi)),
                        int(ya + radius_to_center*np.sin(phi))) for phi in angles]  # array coordinates

            tlcs = [QtCore.QPointF(pt[0] - r2, pt[1] - r2) for pt in points]

            background_rects = [QtCore.QRectF(corner,
                                              QtCore.QSizeF(backgroundsize, backgroundsize)) for corner in tlcs]

            for idx, rect in enumerate(background_rects):
                rectitem = self.LEEDimage.scene().addRect(rect, pen=pen)
                self.LEEDBackgroundrects.append((rectitem, background_rects[idx], pen, r2))
                self.LEEDBackgroundcenters.append(centers[idx])

    def processLEEDIV(self):
        """Plot I(V) from User selections."""
        if not self.hasdisplayedLEEDdata or not self.LEEDrects or not self.LEEDclickpos:
            return
        if len(self.LEEDrects) != len(self.LEEDclickpos):
            print("Error: Number of LEED windows does not match number of stored click positions")
            return

        # loop over user slections
        for idx, tup in enumerate(self.LEEDclickpos):
            # center coordinates
            xc = tup[0]
            yc = tup[1]

            # the lengths of LEEDclickpos and LEEDrects are ensured to be equal now
            rad = int(self.LEEDrects[idx][3])  # cast to int to ensure array indexing uses ints

            # top left corner in array coordinates
            xtl = xc - rad
            ytl = yc - rad

            int_window = self.leeddat.dat3d[ytl:ytl + 2*rad + 1,
                                            xtl:xtl + 2*rad + 1, :]
            # store average intensity per window
            ilist = [img.sum()/(2*rad*2*rad) for img in np.rollaxis(int_window, 2)]
            # ilist = [img.sum() for img in np.rollaxis(int_window, 2)]
            if self.smoothLEEDplot:
                ilist = LF.smooth(ilist, window_type=self.LEEDWindowType, window_len=self.LEEDWindowLen)
            # self.LEEDivplotwidget.plot(self.leeddat.elist, ilist, pen=pg.mkPen(self.qcolors[idx], width=4))
            self.LEEDivplotwidget.plot(self.leeddat.elist,
                                       ilist,
                                       pen=pg.mkPen(self.LEEDrects[idx][2].color(), width=4))
            if self.LEEDBackgroundrects:
                for idx, tup in enumerate(self.LEEDBackgroundcenters):
                    # center coordinates
                    xc = tup[0]
                    yc = tup[1]

                    # the lengths of LEEDclickpos and LEEDrects are ensured to be equal now
                    rad = int(self.LEEDBackgroundrects[idx][3])  # cast to int to ensure array indexing uses ints

                    # top left corner in array coordinates
                    xtl = xc - rad
                    ytl = yc - rad

                    int_window = self.leeddat.dat3d[ytl:ytl + 2*rad + 1,
                                                    xtl:xtl + 2*rad + 1, :]
                    # store average intensity per window
                    ilist = [img.sum()/(2*rad*2*rad) for img in np.rollaxis(int_window, 2)]
                    # ilist = [img.sum() for img in np.rollaxis(int_window, 2)]
                    if self.smoothLEEDplot:
                        ilist = LF.smooth(ilist, window_type=self.LEEDWindowType, window_len=self.LEEDWindowLen)
                    # self.LEEDivplotwidget.plot(self.leeddat.elist, ilist, pen=pg.mkPen(self.qcolors[idx], width=4))

                    # width set to 6 for image clarity; reset to 4 if needed
                    self.LEEDivplotwidget.plot(self.leeddat.elist,
                                               ilist,
                                               pen=pg.mkPen(self.LEEDBackgroundrects[idx][2].color(), width=6))

    def averageLEEDIV(self):
        """Extract IV from current user selections and average the curves."""
        if not self.hasdisplayedLEEDdata or not self.LEEDrects or not self.LEEDclickpos:
            return
        if len(self.LEEDrects) != len(self.LEEDclickpos):
            print("Error: Number of LEED widnows does not match number of stored click positions")
            return
        if len(self.LEEDrects) == 1:
            print("Averaging LEED I(V) curves requires more than one selection.")
            return
        curves = []
        for idx, tup in enumerate(self.LEEDclickpos):
            # center coordinates
            xc = tup[0]
            yc = tup[1]

            # the lengths of LEEDclickpos and LEEDrects are ensured to be equal now
            rad = int(self.LEEDrects[idx][3])  # cast to int to ensure array indexing uses ints

            # top left corner in array coordinates
            xtl = int(xc - rad)
            ytl = int(yc - rad)
            int_window = self.leeddat.dat3d[ytl:ytl + 2*rad + 1,
                                            xtl:xtl + 2*rad + 1, :]
            # store average intensity per window
            ilist = [img.sum()/(2*rad*2*rad) for img in np.rollaxis(int_window, 2)]
            # ilist = [img.sum() for img in np.rollaxis(int_window, 2)]
            curves.append(ilist)
        self.LEEDAverageIV = list(map(lambda l: sum(l)/float(len(l)), zip(*curves)))
        # clear current I(V) plot then plot the averaged I(V) data
        self.LEEDivplotwidget.clear()
        if self.smoothLEEDplot:
            self.LEEDivplotwidget.plot(self.leeddat.elist,
                                       LF.smooth(self.LEEDAverageIV,
                                                 window_len=self.LEEDWindowLen,
                                                 window_type=self.LEEDWindowType),
                                       pen=pg.mkPen(self.qcolors[0], width=3))
        else:
            self.LEEDivplotwidget.plot(self.leeddat.elist,
                                       self.LEEDAverageIV,
                                       pen=pg.mkPen(self.qcolors[0], width=3))

    def undoLEEDSelection(self):
        """Remove last User selection."""
        if (not self.LEEDclicks > 0 or
                not self.LEEDrects or
                not self.LEEDclickpos or
                not self.hasdisplayedLEEDdata):
            return

        self.LEEDclicks -= 1
        self.LEEDimagewidget.scene().removeItem(self.LEEDrects.pop()[0])
        del self.LEEDclickpos[-1]
        self.LEEDivplotwidget.clear()  # reset the IV plot and plot the non-deleted items
        self.processLEEDIV()

    def clearLEEDIV(self):
        """Triggered by menu action to clear all LEED selections."""
        self.LEEDivplotwidget.clear()
        if self.LEEDrects:
            # items stored as (QRectF, QPen)
            for tup in self.LEEDrects:
                self.LEEDimagewidget.scene().removeItem(tup[0])
        if self.LEEDBackgroundrects:
            for tup in self.LEEDBackgroundrects:
                self.LEEDimagewidget.scene().removeItem(tup[0])
        self.LEEDrects = []
        self.LEEDBackgroundrects = []
        self.LEEDclickpos = []
        self.LEEDBackgroundcenters = []
        self.LEEDclicks = 0
        self.LEEDAverageIV = []

    def clearLEEMIV(self):
        """Clear User selections from LEEM image and clear IV plot."""
        if self.LEEMcircs:
            for item in self.LEEMcircs:
                self.LEEMimageplotwidget.scene().removeItem(item)
        self.staticLEEMplot.clear()
        if self.staticLEEMplot.isVisible():
            self.staticLEEMplot.close()
            self.staticLEEMplot = pg.PlotWidget()  # reset to new plot instance but don't call show()
            self.staticLEEMplot.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.LEEMclicks = 0
        self.LEEMselections = []
        self.LEEMcircs = []

    def clearLEEMWindows(self):
        """Clear LEEM rectangular windows."""
        for tup in self.LEEMRects:
            # first item in container is rectitem
            self.LEEMimageplotwidget.scene().removeItem(tup[0])
        for circ in self.LEEMcircs:
            self.LEEMimageplotwidget.scene().removeItem(circ)
        self.LEEMivplotwidget.clear()
        self.LEEMclicks = 0
        self.LEEMcircs = []
        self.LEEMselections = []
        self.LEEMRectCount = 0
        self.LEEMRects = []

    def clearLEEMLines(self):
        """Clear QGraphicsLineItems from LEEMimageplotwidget."""
        if self.LEEMLines:
            for item in self.LEEMLines:
                self.LEEMimageplotwidget.scene().removeItem(item[0])
        if self.LEEMcircs:
            for circ in self.LEEMcircs:
                self.LEEMimageplotwidget.scene().removeItem(circ)
        self.LEEMivplotwidget.clear()
        self.LEEMLines = []
        self.LEEMclicks = 0
        self.LEEMcircs = []


    def keyPressEvent(self, event):
        """Set Arrow keys for navigation."""
        # LEEM Tab is active
        if self.tabs.currentIndex() == 0 and \
           self.hasdisplayedLEEMdata:
            # handle LEEM navigation
            maxIdx = self.leemdat.dat3d.shape[2] - 1
            minIdx = 0
            if (event.key() == QtCore.Qt.Key_Left) and \
               (self.curLEEMIndex >= minIdx + 1):
                self.curLEEMIndex -= 1
                self.showLEEMImage(self.curLEEMIndex)
                """
                if self.currentLEEMTime:
                    title = "Real Space LEEM Image: {} s".format(self.leemdat.timelist[self.curLEEMIndex])
                else:
                    energy = LF.filenumber_to_energy(self.leemdat.elist, self.curLEEMIndex)
                    title = "Real Space LEEM Image: {} eV".format(energy)
                # self.LEEMimageplotwidget.setTitle(title.format(energy))
                self.LEEMimtitle.setText(title)
                """
            elif (event.key() == QtCore.Qt.Key_Right) and \
                 (self.curLEEMIndex <= maxIdx - 1):
                self.curLEEMIndex += 1
                self.showLEEMImage(self.curLEEMIndex)
                """
                if self.currentLEEMTime:
                    title = "Real Space LEEM Image: {} s".format(self.leemdat.timelist[self.curLEEMIndex])
                else:
                    energy = LF.filenumber_to_energy(self.leemdat.elist, self.curLEEMIndex)
                    title = "Real Space LEEM Image: {} eV".format(energy)
                # self.LEEMimageplotwidget.setTitle(title.format(energy))
                self.LEEMimtitle.setText(title)
                """
            title = "Real Space {0} Image: {1} {2}"
            energy = LF.filenumber_to_energy(self.leemdat.elist, self.curLEEMIndex)
            if self.currentLEEMTime:
                energy = self.leemdat.timelist[self.curLEEMIndex]  # this is a time
                unit = "s"
            else:
                unit = "eV"
            self.LEEMimtitle.setText(title.format(self.LEEM_tab_active_exp.exp_type,
                                                  energy,
                                                  unit))
        # LEED Tab is active
        elif (self.tabs.currentIndex() == 1) and \
             (self.hasdisplayedLEEDdata):
            # handle LEED navigation
            maxIdx = self.leeddat.dat3d.shape[2] - 1
            minIdx = 0
            if (event.key() == QtCore.Qt.Key_Left) and \
               (self.curLEEDIndex >= minIdx + 1):
                self.curLEEDIndex -= 1

                self.showLEEDImage(self.curLEEDIndex)
                """
                title = "Reciprocal Space LEED Image: {} eV"
                energy = LF.filenumber_to_energy(self.leeddat.elist,
                                                 self.curLEEDIndex)
                self.LEEDTitle.setText(title.format(energy))
                """
            elif (event.key() == QtCore.Qt.Key_Right) and \
                 (self.curLEEDIndex <= maxIdx - 1):
                self.curLEEDIndex += 1

                self.showLEEDImage(self.curLEEDIndex)
                """
                title = "Reciprocal Space LEED Image: {} eV"
                energy = LF.filenumber_to_energy(self.leeddat.elist,
                                                 self.curLEEDIndex)
                self.LEEDTitle.setText(title.format(energy))
                """
            title = "Reciprocal Space {0} Image: {1} {2}"
            energy = LF.filenumber_to_energy(self.leeddat.elist, self.curLEEDIndex)
            if self.currentLEEDTime:
                energy = self.leeddat.timelist[self.curLEEDIndex]  # this is a time
                unit = "s"
            else:
                unit = "eV"
            self.LEEDTitle.setText(title.format(self.LEED_tab_active_exp.exp_type,
                                                  energy,
                                                  unit))

    def showLEEMImage(self, idx):####
        """Display LEEM image from main data array at index=idx."""
        if idx not in range(self.leemdat.dat3d.shape[2] - 1):
            return

        # see note in instance method update_LEEM_img_after_load()
        # for why the displayed image uses a horizontal flip + transpose
        self.LEEMimage.setImage(self.leemdat.dat3d[::-1, :, idx].T)

    def showLEEDImage(self, idx):
        """Display LEED image from main data array at index=idx."""
        if idx not in range(self.leeddat.dat3d.shape[2] - 1):
            return

        # see note in instance method update_LEED_img_after_load()
        # for why the displayed image uses a horizontal flip + transpose
        self.LEEDimage.setImage(self.leeddat.dat3d[::-1, :, idx].T)
