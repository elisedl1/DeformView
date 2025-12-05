import logging
import os
from typing import Annotated, Optional

import vtk

import ctk 

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode
from slicer import vtkMRMLTransformNode
from slicer import vtkMRMLVectorVolumeNode
import vtk.util.numpy_support
import qt

import re

#
# BrainShiftModule
#
def setCrosshairColor(colorRGB):
    layoutManager = slicer.app.layoutManager()
    sliceViewNames = slicer.util.getSliceViewNames()  # ['Red', 'Yellow', 'Green']
    
    for viewName in sliceViewNames:
        sliceWidget = layoutManager.sliceWidget(viewName)
        dm = sliceWidget.sliceView().displayableManagerByClassName("vtkMRMLCrosshairDisplayableManager")
        if dm:
            # Update color: (R,G,B) in range 0.0-1.0
            dm.SetCrosshairColor(colorRGB)


class BrainShiftModule(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("BrainShiftModule")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Examples")]
        self.parent.dependencies = [] 
        self.parent.contributors = [" Isabel Frolick (McGill), Elise Donszelmann-Lund (McGill), Étienne Léger"]  
        self.parent.helpText = _("""
            Visualize Brain Shift (mm) per voxel
            See more information in <a href="https://github.com/organization/projectname#BrainShiftModule">module documentation</a>.
            """)
        self.parent.acknowledgementText = _(""" """)

#
# BrainShiftModuleParameterNode
#


@parameterNodeWrapper
class BrainShiftModuleParameterNode:
    """
    The parameters needed by module.


    referenceVolume - The pre-operative MRI volume
    transformationNode - The transformation applied (MRI to iUS)).
    displacementField - volume node to store 3D vector field
    displacementMagnitudeVolume - Output volume storing per-voxel displacement (magnitude) in mm.
    """

    referenceVolume: vtkMRMLScalarVolumeNode
    transformNode: vtkMRMLTransformNode
    displacementMagnitudeVolume: vtkMRMLScalarVolumeNode
    backgroundVolume: vtkMRMLScalarVolumeNode



#
# BrainShiftModuleWidgeto
#


class BrainShiftModuleWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None


    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.

        # instructionsLabel = qt.QLabel("Welcome to DisplaceMMent, the intuitive visualization module for non-linear registration.  To get started, select your registered fixed image, moving image, and related transformation. ") 
        # instructionsLabel.setWordWrap(True)

        # === Add the instructions (collapsible, to the top)===

        
        instructionsCollapsibleButton = ctk.ctkCollapsibleButton()
        instructionsCollapsibleButton.text = "Instructions"
        instructionsCollapsibleButton.collapsed = True  # Start collapsed
        self.layout.insertWidget(1, instructionsCollapsibleButton)

        instructionsLayout = qt.QVBoxLayout(instructionsCollapsibleButton)
        
        #instructionsLabel = qt.QLabel("  To get started, select your registered fixed image, moving image, and related transformation. ") 
        #instructionsLabel.setWordWrap(True)
        instructionsLabel = qt.QLabel()
        instructionsLabel.setText("""
        <b>Instructions:</b><br><br>
        Welcome to DisplaceMMent, the intuitive visualization module for non-linear registration!<br><br>
        To get started, select your registered fixed image, moving image, and related transformation. 
        # 1. First step<br>
        # 2. Second step<br>
        # <i>Note: Important information</i>
        """)
        instructionsLabel.setWordWrap(True)
        self.layout.addWidget(instructionsLabel)
        #instructionsLayout.addWidget(instructionsLabel)
        instructionsLayout.addWidget(instructionsLabel)
        #self.layout.insertWidget(1, instructionsLabel)
        
        # === LOAD UI FILE ===

        uiWidget = slicer.util.loadUI(self.resourcePath("UI/BrainShiftModule.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        # Hide the uiWidget so it doesn't take up space
        uiWidget.hide()

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # === DEFINE UI!!!S ===
        self.UIinstance()
       

        #--- Define the connectivity ---

        # set the scene for each individual node widget
        self.ui.referenceVolume.setMRMLScene(slicer.mrmlScene)
        self.ui.transformNode.setMRMLScene(slicer.mrmlScene)
        self.ui.displacementMagnitudeVolume.setMRMLScene(slicer.mrmlScene)
        self.ui.backgroundVolume.setMRMLScene(slicer.mrmlScene)
        #self.ui.ConvertTagFCSVNode.setMRMLScene(slicer.mrmlScene)

        self.ui.backgroundVolume.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.ui.backgroundVolume.addEnabled = False 
        self.ui.backgroundVolume.removeEnabled = False

        self.ui.referenceVolume.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.ui.referenceVolume.addEnabled = False
        self.ui.referenceVolume.removeEnabled = False

        self.ui.displacementMagnitudeVolume.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.ui.displacementMagnitudeVolume.addEnabled = True  # can create new output volume
        self.ui.displacementMagnitudeVolume.removeEnabled = True

        self.ui.transformNode.nodeTypes = ["vtkMRMLTransformNode"]
        self.ui.transformNode.addEnabled = False
        self.ui.transformNode.removeEnabled = False 

        #self.ui.ConvertTagFCSVNode.nodeTypes = ["vtkMRMLTransformNode"]
        self.ui.transformNode.addEnabled = False
        self.ui.transformNode.removeEnabled = False 

        self.ui.loadedTransformVolume.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.ui.loadedTransformVolume.setMRMLScene(slicer.mrmlScene)

        # connect
        self.ui.loadDisplacementVolumeButton.connect("clicked(bool)", self.onLoadDisplacementVolume)

        # color selector
             
        jacobianColorNode = self.createJacobianColorNode()

        self.ui.colorMapSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.colorMapSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.colorMapSelector.nodeTypes = [
            f"{jacobianColorNode}",
            "vtkMRMLColorTableNode",
            "vtkMRMLProceduralColorNode",
            "vtkMRMLPETColorNode"
            
        ]


        # mouse displayer
        self.crosshairNode = slicer.util.getNode("Crosshair")

        # self.labelMarkupNode = slicer.util.getModule("Data").mrmlScene().GetFirstNodeByName("BrainShiftModule_MouseValueLabel")
        self.labelMarkupNode = slicer.mrmlScene.GetFirstNodeByName("BrainShiftModule_MouseValueLabel")

        if(  not self.labelMarkupNode ):
            self.labelMarkupNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "BrainShiftModule_MouseValueLabel")
            self.labelMarkupNode.AddControlPoint(0, 0, 0)
            self.labelMarkupNode.SetLocked(True)
            self.labelMarkupNode.SetMarkupLabelFormat("{label}")
            self.labelMarkupNode.GetDisplayNode().SetVisibility2D(False)
            self.labelMarkupNode.GetDisplayNode().SetVisibility3D(False)
            self.labelMarkupNode.SetNthControlPointLabel(0, "")
            self.labelMarkupNode.GetDisplayNode().SetColor([0.0, 0.0, 0.0])  # [0.0,0.0,0.0]       # Fiducial marker color
            self.labelMarkupNode.GetDisplayNode().SetSelectedColor([0.0, 0.0, 0.0])  # [0.0, 0.0, 0.0]    # Color when selected
            self.labelMarkupNode.GetDisplayNode().GetTextProperty().SetColor(0.0, 0.0, 0.0)  # 0,0,0 # Label **text** color (this is key!)

        self.crosshairObserverTag = None

        self.ui.enableHoverDisplayCheckbox.setChecked(False)  # start disabled
        self.ui.enableHoverDisplayCheckbox.connect("toggled(bool)", self.onToggleHoverDisplay)



        # self.line_edit = qt.QLineEdit(self)
        # self.layout.addWidget(self.line_edit)

        # self.line_edit = qt.QLineEdit()
        # self.layout().addWidget(self.line_edit)

        #self.ui.line_edit = qt.QLineEdit()
        
        # connect backgroundVolume
        self.ui.backgroundVolume.setProperty("SlicerParameterName", "backgroundVolume")

        # connect US Border display checkbox
        self.ui.enableUsBorderDisplay.toggled.connect(self.onToggleUsDisplay)
        

        
        # connect threshold slider
        self.ui.thresholdSlider.connect("valuesChanged(double,double)", self.onThresholdSliderChanged)
        
        self.ui.colourWindowSlider.connect("valuesChanged(double,double)", self.onColourWindowSliderChanged)

        # set spin box max and mins
        self.ui.thresholdMinSpinBox.connect("valueChanged(double)", self.onMinSpinBoxChanged)
        self.ui.thresholdMaxSpinBox.connect("valueChanged(double)", self.onMaxSpinBoxChanged)        
      
        #self.ui.minColourWindow.connect("valueChanged(double)", self.onMinColourWindowChanged)
        #self.ui.maxColourWindow.connect("valueChanged(double)", self.onMaxColourWindowChanged)        
      

        # button to create fcsv from tag file
        self.ConvertTagFCSVButton = qt.QPushButton("Load Tag File")
        self.ConvertTagFCSVButton.toolTip = "Load a .tag file and create fiducial nodes"
       
        self.ui.ConvertTagFCSVButton.connect("clicked(bool)", self.onConvertTagFCSVButtonClicked)


        #Visualize the landmarks as desired (multi-slect)
        self.LandmarkSelectorComboBox = ctk.ctkCheckableComboBox()
        self.LandmarkSelectorComboBox.setToolTip("Select fiducial landmark nodes to display")
        
        # Populate list manually
        self.updateLandmarkSelectorComboBox()

        # Check which landmarks to display
        self.LandmarkSelectorComboBox.connect('checkedIndexesChanged()', self.onLandmarkSelectionChanged)

        self.LoadExpertLabelsButton = qt.QPushButton("Load Tag File")
        self.LoadExpertLabelsButton.toolTip = "Visualize landmarks"
        #self.layout.addWidget(self.LoadExpertLabelsButton)
        self.ui.LoadExpertLabelsButton.connect('clicked(bool)', self.onLoadExpertLabelsClicked)
        #self.ui.LoadExpertLabelsButton.pressed.connect(self.onLoadExpertLabelsClicked)
        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = BrainShiftModuleLogic()

        # Connections
        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
       
    
        #Add observer to the node event to track landmark files available
        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeChanged)
        self.addObserver(slicer.mrmlScene, slicer.vtkMRMLScene.NodeRemovedEvent, self.onNodeChanged)


        # Buttons
        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

        # allow for user to adjust opacity
        self.ui.opacitySlider.valueChanged.connect(self.onOpacityChanged)
        self.onOpacityChanged(self.ui.opacitySlider.value)

        #Euclidian
        self.watchActiveLabel()
        self.ui.selectedLandmarks.setReadOnly(True)
        self.ui.landmarkEuclidianDistance.setReadOnly(True)

        






        



    def UIinstance(self):
        # === SECTION 1: IMAGES LOADING ===

        inputGroup = qt.QGroupBox("Input Images")
        inputGroup.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                margin-top: 15px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        self.layout.addWidget(inputGroup)

        inputLayout = qt.QFormLayout(inputGroup)
        inputLayout.setContentsMargins(20, 25, 20, 20)  # Increased margins
        inputLayout.setSpacing(12)  # Increased spacing between rows
        inputLayout.setVerticalSpacing(12)  # Vertical spacing between form rows
        inputLayout.setLabelAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)  # Right-align labels

        inputLayout.addRow("Moving Image:", self.ui.referenceVolume)
        inputLayout.addRow("Fixed Image:", self.ui.backgroundVolume)
        inputLayout.addRow("Transformation:", self.ui.transformNode)
        inputLayout.addRow("Output Volume:", self.ui.displacementMagnitudeVolume)

        # Add some space before the button
        inputLayout.addRow("", qt.QWidget())  # Empty spacer row
        inputLayout.addRow("", self.ui.applyButton)


        # === SECTION 2: PROCESSING ===

        processingGroup = qt.QGroupBox("Displacement Field Visualization")
        processingGroup.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                margin-top: 15px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        self.layout.addWidget(processingGroup)

        processingLayout = qt.QFormLayout(processingGroup)  # Use QFormLayout for consistency
        processingLayout.setContentsMargins(20, 25, 20, 20)
        processingLayout.setSpacing(12)
        processingLayout.setVerticalSpacing(12)
        processingLayout.setLabelAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)

        processingLayout.addRow("Displacement Field:", self.ui.loadedTransformVolume)
        processingLayout.addRow("Color Map:", self.ui.colorMapSelector)
        processingLayout.addRow("", self.ui.loadDisplacementVolumeButton)


        # === SECTION 3: LANDMARKS ===

        landmarkGroup = qt.QGroupBox("Landmark Analysis")
        landmarkGroup.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                margin-top: 15px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        self.layout.addWidget(landmarkGroup)

        landmarkLayout = qt.QFormLayout(landmarkGroup)
        landmarkLayout.setContentsMargins(20, 25, 20, 20)
        landmarkLayout.setSpacing(12)
        landmarkLayout.setVerticalSpacing(12)
        landmarkLayout.setLabelAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)

        landmarkLayout.addRow("Convert .tag File:", self.ui.ConvertTagFCSVButton)
        landmarkLayout.addRow("Select Landmarks:", self.ui.LandmarkSelectorComboBox)
        landmarkLayout.addRow("Load Landmarks:", self.ui.LoadExpertLabelsButton)

        # Add separator space
        landmarkLayout.addRow("", qt.QWidget())

        # Results section within landmarks
        self.ui.selectedLandmarks.setReadOnly(True)
        self.ui.landmarkEuclidianDistance.setReadOnly(True)
        self.ui.selectedLandmarks.setStyleSheet("QLineEdit { background-color:gray; color: #333; }")
        self.ui.landmarkEuclidianDistance.setStyleSheet("QLineEdit { background-color:gray; color: #333; }")
        landmarkLayout.addRow("Active Landmarks:", self.ui.selectedLandmarks)
        landmarkLayout.addRow("Distance (mm):", self.ui.landmarkEuclidianDistance)


        # === SECTION 4: VISUALIZATION SETTINGS ===

        vizGroup = qt.QGroupBox("Display Settings")
        vizGroup.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                margin-top: 15px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        self.layout.addWidget(vizGroup)

        vizLayout = qt.QFormLayout(vizGroup)
        vizLayout.setContentsMargins(20, 25, 20, 20)
        vizLayout.setSpacing(12)
        vizLayout.setVerticalSpacing(12)
        vizLayout.setLabelAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)

        vizLayout.addRow(self.ui.enableHoverDisplayCheckbox)
        vizLayout.addRow(self.ui.enableUsBorderDisplay)

        # Opacity with better layout
        opacityLayout = qt.QHBoxLayout()
        opacityLayout.addWidget(self.ui.opacitySlider, 1)  # Stretch factor
        opacityLayout.addSpacing(10)
        opacityLayout.addWidget(self.ui.opacityValue)
        vizLayout.addRow("Opacity:", opacityLayout)

        # Threshold with labels
        thresLayout = qt.QVBoxLayout()
        thresLayout.setSpacing(5)

        sliderLayout = qt.QHBoxLayout()
        sliderLayout.addWidget(self.ui.thresholdSlider)
        thresLayout.addLayout(sliderLayout)

        spinBoxLayout = qt.QHBoxLayout()
        spinBoxLayout.addWidget(qt.QLabel("Min:"))
        spinBoxLayout.addWidget(self.ui.thresholdMinSpinBox)
        spinBoxLayout.addSpacing(10)
        spinBoxLayout.addWidget(qt.QLabel("Max:"))
        spinBoxLayout.addWidget(self.ui.thresholdMaxSpinBox)
        thresLayout.addLayout(spinBoxLayout)

        vizLayout.addRow("Threshold Range:", thresLayout)


        windowLayout = qt.QVBoxLayout()
        windowLayout.setSpacing(5)
        #vizLayout.addRow("Colour Window:", self.ui.colourWindowSlider)
        colourWindowSliderLayout = qt.QHBoxLayout()
        colourWindowSliderLayout.addWidget(self.ui.colourWindowSlider)
        windowLayout.addLayout(colourWindowSliderLayout)

        # colourWindowLayout = qt.QHBoxLayout()
        # colourWindowLayout.addWidget(qt.QLabel("Min:"))
        # #colourWindowLayout.addWidget(self.ui.minColourWindow)
        # colourWindowLayout.addSpacing(10)
        # colourWindowLayout.addWidget(qt.QLabel("Max:"))
        # colourWindowLayout.addWidget(self.ui.maxColourWindow)
        # windowLayout.addLayout(colourWindowLayout)
        
        vizLayout.addRow("Colour Window (contrast):", windowLayout)


        # COLOUR LEVEL
        levelLayout = qt.QVBoxLayout()
        levelLayout.setSpacing(5)
        #vizLayout.addRow("Colour Window:", self.ui.colourWindowSlider)
        colourLevelSliderLayout = qt.QHBoxLayout()
        colourLevelSliderLayout.addWidget(self.ui.colourLevelSlider)
        levelLayout.addLayout(colourLevelSliderLayout)

        # colourLevelLayout = qt.QHBoxLayout()
        # colourLevelLayout.addWidget(qt.QLabel("Min:"))
        # colourLevelLayout.addWidget(self.ui.minColourLevel)
        # colourLevelLayout.addSpacing(10)
        # colourLevelLayout.addWidget(qt.QLabel("Max:"))
        # colourLevelLayout.addWidget(self.ui.maxColourLevel)
        # levelLayout.addLayout(colourLevelLayout)
        
        vizLayout.addRow("Colour Level (brightness):", levelLayout)

        # Add stretch at the end
        self.layout.addStretch(1)


        




    def onOpacityChanged(self, value) -> None:
        normalizedValue = value/100
        slicer.util.setSliceViewerLayers(foregroundOpacity=normalizedValue)
        self.ui.opacityValue.setText(f"{value:.0f}%")


    def onToggleUsDisplay(self) -> None:
        usVolume = self.ui.referenceVolume.currentNode()
        state = self.ui.enableUsBorderDisplay.checkState() 
    
        self.logic.showNonZeroWireframe(foregroundVolume=usVolume, state=state)
    
    

    def createJacobianColorNode(self):
        # Check if node already exists
        existingNode = slicer.mrmlScene.GetFirstNodeByName("JacobianMap")
        if existingNode:
        #     print("JacobianMap already exists, reusing.")
            return existingNode

        # Create a new color node

        # if not slicer.vtkMRMLProceduralColorNode().Get
        colorNode = slicer.vtkMRMLProceduralColorNode()
        colorNode.SetName("JacobianMap")
        slicer.mrmlScene.AddNode(colorNode)
        
        # Metadata
        colorNode.SetAttribute("Category", "Jacobian")
        colorNode.SetAttribute("Type", "UserDefined")
        colorNode.SetDescription("Blue for <1 (compression), Red for >1 (expansion)")

        # Define custom transfer function
        ctf = colorNode.GetColorTransferFunction()
        ctf.RemoveAllPoints()
        
        # Stronger, deeper colors
        ctf.AddRGBPoint(0.0, 0.0, 0.0, 0.6)   # deep blue at 0
        ctf.AddRGBPoint(0.999, 0.0, 0.0, 1.0) # strong blue just below 1
        ctf.AddRGBPoint(1.0, 1.0, 1.0, 1.0)   # neutral white at 1
        ctf.AddRGBPoint(1.001, 1.0, 0.0, 0.0) # strong red just above 1
        ctf.AddRGBPoint(2.0, 0.6, 0.0, 0.0)   # deep red at 2
        
        colorNode.Modified()
        print("Created new JacobianMap node")
        return colorNode

    def createInputSection(self):
        section = ctk.ctkCollapsibleButton()
        section.text = "1. Input Volumes"
        self.layout.addWidget(section)
        
        layout = qt.QFormLayout(section)
        layout.addRow("Moving Image:", self.referenceVolume)
        layout.addRow("Fixed Image:", self.backgroundVolume)
        layout.addRow("Transformation:", self.transformNode)


    def onConvertTagFCSVButtonClicked(self):
        filePath = qt.QFileDialog.getOpenFileName(
            None, "Open Tag File", "", "Tag files (*.tag)"
        )
        text1, text2 = self.getLandmarkLabel()
        print("Selected file:", filePath, text1, text2)
        if filePath:
            success = self.logic.loadTagFile(filePath, text1, text2)
            if not success:
                slicer.util.errorDisplay(f"Failed to load tag file: {filePath}")
            else:
                logging.info(f"Loaded tag file: {filePath}")
    
    def onLoadExpertLabelsClicked(self):

        comboBox = self.ui.LandmarkSelectorComboBox
        model = comboBox.model()
        for i in range(comboBox.count):
            #print("i", i)
            index = model.index(i, 0)
            itemText = comboBox.itemText(i)
            try:
                node = slicer.util.getNode(itemText)
                displayNode = node.GetDisplayNode()
                displayNode.SetVisibility(False)
                displayNode.SetVisibility2D(False)
            except:
                print(f"Could not get node for: {itemText}")
                continue
            
            checked = model.data(index, qt.Qt.CheckStateRole) == qt.Qt.Checked
            displayNode = node.GetDisplayNode()

            if node.IsA("vtkMRMLMarkupsFiducialNode") and checked:
                if displayNode:
                    print("Show Node", node.GetName())
                    displayNode.SetVisibility(True)
                    displayNode.SetVisibility2D(True)
                    displayNode.SetGlyphScale(3.0)
                    displayNode.SetTextScale(3.0)
                    displayNode.SetActiveColor([1.0, 0.2, 0.5])
                    displayNode.SetSelectedColor(0.0, 0.0, 0.0)
                    displayNode.SetGlyphTypeFromString("Circle2D")
                    displayNode.SetSelected(checked)
                    displayNode.SetHandlesInteractive(False) #??
                    displayNode.SetInteractionHandleScale(0.0)

            else:
                print("don't show node", node.GetName()) #stores typed in landmark name
                #displayNode = node.GetDisplayNode()
                displayNode.SetVisibility(False)
                displayNode.SetVisibility2D(False)
                displayNode.SetGlyphScale(3.0)

    
    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()
        for interactor, tag in getattr(self, "sliceObservers", []):
            interactor.RemoveObserver(tag)
            self.sliceObservers = []
        for dn, tag in getattr(self, "_activeWatchers", []):
            try:
                dn.RemoveObserver(tag)
            except:
                pass
        self._activeWatchers = []

    

    def onSceneUpdated(self, caller, event):
        self.updateLandmarkSelectorComboBox()
    
    
    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

        # re-acquire or create mouse label node
        self.labelMarkupNode = self.getOrCreateMouseLabelNode()
        # sync checkbox to match visibility
        self.updateHoverCheckboxFromNode()


    # def setFixedImage(self, volumeNode):
    #     if not volumeNode:
    #         return
    #     if self._parameterNode:
    #         self._parameterNode.SetParameter("FixedImageID", volumeNode.GetID())
    #     # Optionally apply grey map immediately
    #     if volumeNode.GetDisplayNode():
    #         volumeNode.GetDisplayNode().SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")


    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()


    def _forceGreyColormap(self, displayNode):
        if displayNode and displayNode.GetColorNodeID() != "vtkMRMLColorTableNodeGrey":
            displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
            displayNode.AutoWindowLevelOn()



    def removeDisplayNodesFromVolume(self, volumeNode):
        if not volumeNode:
            return
        # Get all display nodes linked to this volume
        # displayNodes = volumeNode.GetDisplayNodes()
        #for displayNode in volumeNode.GetDisplayNode():
        for i in range(volumeNode.GetNumberOfDisplayNodes()):
            displayNode = volumeNode.GetNthDisplayNode(i)
            if displayNode:
                displayNode.SetVisibility(False)
        #slicer.mrmlScene.RemoveNode(volumeNode.GetDisplayNode())
        # Disconnect volume from any display nodes
        #volumeNode.RemoveAllDisplayNodeIDs()


    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        self.setParameterNode(self.logic.getParameterNode())
        
      
        #Reset the slice viewers to have no foreground initially on entering and reloading module - much cleaner
        layoutManager = slicer.app.layoutManager()
        for sliceViewName in layoutManager.sliceViewNames():
            compositeNode = layoutManager.sliceWidget(sliceViewName).mrmlSliceCompositeNode()
            compositeNode.SetForegroundVolumeID(None)
    
        backgroundVolumeID = self._parameterNode.backgroundVolume.GetID() if self._parameterNode.backgroundVolume else None
        
        if backgroundVolumeID and self._parameterNode.backgroundVolume.GetDisplayNode():
            displayNode = self._parameterNode.backgroundVolume.GetDisplayNode()
            displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
            displayNode.AutoWindowLevelOn()

        referenceVolumeID = self._parameterNode.referenceVolume.GetID() if self._parameterNode.referenceVolume else None
        
        if referenceVolumeID and self._parameterNode.referenceVolume.GetDisplayNode():
            displayNode = self._parameterNode.referenceVolume.GetDisplayNode()
            displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeGrey")
            displayNode.AutoWindowLevelOn()

        
                
  
    def onNodeChanged(self, caller, event) -> None:
    
        self.updateLandmarkSelectorComboBox()

    
    def updateLandmarkSelectorComboBox(self):
        '''
        Tracks which files to add to the selection box for the available landmarks
        '''
        self.ui.LandmarkSelectorComboBox.clear()

        #print("Landmark Selector Count", self.LandmarkSelectorComboBox.count)

        #print("Update... ")
        fiducialNodes = slicer.util.getNodesByClass("vtkMRMLMarkupsFiducialNode")
        
        #print(f"fiducial Nodes", fiducialNodes)
        #print("fiducial Nodes available", len(fiducialNodes))

        for node in fiducialNodes:
            if node == self.labelMarkupNode:  # or whatever your variable name is
                continue
            self.ui.LandmarkSelectorComboBox.addItem(node.GetName()) #stores node name (string)

        self.watchActiveLabel()
        
       






    def onLandmarkSelectionChanged(self):
        # Get all fiducial nodes
        #allFiducials = slicer.util.getNodesByClass("vtkMRMLMarkupsFiducialNode")
        fcsvFiducials = [
            node for node in slicer.util.getNodesByClass("vtkMRMLMarkupsFiducialNode")
            if node.GetStorageNode() and node.GetStorageNode().GetFileName().endswith('.fcsv')
        ]
        
        # Get selected names from the combo box
        selectedNames = []
        for i in range(self.LandmarkSelectorComboBox.count):
            if self.LandmarkSelectorComboBox.checkState(i) == qt.Qt.Checked :
                selectedNames.append(self.LandmarkSelectorComboBox.itemText(i))

        # Show only selected ones
        for node in fcsvFiducials:
            print("Gte nMae:",node.GetName())
            displayNode = node.GetDisplayNode()
            if not displayNode:
                continue
            if node.GetName() in selectedNames:
                displayNode.SetUsePointColors(True)         # Use global color, not per-point
                displayNode.SetVisibility(True)
                displayNode.SetVisibility2D()
                displayNode.SetTextScale(1.0)
                
                displayNode.SetActiveColor([1.0, 0.0, 1.0])   # Pink when active
                displayNode.SetColor(1.0, 0.0, 1.0)           # Pink when not active
                displayNode.SetSelectedColor(1.0, 0.0, 1.0)   # Pink when selected
                displayNode.SetUseSelectedColor()       
                
                displayNode.SetGlyphScale(2.0)
                displayNode.SetHandlesInteractive(False)
                displayNode.SetInteractionHandleScale(0.0)
            else:

                displayNode.SetVisibility(False)
                displayNode.SetVisibility2D(False)


    def watchActiveLabel(self):
        
        #observers for selected landmark
        for n, tag in getattr(self, "_activeWatchers", []):
            try: n.RemoveObserver(tag)
            except: pass
        self._activeWatchers = []
        self._lastDistancePrinted = None

        def onPointEnd(markupsNode, ev):
            dn = markupsNode.GetDisplayNode()
            if not dn:
                return
            if dn.GetActiveComponentType() != slicer.vtkMRMLMarkupsDisplayNode.ComponentControlPoint:
                return
            i = dn.GetActiveComponentIndex()
            if i is None or i < 0 or i >= markupsNode.GetNumberOfControlPoints():
                return

            dist = self.getActivePairInfo()
            if dist is None:
                return
            if self._lastDistancePrinted is not None and abs(dist - self._lastDistancePrinted) < 1e-6:
                return
            self._lastDistancePrinted = dist
            #print(f"distance = {dist:.3f} mm")
            self.updateLandmarkDistanceDisplay(dist)
            
        for n in slicer.util.getNodesByClass("vtkMRMLMarkupsFiducialNode"):
            if n is getattr(self, "labelMarkupNode", None):
                continue
            tag = n.AddObserver(slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent, onPointEnd)
            self._activeWatchers.append((n, tag))
            

    def getActivePairInfo(self):

        activeNode = None
        activeIndex = None
        
        #find active landmark
        for n in slicer.util.getNodesByClass("vtkMRMLMarkupsFiducialNode"):
            if n is getattr(self, "labelMarkupNode", None) or not n.GetDisplayNode():
                continue
            if n.GetDisplayNode().GetActiveComponentType() != slicer.vtkMRMLMarkupsDisplayNode.ComponentControlPoint:
                continue
            idx = n.GetDisplayNode().GetActiveComponentIndex()
            if idx is None or idx < 0:
                continue
            activeNode = n
            activeIndex = idx
            break

        if activeNode is None:
            return None
        
        #find pair landmark
        pairNode = None
        for lmrk in slicer.util.getNodesByClass("vtkMRMLMarkupsFiducialNode"):
            if lmrk is not activeNode and lmrk is not getattr(self, "labelMarkupNode", None):
                pairNode = lmrk
                break
        if pairNode is None:
            return None

        pairIndex = -1
        if activeIndex < pairNode.GetNumberOfControlPoints():
            pairIndex = activeIndex
        if pairIndex < 0:
            return None
        
        #compute distance in IJK (mm)
        rasA = [0.0, 0.0, 0.0]
        rasB = [0.0, 0.0, 0.0]
        activeNode.GetNthControlPointPositionWorld(activeIndex, rasA)
        pairNode.GetNthControlPointPositionWorld(pairIndex, rasB)
        vol = self.ui.loadedTransformVolume.currentNode()
        ijkA = ijkB = None
        if vol:
            rasToIjk = vtk.vtkMatrix4x4()
            vol.GetRASToIJKMatrix(rasToIjk)

            ijkhA = [0.0, 0.0, 0.0, 1.0]
            ras_hA = [rasA[0], rasA[1], rasA[2], 1.0]
            rasToIjk.MultiplyPoint(ras_hA, ijkhA)
            ijkA = [float(ijkhA[0]), float(ijkhA[1]), float(ijkhA[2])]

            ijkhB = [0.0, 0.0, 0.0, 1.0]
            ras_hB = [rasB[0], rasB[1], rasB[2], 1.0]
            rasToIjk.MultiplyPoint(ras_hB, ijkhB)
            ijkB = [float(ijkhB[0]), float(ijkhB[1]), float(ijkhB[2])]

        dx = ijkA[0]-ijkB[0]
        dy = ijkA[1]-ijkB[1]
        dz = ijkA[2]-ijkB[2]
        activeLabel = activeNode.GetNthControlPointLabel(activeIndex) or f"{activeNode.GetName()}-{activeIndex+1}"
        pairLabel   = pairNode.GetNthControlPointLabel(pairIndex)   or f"{pairNode.GetName()}-{pairIndex+1}"
        #print(f"{activeLabel}: IJK = {(ijkA)}")
        #print(f"{pairLabel}: IJK = {(ijkB)}")
        self.updateSelectedLandmarksDisplay(activeLabel, pairLabel)
        return (dx*dx + dy*dy + dz*dz) ** 0.5 
    

    def updateLandmarkDistanceDisplay(self, dist: float) -> None:
    
        if dist is None:
            self.ui.landmarkEuclidianDistance.setText("N/A")
        else:
            self.ui.landmarkEuclidianDistance.setText(f"{dist:.3f} mm")
            self.ui.landmarkEuclidianDistance.setReadOnly(True)

    
    def updateSelectedLandmarksDisplay(self, activeLabel: str, pairLabel: str) -> None:
        if not hasattr(self.ui, 'selectedLandmarks') or self.ui.selectedLandmarks is None:
            return
        self.ui.selectedLandmarks.setReadOnly(True)
        self.ui.landmarkEuclidianDistance.setReadOnly(True)
        self.ui.selectedLandmarks.setText(f"{activeLabel}  ↔  {pairLabel}")


    def setParameterNode(self, inputParameterNode: Optional[BrainShiftModuleParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)

            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        
        # make sure there's a reference MRI and transformation
        if (
            self._parameterNode
            and self._parameterNode.referenceVolume
            and self._parameterNode.transformNode
            and self._parameterNode.backgroundVolume
        ):
            self.ui.applyButton.toolTip = _("Compute voxel-wise displacement magnitude")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = _("Select reference volume and transform")
            self.ui.applyButton.enabled = False


    def onApplyButton(self) -> None:
        """Run processing when user clicks 'Compute Mapping' button.
        
        """
        #print("in onApply")
        with slicer.util.tryWithErrorDisplay(_("Failed to compute voxel-wise displacement."), waitCursor=True):
            
            logging.info(f"Reference Volume: {self._parameterNode.referenceVolume}")
            logging.info(f"Transform Node: {self._parameterNode.transformNode}")
            logging.info(f"Displacement Volume: {self._parameterNode.displacementMagnitudeVolume}")

            #TODO: stop duplicates of displacement/jacobian
            
            # Create displacement field (vector volume)
            displacementVolume = self.logic.computeDisplacementMagnitude(
                referenceVolume=self._parameterNode.referenceVolume,
                transformNode=self._parameterNode.transformNode
            )

            # Create Jacobian  (vector volume)
            jacobianVolume = self.logic.computeJacobianMagnitude(
                referenceVolume=self._parameterNode.referenceVolume,
                transformNode=self._parameterNode.transformNode
            )
            
            # --- Make displacementMagnitude the thing we see + select in UI ---

            # Ensure the magnitude volume has a display node
            dispDisplay = displacementVolume.GetDisplayNode()
            if not dispDisplay:
                displacementVolume.CreateDefaultDisplayNodes()
                dispDisplay = displacementVolume.GetDisplayNode()

            # Sensible W/L (lets Slicer compute it from data range)
            if dispDisplay:
                dispDisplay.AutoWindowLevelOn()
                dispDisplay.SetScalarVisibility(True)



            # displacementMagnitude by default
            if hasattr(self.ui, "loadedTransformVolume") and displacementVolume:
                try:
                    self.ui.loadedTransformVolume.nodeTypes = ['vtkMRMLScalarVolumeNode']
                except Exception:
                    pass  # already set in setup()
                self.ui.loadedTransformVolume.setEnabled(True)
                self.ui.loadedTransformVolume.setCurrentNode(displacementVolume)


            # fMRI as default colour (unless one already preselected)
            #colorNode = None
            if hasattr(self.ui, "colorMapSelector"):
                colorNode = self.ui.colorMapSelector.currentNode()
            if colorNode is None:
                colorNode = slicer.util.getFirstNodeByClassByName('vtkMRMLColorTableNode', 'fMRI')
            self.ui.colorMapSelector.setEnabled(True)
            self.ui.colorMapSelector.setCurrentNode(colorNode)
            

            self.onLoadDisplacementVolume()


            #if colorNode and dispDisplay:
                #dispDisplay.SetAndObserveColorNodeID(colorNode.GetID())
            # --- end ---

            #if colorNode and dispDisplay:
                #dispDisplay.SetAndObserveColorNodeID(colorNode.GetID())
            # --- end ---




            # self._parameterNode.jacobianMagnitudeVolume = jacobianVolume  # Save for access
            # self._parameterNode.displacementMagnitudeVolume = displacementVolume  # Save for access


            # slicer.util.setSliceViewerLayers(
            #     # background=self._parameterNode.referenceVolume,
            #     background=self._parameterNode.backgroundVolume,
            #     foreground=#displacementVolume#self._parameterNode.displacementMagnitudeVolume
                                
            # )
            
            # TODO: Add this back in if we want to directly load the colour map 
            # colorNode = self.ui.colorMapSelector.currentNode()
            # if colorNode and self._parameterNode.displacementMagnitudeVolume:
            #     print("In 490!!!")
            #     displayNode = self._parameterNode.displacementMagnitudeVolume.GetDisplayNode()
            #     if displayNode:
            #         displayNode.SetAndObserveColorNodeID(colorNode.GetID())







    def onLoadDisplacementVolume(self) -> None:

        '''
        Runs when user selects the Load Volume button
        
        '''

        #selectedVolume = self.ui.existingDisplacementVolumeSelector.currentNode()
        selectedVolume = self.ui.loadedTransformVolume.currentNode()

        if not selectedVolume or not selectedVolume.GetDisplayNode():
            slicer.util.errorDisplay("Please select a volume before loading.")
            return

        usVolume = self.ui.referenceVolume.currentNode()
    
        backgroundVolume = self._parameterNode.backgroundVolume
        
        state = self.ui.enableUsBorderDisplay.checkState()

        #self.logic.showNonZeroWireframe(foregroundVolume=usVolume, state=state, reload=True)
        
        # slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(selectedVolume)    


        # visualize it
        # slicer.util.setSliceViewerLayers(
        #     background=backgroundVolume,
        #     foreground=selectedVolume
        # )
        
        self.onLoadExpertLabelsClicked()

        
        persistentDisplayNode = selectedVolume.GetDisplayNode()

        
    
        # newDisplayNode = slicer.mrmlScene.AddNewNodeByClass(persistentDisplayNode.GetClassName())
        # newDisplayNode.Copy(persistentDisplayNode)
        # #newDisplayNode = originalDisplayNode

        # Attach the new display node to the same volume
        #selectedVolume.RemoveAllDisplayNodeIDs()

        internalDisplayNode = slicer.mrmlScene.AddNewNodeByClass(persistentDisplayNode.GetClassName())
        #internalDisplayNode.Copy(persistentDisplayNode)
        internalDisplayNode = persistentDisplayNode
        selectedVolume.AddAndObserveDisplayNodeID(internalDisplayNode.GetID())

        #persistentDisplayNode.AddAndObserveDisplayNodeID(newDisplayNode.GetID())
        # print(selectedVolume.GetDisplayNode())
        # print(selectedVolume.GetClassName())

        numDisplayNodes = selectedVolume.GetNumberOfDisplayNodes()      
        print(f"Number of display nodes: {numDisplayNodes}")
        print("Update 1")
        try:
            viridisNode = slicer.util.getNode("Viridis")
            internalDisplayNode.SetAndObserveColorNodeID(viridisNode.GetID())
            internalDisplayNode.Modified()
        except slicer.util.MRMLNodeNotFoundException:
            slicer.util.errorDisplay("Viridis colormap not found in the scene.")

        normalizedValue = self.ui.opacitySlider.value / 100
        internalDisplayNode.SetOpacity(normalizedValue)
        
        slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(persistentDisplayNode)

        # Do NOT set it as foreground of another volume to avoid cropping
        for sliceName in slicer.app.layoutManager().sliceViewNames():
            sliceComposite = slicer.app.layoutManager().sliceWidget(sliceName).mrmlSliceCompositeNode()
            sliceComposite.SetBackgroundVolumeID(backgroundVolume.GetID())  # your US/reference
            sliceComposite.SetForegroundVolumeID(selectedVolume.GetID())    # displacement field
            sliceComposite.SetForegroundOpacity(normalizedValue)
            # scalarBar = slicer.app.layoutManager().sliceWidget(sliceName).GetForegroundScalarBarActor()
            # scalarBar.SetTitle("Displacement magnitude")
            # scalarBar.SetNumberOfLabels(5)

        #slicer.util.setSliceViewerLayers(foregroundOpacity=normalizedValue)


        # set max and min of threshold slider
        imageData = selectedVolume.GetImageData()
        #print("Image Data", imageData)
        if imageData:
            minScalar, maxScalar = imageData.GetScalarRange()
            defaultMinValue = minScalar + 0.02 * (maxScalar - minScalar) #Default minimum set to 2%
            self.scalarRange = (float(minScalar), float(maxScalar))  # store exact range
            #print(f"min: {minScalar}, max: {maxScalar}")
            #print(defaultMinValue)
            
            self.ui.thresholdSlider.setRange(minScalar, maxScalar)
            

            self.ui.thresholdMinSpinBox.setSpecialValueText("") #clear 'Minimum Threshold'
            self.ui.thresholdMaxSpinBox.setSpecialValueText("")  
            self.ui.thresholdMinSpinBox.setRange(minScalar, maxScalar)
            self.ui.thresholdMaxSpinBox.setRange(minScalar, maxScalar)
            self.ui.thresholdMinSpinBox.setDecimals(6) 
            self.ui.thresholdMaxSpinBox.setDecimals(6)

            step = (maxScalar - minScalar) / 1000   # 0.1% of range 
        
            self.ui.thresholdSlider.singleStep = step
            self.ui.thresholdMinSpinBox.singleStep = step
            self.ui.thresholdMaxSpinBox.singleStep = step



            #Always set the values after setting the mins/ maxs to avoid caching issues 
            self.ui.thresholdSlider.setValues(minScalar, maxScalar)
            self.ui.thresholdMinSpinBox.setValue(defaultMinValue)  
            self.ui.thresholdMaxSpinBox.setValue(maxScalar)

        displayNode = selectedVolume.GetDisplayNode()
        if displayNode:
            # --- Colour Window (contrast)---

            # Turn off auto window/level to get current manual settings
            displayNode.AutoWindowLevelOff()
            
            window = displayNode.GetWindow()
            
            minWindow = displayNode.GetWindowLevelMin()
            maxWindow = displayNode.GetWindowLevelMax()
            
            print("Current Window:", window)
            print("Window Range:", minWindow, "to", maxWindow)
            
            # Set up the slider
            self.ui.colourWindowSlider.singleStep = step
            self.ui.colourWindowSlider.minimum = minWindow
            self.ui.colourWindowSlider.maximum = maxWindow
            self.ui.colourWindowSlider.value = window  # Set current window as default
            
            # Connect slider to update function
            self.ui.colourWindowSlider.valueChanged.connect(self.onWindowChanged)
            
            # --- Colour Level (brightness)---
            level = displayNode.GetLevel()

            minLevel = displayNode.GetWindowLevelMin()
            maxLevel = displayNode.GetWindowLevelMax()

            print("Current Level:", level)
            print("Level Range:", minLevel, "to", maxLevel)

            # Set up the slider
            self.ui.colourLevelSlider.singleStep = step
            self.ui.colourLevelSlider.minimum = minLevel
            self.ui.colourLevelSlider.maximum = maxLevel
            self.ui.colourLevelSlider.value = level  # Set current level as default

            # Connect slider to update function
            self.ui.colourLevelSlider.valueChanged.connect(self.onLevelChanged)



    def onWindowChanged(self, value):
        """Update the display node when slider changes"""
        volumeNode = self.ui.loadedTransformVolume.currentNode()

        displayNode = volumeNode.GetDisplayNode()
        if displayNode:
            currentLevel = displayNode.GetLevel()
            displayNode.SetWindowLevel(value, currentLevel)


    def onLevelChanged(self, value):
        """Update the display node when level slider changes"""
        volumeNode = self.ui.loadedTransformVolume.currentNode()
        displayNode = volumeNode.GetDisplayNode()
        if displayNode:
            currentWindow = displayNode.GetWindow()
            displayNode.SetWindowLevel(currentWindow, value)


    def onMouseMoved(self, observer, eventid):
        # if markup node doesn't exist do nothing
        if not self.labelMarkupNode.GetDisplayNode().GetVisibility2D():
            return

        ras = [0.0, 0.0, 0.0] 
        self.crosshairNode.GetCursorPositionRAS(ras)
    
        # move label to current RAS position
        self.labelMarkupNode.SetNthControlPointPosition(0, ras)


        # sample displacement volume at that RAS location
        #displacementVolume = self.ui.existingDisplacementVolumeSelector.currentNode()
        displacementVolume = self.ui.loadedTransformVolume.currentNode()

        if not displacementVolume:
            self.labelMarkupNode.SetNthControlPointLabel(0, "No volume")
            return

        # convert RAS to IJK
        rasToIjk = vtk.vtkMatrix4x4()
        displacementVolume.GetRASToIJKMatrix(rasToIjk)
        ijk = [0.0, 0.0, 0.0, 1.0]
        ras_hom = list(ras) + [1.0]
        rasToIjk.MultiplyPoint(ras_hom, ijk)
        ijk = [int(round(i)) for i in ijk[:3]]

        dims = displacementVolume.GetImageData().GetDimensions()
        if any(i < 0 or i >= d for i, d in zip(ijk, dims)):
            self.labelMarkupNode.SetNthControlPointLabel(0, "Out of bounds")
            return

        value = displacementVolume.GetImageData().GetScalarComponentAsDouble(*ijk, 0)
        label = f"{value:.3f} mm"
        self.labelMarkupNode.SetNthControlPointLabel(0, label)


    def onToggleHoverDisplay(self, enabled: bool) -> None:
        print("on Toggle Hover Display")

        self.labelMarkupNode = self.getOrCreateMouseLabelNode()
        disp = self.labelMarkupNode.GetDisplayNode()

        if enabled:
            print("enabled")

            # FORCE all relevant visibilities ON
            self.labelMarkupNode.SetDisplayVisibility(True)       # main visibility toggle
            disp.SetVisibility(True)                              # fallback
            disp.SetVisibility2D(True)
            disp.SetVisibility3D(False)                           # i want 2D only
            disp.SetPointLabelsVisibility(True)                   # show text
            disp.SetTextScale(3.0)                                # ensure label isn't scaled to zero

            if self.crosshairObserverTag is None:
                self.crosshairObserverTag = self.crosshairNode.AddObserver(
                    slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent,
                    self.onMouseMoved
                )

        else:
            # FORCE everything off
            self.labelMarkupNode.SetDisplayVisibility(False)
            disp.SetVisibility(False)
            disp.SetVisibility2D(False)
            disp.SetVisibility3D(False)
            disp.SetPointLabelsVisibility(False)

            if self.crosshairObserverTag is not None:
                self.crosshairNode.RemoveObserver(self.crosshairObserverTag)
                self.crosshairObserverTag = None

    def updateHoverCheckboxFromNode(self):
        # Syncs the hover display checkbox with the actual visibility of the mouse label node 
        self.labelMarkupNode = self.getOrCreateMouseLabelNode()
        disp = self.labelMarkupNode.GetDisplayNode()
        if disp:
            visible = disp.GetVisibility2D() and self.labelMarkupNode.GetDisplayVisibility()
            self.ui.enableHoverDisplayCheckbox.blockSignals(True)
            self.ui.enableHoverDisplayCheckbox.setChecked(visible)
            self.ui.enableHoverDisplayCheckbox.blockSignals(False)

        
    def getOrCreateMouseLabelNode(self):
        node = slicer.mrmlScene.GetFirstNodeByName("BrainShiftModule_MouseValueLabel")
        if node is None:
            node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLMarkupsFiducialNode",
                "BrainShiftModule_MouseValueLabel"
            )
            node.AddControlPoint(0, 0, 0)
            node.SetLocked(True)
            node.SetMarkupLabelFormat("{label}")
            node.GetDisplayNode().SetVisibility2D(False)
            node.GetDisplayNode().SetVisibility3D(False)
            node.SetNthControlPointLabel(0, "")
            node.GetDisplayNode().SetColor([0.0, 0.0, 0.0])
            node.GetDisplayNode().SetSelectedColor([0.0, 0.0, 0.0])
            node.GetDisplayNode().GetTextProperty().SetColor(0.0, 0.0, 0.0)
        return node



    # def getLandmarkLabel(self):
    #     default_text = "Initial Text"
    
    #     # text1 = qt.QInputDialog.getText(self.line_edit, "Please name the first landmark file (derived from the source volume)", "Name: ")
    #     # text2 = qt.QInputDialog.getText(self.line_edit, "Please name the second landmark file (derived from the moving volume)", "Name: ")

    #     text1, ok1 = qt.QInputDialog.getText(
    #         self,  # parent widget
    #         "Please name the first landmark file (derived from the source volume)",
    #         "Name:"
    #     )

    #     text2, ok2 = qt.QInputDialog.getText(
    #         self,
    #         "Please name the second landmark file (derived from the moving volume)",
    #         "Name:"
    #     )
    #     #print(f"User input: '{text}', OK pressed: ")

    #     #print(type(ok))
    #     if text1:
    #         self.line_edit.setText(text1)
    #     if text2:
    #         self.line_edit.setText(text2)

    #     else:
    #         raise Exception("could not rename landmark file")
    #     print("Renamed to: ", text1)
    #     return text1, text2



    def getLandmarkLabel(self):
        parent = slicer.util.mainWindow()  # safe parent for dialogs in Slicer

        # First prompt
        text1 = qt.QInputDialog.getText(
            parent,
            "Please name the first landmark file (derived from the source volume)",
            "Name:",
            qt.QLineEdit.Normal,  # Echo mode required!
            ""                    # default text (optional)
        )

        if not text1:
            slicer.util.errorDisplay("No name provided for first landmark file.")
            return None, None

        # Second prompt
        text2 = qt.QInputDialog.getText(
            parent,
            "Please name the second landmark file (derived from the moving volume)",
            "Name:",
            qt.QLineEdit.Normal,
            ""
        )

        if not text2:
            slicer.util.errorDisplay("No name provided for second landmark file.")
            return None, None

        print("Renamed to:", text1, text2)
        return text1, text2

    # def getLandmarkLabel(self):
    #     default_text = "Initial Text"
    
    #     # text1 = qt.QInputDialog.getText(self.line_edit, "Please name the first landmark file (derived from the source volume)", "Name: ")
    #     # text2 = qt.QInputDialog.getText(self.line_edit, "Please name the second landmark file (derived from the moving volume)", "Name: ")

    #     text1, ok1 = qt.QInputDialog.getText(
    #         self,  # parent widget
    #         "Please name the first landmark file (derived from the source volume)",
    #         "Name:"
    #     )

    #     text2, ok2 = qt.QInputDialog.getText(
    #         self,
    #         "Please name the second landmark file (derived from the moving volume)",
    #         "Name:"
    #     )
    #     #print(f"User input: '{text}', OK pressed: ")

    #     #print(type(ok))
    #     if text1:
    #         self.line_edit.setText(text1)
    #     if text2:
    #         self.line_edit.setText(text2)

    #     else:
    #         raise Exception("could not rename landmark file")
    #     print("Renamed to: ", text1)
    #     return text1, text2

    def getLandmarkLabel(self):
        parent = slicer.util.mainWindow()  # safe parent for dialogs in Slicer

        # First prompt
        text1 = qt.QInputDialog.getText(
            parent,
            "Please name the first landmark file (derived from the source volume)",
            "Name:",
            qt.QLineEdit.Normal,  # Echo mode required!
            ""                    # default text (optional)
        )

        if not text1:
            slicer.util.errorDisplay("No name provided for first landmark file.")
            return None, None

        # Second prompt
        text2 = qt.QInputDialog.getText(
            parent,
            "Please name the second landmark file (derived from the moving volume)",
            "Name:",
            qt.QLineEdit.Normal,
            ""
        )

        if not text2:
            slicer.util.errorDisplay("No name provided for second landmark file.")
            return None, None

        print("Renamed to:", text1, text2)
        return text1, text2



    def onThresholdSliderChanged(self, minValue, maxValue):

        volumeNode = self.ui.loadedTransformVolume.currentNode()
        if not volumeNode:
            logging.warning("No displacement magnitude volume available for thresholding.")
            return
        
        # dynamically set min and max value
        displayNode = volumeNode.GetDisplayNode()


    def onColourWindowSliderChanged(self, minValue, maxValue):

        volumeNode = self.ui.loadedTransformVolume.currentNode()
        if not volumeNode:
            logging.warning("No displacement magnitude volume available for thresholding.")
            return
        
        # dynamically set min and max value
        displayNode = volumeNode.GetDisplayNode()

        displayNode.AutoWindowLevelOff()
        displayNode.SetThreshold(minValue, maxValue)
        displayNode.SetApplyThreshold(True)
        displayNode.Modified()
        logging.info(f"Colour window applied: min = {minValue}, max = {maxValue}")

        self.ui.colourWindowMinSpinBox.blockSignals(True)
        self.ui.colourWindowMaxSpinBox.blockSignals(True)
        self.ui.colourWindowMinSpinBox.setValue(minValue)
        self.ui.colourWindowMaxSpinBox.setValue(maxValue)
        self.ui.colourWindowMinSpinBox.blockSignals(False)
        self.ui.colourWindowMaxSpinBox.blockSignals(False)


    def onThresholdSliderChanged(self, minValue, maxValue):

        volumeNode = self.ui.loadedTransformVolume.currentNode()
        if not volumeNode:
            logging.warning("No displacement magnitude volume available for thresholding.")
            return
        
        # dynamically set min and max value
        displayNode = volumeNode.GetDisplayNode()

        displayNode.AutoWindowLevelOff()
        displayNode.SetThreshold(minValue, maxValue)
        displayNode.SetApplyThreshold(True)
        displayNode.Modified()
        logging.info(f"Threshold applied: min = {minValue}, max = {maxValue}")

        self.ui.thresholdMinSpinBox.blockSignals(True)
        self.ui.thresholdMaxSpinBox.blockSignals(True)
        self.ui.thresholdMinSpinBox.setValue(minValue)
        self.ui.thresholdMaxSpinBox.setValue(maxValue)
        self.ui.thresholdMinSpinBox.blockSignals(False)
        self.ui.thresholdMaxSpinBox.blockSignals(False)


    def onMinSpinBoxChanged(self, value):
        currentMax = self.ui.thresholdMaxSpinBox.value
        self.ui.thresholdSlider.setValues(value, currentMax)

    def onMinColourWindowChanged(self, value):
        currentMax = self.ui.colourWindowMax.value
        self.ui.colourWindowSlider.setValues(value, currentMax)

    def onMaxSpinBoxChanged(self, value):
        currentMin = self.ui.thresholdMinSpinBox.value
        self.ui.thresholdSlider.setValues(currentMin, value)

    def onMaxColourWindowChanged(self, value):
        currentMin = self.ui.colourWindowMax.value
        self.ui.colourWindowSlider.setValues(currentMin, value)

# BrainShiftModuleLogic
class BrainShiftModuleLogic(ScriptedLoadableModuleLogic):
    """Logic for computing voxel-wise displacement from transformation field"""

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def getParameterNode(self):
        return BrainShiftModuleParameterNode(super().getParameterNode())
    
    def countUniqueValues(self, volumeNode: vtkMRMLScalarVolumeNode):

        import numpy as np
        from vtk.util.numpy_support import vtk_to_numpy

        imageData = volumeNode.GetImageData()
        if imageData is None:
            logging.warning("Volume has no image data.")
            return None

        vtk_array = imageData.GetPointData().GetScalars()
        np_array = vtk_to_numpy(vtk_array)

        unique_values = np.unique(np_array)
        logging.info(f"Number of unique values in displacement magnitude volume: {len(unique_values)}")
        return len(unique_values), unique_values


    def loadTagFile(self, filepath, text1, text2):
        print(f"Reading tag file: {filepath}")
        print("Label: ", text2)
        points1, points2 = self.read_tag_file(filepath)
        if points1 is None or points2 is None or len(points1) == 0 or len(points2) == 0:
            logging.error("No valid points found in tag file.")
            return False
        

        # create fiducial nodes in Slicer scene
        fiducialNode1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", f"{text1}") #the set of landmarks from the first volume registered
        fiducialNode2 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", f"{text2}") #the set of landmarks from the second volume registered

        # add points from tag file to the fiducial nodes
        for pt in points1:
            fiducialNode1.AddControlPoint(pt)
        for pt in points2:
            fiducialNode2.AddControlPoint(pt)

        displayNode1 = fiducialNode1.GetDisplayNode()
        if displayNode1:
            displayNode1.SetVisibility(False)            # Hide in 3D
            displayNode1.SetVisibility2D(False)          # Hide in 2D slice views
            displayNode1.SetSelectedColor(0.5, 0.5, 0.5) # Optional: make it less prominent when turned on
            displayNode1.SetTextScale(5.0)               # Hide label text
            #displayNode1.SetGlyphTypeFromString("None")  # Hide glyph icon
            displayNode1.SetHandlesInteractive(False)    # Disable user interaction
            #displayNode1.SetOpacity(1.0)
            #displayNode1.SetGlyphScale(5.0)  
        print("Number of points1:", fiducialNode1.GetNumberOfControlPoints())

        displayNode2 = fiducialNode2.GetDisplayNode()
        if displayNode2:
            displayNode2.SetVisibility(False)            # Hide in 3D
            displayNode2.SetVisibility2D(False)          # Hide in 2D slice views
            displayNode2.SetSelectedColor(0.5, 0.5, 0.5) # Optional: make it less prominent when turned on
            displayNode2.SetTextScale(5.0)               # Hide label text
            displayNode2.SetOpacity(1.0)
            displayNode2.SetGlyphScale(5.0)  
            displayNode2.SetHandlesInteractive(False)    # Disable user interaction
        
        else:
            slicer.util.errorDisplay("Failed to load landmark file.")
        qt.QMessageBox.information(slicer.util.mainWindow(), "Success", "Success! \nLandmark files created and available in Data.")
        print("Number of points2:", fiducialNode1.GetNumberOfControlPoints())

        logging.info("Landmarks loaded and hidden.")
        
        logging.info(f"Created {len(points1)} landmarks in each set.")
        return True
    

    def read_tag_file(self, filepath):
        import numpy as np
        import re

        """Parse the tag file robustly and return two numpy arrays of points."""
        source_points = []
        target_points = []
        try:
            with open(filepath, 'r') as file:
                for line in file:
                    line = line.strip()
                    if line.startswith('%') or not line:
                        continue
                    try:
                        values = list(map(float, re.findall(r"[-+]?\d*\.\d+|\d+", line)))
                        if len(values) >= 6:
                            source_points.append(values[0:3])
                            target_points.append(values[3:6])
                    except ValueError:
                        # skip lines that cannot be parsed into floats
                        continue
        except Exception as e:
            logging.error(f"Failed to read tag file: {e}")
            return None, None
        return np.array(source_points), np.array(target_points)
    


    def computeDisplacementMagnitude(self,
                                 referenceVolume: vtkMRMLScalarVolumeNode,
                                 transformNode:   vtkMRMLTransformNode,
                                 ) -> vtkMRMLScalarVolumeNode:
        """
        Compute voxel-wise displacement magnitude from a BSpline transform.
        Returns a scalar volume node.
        """

        import SimpleITK as sitk
        import sitkUtils

        if not referenceVolume:
            raise ValueError("Reference volume is invalid")
        if not transformNode:
            raise ValueError("Transform node is invalid")
        
        #volumesLogic = slicer.modules.volumes.logic()
        

        # Get reference image as SimpleITK image
        refImage = sitkUtils.PullVolumeFromSlicer(referenceVolume)

       #imageData = refImage.GetImageData()
        print("outputVolume image data: ", refImage)
        
        if refImage is None:
            raise Exception("Reference volume has no image data")
            
        
        # Convert MRML BSpline transform to ITK transform
        itkTx = sitk.ReadTransform(transformNode.GetStorageNode().GetFileName())

        # Resample the transform into a displacement field on the reference grid
        dispField = sitk.TransformToDisplacementField(
            itkTx,
            sitk.sitkVectorFloat64,
            refImage.GetSize(),
            refImage.GetOrigin(),
            refImage.GetSpacing(),
            refImage.GetDirection()
        )

        # Compute magnitude image
        dispMag = sitk.VectorMagnitude(dispField)

        # Push back to Slicer
        outputVolume = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLScalarVolumeNode",
            referenceVolume.GetName() + "_displacementMagnitude"
        )
        sitkUtils.PushVolumeToSlicer(dispMag, outputVolume)
        # Ensure display node exists
        if not outputVolume.GetDisplayNode():
            #slicer.modules.volumes.logic().CreateDefaultDisplayNodes(outputVolume)
            outputVolume.CreateDefaultDisplayNodes()


        displayNode = outputVolume.GetDisplayNode()

        # Disable auto WL/CL so it doesn’t reset every time
        displayNode.AutoWindowLevelOff()
        # displayNode.SetWindow(10.0)
        # displayNode.SetLevel(5.0)

        array = sitk.GetArrayFromImage(dispMag)
        minVal, maxVal = float(array.min()), float(array.max())
        displayNode.SetWindow(maxVal - minVal)
        displayNode.SetLevel((maxVal + minVal) / 2)

        # Apply threshold for visibility
        displayNode.SetThreshold(0.05, 10.0)
        displayNode.SetApplyThreshold(True)

        # Use specific color map if available
        colorNode = slicer.util.getNode("Viridis")
        if colorNode:
            displayNode.SetAndObserveColorNodeID(colorNode.GetID())
        return outputVolume



    def computeJacobianMagnitude(self,
                                referenceVolume: vtkMRMLScalarVolumeNode,
                                transformNode: vtkMRMLTransformNode
                                ) -> vtkMRMLScalarVolumeNode:
        import slicer
        import vtk
        import SimpleITK as sitk
        import sitkUtils
        import numpy as np

        refImage = sitkUtils.PullVolumeFromSlicer(referenceVolume)

        
        itkTx = sitk.ReadTransform(transformNode.GetStorageNode().GetFileName())

        # Convert transform to displacement field in reference grid
        displacementField = sitk.TransformToDisplacementField(
            itkTx,
            sitk.sitkVectorFloat64,
            refImage.GetSize(),
            refImage.GetOrigin(),
            refImage.GetSpacing(),
            refImage.GetDirection()
        )

        # Step 4: Compute Jacobian determinant
        jacDet = sitk.DisplacementFieldJacobianDeterminant(displacementField)

        # Step 5: Take magnitude (absolute value)
        #jacMagnitude = sitk.Abs(jacDet)

        # Step 6: Push result back into Slicer
        outputVolume = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLScalarVolumeNode",
            referenceVolume.GetName() + "_jacobianMagnitude"
        )
        sitkUtils.PushVolumeToSlicer(jacDet, targetNode=outputVolume)

        # Step 7: Display setup
        if not outputVolume.GetDisplayNode():
            outputVolume.CreateDefaultDisplayNodes()

        displayNode = outputVolume.GetDisplayNode()
        displayNode.AutoWindowLevelOff()
        # displayNode.SetWindow(5.0)
        # displayNode.SetLevel(2.5)
        array = sitk.GetArrayFromImage(jacDet)
        minVal, maxVal = float(array.min()), float(array.max())
        displayNode.SetWindow(maxVal - minVal)
        displayNode.SetLevel((maxVal + minVal) / 2)

        colorNode = slicer.util.getNode("Inferno")
        if colorNode:
            displayNode.SetAndObserveColorNodeID(colorNode.GetID())

        # Step 8: Store in UI and parameter node
        #self.ui.jacobianMagnitudeVolume.setCurrentNode(outputVolume)
        #self._parameterNode().SetNodeReferenceID("jacobianMagnitudeVolume", outputVolume.GetID())

        return outputVolume




    def showNonZeroWireframe(self, foregroundVolume, state, reload=False, modelName="NonZeroWireframe"):
        """
        Extracts the non-zero region of a volume and displays its surface wireframe
        as a non-destructive 3D overlay using a vtkModelNode.
        """
        import slicer
        import vtk
        import numpy as np
        import SimpleITK as sitk
        import sitkUtils
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)

        currentModelNode = slicer.mrmlScene.GetFirstNodeByName(modelName)
        if currentModelNode:
            currentDisplayNode = currentModelNode.GetDisplayNode()
            if not reload:
                if not state:
                    currentDisplayNode.SetVisibility2D(False)
                    return
                currentDisplayNode.SetVisibility2D(True)
                return

            slicer.mrmlScene.RemoveNode(currentDisplayNode)
            slicer.mrmlScene.RemoveNode(currentModelNode)

        #print("Starting showNonZeroWireframe...")
        # Step 1: Convert foreground image to binary mask
        #print("Step 1: Pulling volume from Slicer for node: %s", foregroundVolume.GetName())
        image_sitk = sitkUtils.PullVolumeFromSlicer(foregroundVolume)
        arr = sitk.GetArrayFromImage(image_sitk)
        nonzero_voxels = np.count_nonzero(arr)
        #print("Step 1b: Number of non-zero voxels: %d", nonzero_voxels)

        if nonzero_voxels == 0:
            logger.warning("WARNING: No non-zero voxels found in the image. Aborting wireframe display.")
            return

        mask_arr = (arr != 0).astype(np.uint8)
        mask_sitk = sitk.GetImageFromArray(mask_arr)
        mask_sitk.CopyInformation(image_sitk)
        #print("Step 1b: Converted to binary mask.")

        # Push to Slicer as labelmap
        labelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "TempBinaryMask")
        sitkUtils.PushVolumeToSlicer(mask_sitk, targetNode=labelNode)
        #print("Step 1 done: Binary mask pushed to Slicer label node: %s", labelNode.GetName())

        # Step 2: Extract surface using marching cubes
        imageData = labelNode.GetImageData()
        if imageData is None:
            print("WARNING: Image data is None. Check label node data.")
            return

        #print("Step 2: Starting marching cubes...")
        marching = vtk.vtkDiscreteMarchingCubes()
        marching.SetInputData(imageData)
        marching.SetValue(0, 1)
        marching.Update()
        surface = marching.GetOutput()
        if surface is None or surface.GetNumberOfPoints() == 0:
            print("WARNING: No surface generated by marching cubes.")
            return

        # Step 3: Extract wireframe edges from the surface mesh
        #print("Step 3: Extracting edges from surface...")
        edges = vtk.vtkExtractEdges()
        edges.SetInputConnection(marching.GetOutputPort())
        edges.Update()

        # Step 4: Create and show model node with only edges
        #print("Step 4: Preparing model node '%s'...", modelName)
        newModelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", modelName)
       # print("STep 4 done: Created new model node.")
        newModelNode.SetAndObservePolyData(edges.GetOutput())

        # Match spatial transform
        #print("Step 5: Applying spatial transform (IJK to RAS)...")
        transform = vtk.vtkTransform()
        ijkToRAS = vtk.vtkMatrix4x4()
        labelNode.GetIJKToRASMatrix(ijkToRAS)
        transform.SetMatrix(ijkToRAS)
        transformFilter = vtk.vtkTransformPolyDataFilter()
        transformFilter.SetTransform(transform)
        transformFilter.SetInputData(edges.GetOutput())
        transformFilter.Update()
        newModelNode.SetAndObservePolyData(transformFilter.GetOutput())

        # Step 6: Set wireframe-only display
        #print("Step 6: Setting display properties for wireframe...")
        displayNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelDisplayNode")

        #slicer.mrmlScene.AddNode(displayNode)
        newModelNode.SetAndObserveDisplayNodeID(displayNode.GetID())
        #print("Done: Created and linked display node.")

        displayNode.SetRepresentation(0)  # Wireframe
        displayNode.SetColor(0, 0, 0)     # Green
        displayNode.SetEdgeVisibility(True)
        displayNode.SetPointSize(3.0)
        displayNode.SetSliceIntersectionThickness(2)

        displayNode.SetVisibility3D(False)
        displayNode.SetVisibility2D(True)

        # Optional: remove temp label node
        slicer.mrmlScene.RemoveNode(labelNode)
        #print("Temporary label node removed. Done!")

        return newModelNode
