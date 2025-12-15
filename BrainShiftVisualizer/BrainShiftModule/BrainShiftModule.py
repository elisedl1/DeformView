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
from slicer import vtkMRMLColorTableNode
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

        self.ui.loadedTransformVolume.connect("currentNodeChanged(vtkMRMLNode*)", 
                                          self.onTransformVolumeChanged)
        # connect
        self.ui.loadDisplacementVolumeButton.connect("clicked(bool)", self.onLoadDisplacementVolume)

        # Color selector
        # self.cleanupDuplicateColorNodes("ColdToHotRainbow")

        # # Force remove ALL nodes with these names
        # for name in ["ColdToHotRainbow", "HotToColdRainbow", "DivergingBlueRed", 
        #             "Isodose_ColorTable_Default", "Isodose_ColorTable_Relative"]:
        #     nodes = slicer.util.getNodesByClass('vtkMRMLColorNode')
        #     for node in nodes:
        #         if node.GetName() == name:
        #             print(f"Removing {name}")
        #             slicer.mrmlScene.RemoveNode(node)

        self.enableVTKErrorTracking()

        self.cleanupDuplicateColorNodes("JacobianMap")

        self.resetBuiltInColorNodes()
        #self.resetAllColorNodes()
        self.selectColourMap()



        # mouse displayer
        self.crosshairNode = slicer.util.getNode("Crosshair")

        # self.labelMarkupNode = slicer.util.getModule("Data").mrmlScene().GetFirstNodeByName("BrainShiftModule_MouseValueLabel")
        #Need to dynamically set the labelMarkupNode, depending on which label is being loaded by loadDisplacementVolume
        #Set to None initially so it can be created dynamically?
        self.labelMarkupNode = None 
        #Functionality moved to self.getOrCreateLabelNodeForCurrentVolume
  
        self.crosshairObserverTag = None

        self.ui.enableHoverDisplayCheckbox.setChecked(False)  # start disabled
        self.ui.enableHoverDisplayCheckbox.connect("toggled(bool)", self.onToggleHoverDisplay)


        self.ui.enableDisplacementVisualizationCheckbox.setChecked(False)  # start disabled
        self.ui.enableDisplacementVisualizationCheckbox.connect("toggled(bool)", self.onToggleDisplacementVisualizationDisplay)



    
        
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

        

    import numpy as np

    def enableVTKErrorTracking(self):
        """Enable detailed VTK error tracking with stack traces"""
        import vtk
        
        # Create an error observer
        def errorCallback(obj, event):
            import traceback
            print("\n" + "="*60)
            print("VTK ERROR DETECTED:")
            print("="*60)
            traceback.print_stack()
            print("="*60 + "\n")
        
        # Add observer to VTK output window
        errorObserver = vtk.vtkFileOutputWindow()
        vtk.vtkOutputWindow.SetInstance(errorObserver)
        
        # You can also observe specific objects
        return errorCallback
    

    def resetBuiltInColorNodes(self):
        """Reset built-in color nodes to defaults"""
        colorLogic = slicer.modules.colors.logic()
        # This will reload all default color nodes
        colorLogic.RemoveDefaultColorNodes()

        colorLogic.AddDefaultColorNodes()

        
    def cleanupCorruptedColormaps(self, name_str, type_str):
        """
        Remove corrupted/empty color nodes and recreate them properly.
        Returns True if node was created/recreated, False if already valid.
        """
        print(f"Checking {name_str}...")
        
        # Find the node
        node = slicer.mrmlScene.GetFirstNodeByName(name_str)
        
        # Case 1: Node doesn't exist - create it
        if not node:
            print(f"  {name_str} doesn't exist, creating...")
            self.create_colour_node(name_str, type_str)
            return True  # We created it
        
        # Case 2: Node exists - check if it's corrupted
        is_corrupted = False
        
        # Check 1: Is it a procedural node when it should be a table node?
        if node.GetClassName() == "vtkMRMLProceduralColorNode":
            print(f"  {name_str} is procedural node (should be color table)")
            is_corrupted = True
        
        # Check 2: Does it have a valid lookup table?
        if hasattr(node, 'GetLookupTable'):
            lut = node.GetLookupTable()
            if not lut or lut.GetNumberOfTableValues() == 0:
                print(f"  {name_str} has no lookup table")
                is_corrupted = True
            else:
                # Check if all colors are black (empty/corrupted)
                all_black = True
                for i in range(min(10, lut.GetNumberOfTableValues())):
                    rgba = lut.GetTableValue(i)
                    if rgba[0] > 0.01 or rgba[1] > 0.01 or rgba[2] > 0.01:
                        all_black = False
                        break
                
                if all_black:
                    print(f"  {name_str} has all-black colors (corrupted)")
                    is_corrupted = True
        
        # Check 3: Does it have any colors defined?
        if hasattr(node, 'GetNumberOfColors'):
            num_colors = node.GetNumberOfColors()
            if num_colors == 0:
                print(f"  {name_str} has 0 colors")
                is_corrupted = True
        
        # Case 3: If corrupted, remove and recreate
        if is_corrupted:
            print(f"  Removing corrupted {name_str}")
            slicer.mrmlScene.RemoveNode(node)
            print(f"  Recreating {name_str}")
            self.create_colour_node(name_str, type_str)
            return True  # We recreated it
        
        # Case 4: Node exists and is valid
        print(f"  ✓ {name_str} is valid")
        node.SetAttribute("MyColourMaps", "1")
        return False  # No changes needed



    
    def selectColourMap(self):
        """
        Set up the color map selector with available colormaps.
        Only creates colormaps that don't already exist.
        """
        
        # Set the scene FIRST
        self.ui.colorMapSelector.setMRMLScene(slicer.mrmlScene)
  
        # Disable automatic sorting
        self.ui.colorMapSelector.sortFilterProxyModel().sort(-1)
        
        # Configure node types
        self.ui.colorMapSelector.nodeTypes = [
            #f"{jacobianColorNode}",
            "vtkMRMLColorTableNode",
            "vtkMRMLProceduralColorNode",
            "vtkMRMLPETColorNode",
            "vtkMRMLColorTableNodeFile"
        ]
        
        # Filter: only show nodes with "MyColourMaps" attribute
        # self.ui.colorMapSelector.addAttribute(f"{jacobianColorNode}", "MyColourMaps", "1")
        self.ui.colorMapSelector.addAttribute("vtkMRMLColorTableNode", "MyColourMaps", "1")
        self.ui.colorMapSelector.addAttribute("vtkMRMLProceduralColorNode", "MyColourMaps", "1")
        self.ui.colorMapSelector.addAttribute("vtkMRMLPETColorNode", "MyColourMaps", "1")
        self.ui.colorMapSelector.addAttribute("vtkMRMLColorTableNodeFile", "MyColourMaps", "1")
        #self.ui.colorMapSelector.AddDefaultFileNodes()
        #slicer.util.AddDefaultFileNodes()
        #colorLogic = slicer.modules.colors.logic()
        # The color nodes are already in the scene

        # allColorNodes = slicer.util.getNodesByClass('vtkMRMLColorTableNode')
        # for node in allColorNodes:
        #     print(f"{node.GetID()} - {node.GetName()}")
      
        # Create Jacobian color node
        jacobianColorNode = self.createJacobianColorNode()

        # List of colormaps to ensure exist
        nodes_to_add = [
            ("HotToColdRainbow", "vtkMRMLColorTableNodeFileHotToColdRainbow.txt"),
            ("DivergingBlueRed", "vtkMRMLColorTableNodeFileDivergingBlueRed.txt"),
            ("FullRainbow", "vtkMRMLColorTableNodeFullRainbow"),
            ("Iron", "vtkMRMLColorTableNodeIron"),
            ("Grey", "vtkMRMLColorTableNodeGrey"),
            ("Plasma", "vtkMRMLColorTableNodeFilePlasma.txt"),
            ("Cividis", "vtkMRMLColorTableNodeFileCividis.txt"),
            ("Inferno", "vtkMRMLColorTableNodeFileInferno.txt"),
            ("Viridis", "vtkMRMLColorTableNodeFileViridis.txt"),
            ("Rainbow", "vtkMRMLColorTableNodeRainbow"),
            ("Ocean", "vtkMRMLColorTableNodeOcean"),
            ("InvertedGrey", "vtkMRMLColorTableNodeInvertedGrey"),
            ("fMRI", "vtkMRMLColorTableNodefMRI"),
            ("Yellow", "vtkMRMLColorTableNodeYellow"),
            ("Warm1", "vtkMRMLColorTableNodeWarm1"),
            ("Magma", "vtkMRMLColorTableNodeFileMagma.txt"),
            #("Isodose_ColorTable_Relative", "Isodose_ColorTable_Relative"),
        ]

        # CRITICAL FIX: Only create if doesn't exist
        #for name_str, node_ID in nodes_to_add:
            # self.cleanupCorruptedColormaps(name_str, type_str)
            #existing = slicer.mrmlScene.GetFirstNodeByName(name_str)
            #existing = slicer.mrmlScene.GetNodeByID(f'{node_ID}')

                #existing = None

            #if not existing:
                #Only create if it doesn't exist

            #print(f"Creating colormap: {name_str}")
        #    new_node = self.create_colour_node(name_str, node_ID)
    # Add display order attribute
        for index, (name_str, node_ID) in enumerate(nodes_to_add):
            node = self.create_colour_node(name_str, node_ID)
            if node:
                #node.SetAttribute("DisplayOrder", str(index))
                node.SetAttribute("SortOrder", f"{index:03d}")

        # else:
        proxyModel = self.ui.colorMapSelector.sortFilterProxyModel()

        #     existing.SetAttribute("MyColourMaps", "1")
        #     print(f"Colormap {name_str} already exists, skipping")
    
        # for name_str, type_str in nodes_to_add:
        #     self.cleanupCorruptedColormaps(name_str, type_str)
    

        #self.verify_colormap("Viridis")
          # Set default to Rainbow
        HotToColdRainbowNode = slicer.mrmlScene.GetNodeByID(f'vtkMRMLColorTableNodeFileHotToColdRainbow.txt')
        self.defaultColorNodeID = 'vtkMRMLColorTableNodeFileHotToColdRainbow.txt'
        print(self.defaultColorNodeID)
        #ColdToHotRainbowNode = slicer.mrmlScene.GetFirstNodeByName("HotToColdRainbow")
        if HotToColdRainbowNode:
            self.ui.colorMapSelector.setCurrentNode(HotToColdRainbowNode)
            #self.ui.colorMapSelector.Attribute("DefaultColourMap", "vtkMRMLColorTableNodeFileHotToColdRainbow.txt")
            #self.ui.colorMapSelector.addAttribute("vtkMRMLColorTableNode", "DefaultColourMap", "vtkMRMLColorTableNodeFileHotToColdRainbow.txt")


    def diagnose_colormap_application(self, volumeNode):
        """
        Diagnose why the colormap isn't showing correctly
        """
        print("\n=== COLORMAP DIAGNOSTIC ===")
        
        if not volumeNode:
            print("No volume node!")
            return
        
        print(f"Volume: {volumeNode.GetName()}")
        
        # Check image data
        imageData = volumeNode.GetImageData()
        if imageData:
            scalarRange = imageData.GetScalarRange()
            numComponents = imageData.GetNumberOfScalarComponents()
            print(f"  Scalar range: {scalarRange}")
            print(f"  Components: {numComponents}")
        
        # Check display node
        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            print("  ERROR: No display node!")
            return
        
        print(f"  Display node exists: Yes")
        
        # Check color node
        colorNodeID = displayNode.GetColorNodeID()
        if not colorNodeID:
            print("  ERROR: No color node ID set!")
            return
        
        print(f"  Color node ID: {colorNodeID}")
        
        colorNode = slicer.mrmlScene.GetNodeByID(colorNodeID)
        if not colorNode:
            print("  ERROR: Color node not found in scene!")
            return
        
        print(f"  Color node: {colorNode.GetName()}")
        print(f"  Color node type: {colorNode.GetClassName()}")
        
        # Check lookup table
        if hasattr(colorNode, 'GetLookupTable'):
            lut = colorNode.GetLookupTable()
            if lut:
                lutRange = lut.GetRange()
                print(f"  LUT range: {lutRange}")
                print(f"  LUT entries: {lut.GetNumberOfTableValues()}")
            else:
                print("  ERROR: No lookup table!")
        
        # Check window/level settings
        window = displayNode.GetWindow()
        level = displayNode.GetLevel()
        print(f"  Window: {window}")
        print(f"  Level: {level}")
        
        # Check if auto window/level is on
        autoWL = displayNode.GetAutoWindowLevel()
        print(f"  Auto window/level: {autoWL}")
        
        # Check scalar range on display node
        displayScalarRange = displayNode.GetScalarRange()
        print(f"  Display scalar range: {displayScalarRange}")
        
        # Check color mapping
        colorMapping = displayNode.GetScalarRangeFlag()
        print(f"  Scalar range flag: {colorMapping}")
        print(f"    0 = Manual, 1 = Use color node scalar range, 2 = Use data scalar range")
        
        print("=== END DIAGNOSTIC ===\n")


    def create_colour_node_from_matplotlib(self, name_str, cmap_name, num_colors=256):
        """
        Create a properly configured 3D Slicer color node from matplotlib colormap.
        """
        try:
            import matplotlib
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError as e:
            print(f"Matplotlib not available: {e}")
            return None
        
        # Remove existing node if present
        #node = slicer.mrmlScene.GetFirstNodeByName(name_str)
        existing_node = slicer.mrmlScene.GetFirstNodeByName(name_str)
        if existing_node:
            #print(f"Matplotlib colormap {name_str} already exists")
            return existing_node
        # if node:
        #     slicer.mrmlScene.RemoveNode(node)
        
        try:
            mpl_cmap = matplotlib.colormaps[cmap_name].resampled(num_colors)
        except:
            mpl_cmap = plt.cm.get_cmap(cmap_name, num_colors)
        
        # Get RGBA values from matplotlib
        colors_rgba = mpl_cmap(np.linspace(0, 1, num_colors))
        
        # Use ColorTableNode
        colorNode = slicer.vtkMRMLColorTableNode()
        colorNode.SetTypeToUser()
        colorNode.SetNumberOfColors(num_colors)
        colorNode.SetName(name_str)
        #colorNode.SetAttribute("Category", "Matplotlib")
        
        # CRITICAL FIX: Set the range to match how Slicer maps values
        # Slicer typically uses the actual data range, not 0-255
        lookupTable = colorNode.GetLookupTable()
        lookupTable.SetNumberOfTableValues(num_colors)
        
        # Use normalized range (0.0 to 1.0) instead of (0 to 255)
        # This matches how other Slicer colormaps work
        lookupTable.SetRange(0.0, 255.0)
        lookupTable.SetRampToLinear()
        
        # Set each color
        for i, (r, g, b, a) in enumerate(colors_rgba):
            colorNode.SetColor(i, f"{cmap_name}_{i}", r, g, b, a)
            # Map to normalized range
            normalized_value = i / (num_colors - 1.0)
            lookupTable.SetTableValue(i, r, g, b, a)
        
        # Build and configure the lookup table
        lookupTable.Build()
        
        # IMPORTANT: Set these properties to match Slicer's behavior
        colorNode.SetNamesInitialised(True)
        colorNode.SaveWithSceneOff()  # Don't save with scene (like built-in colormaps)
        
        # Add to scene
        slicer.mrmlScene.AddNode(colorNode)
        colorNode.SetAttribute("MyColourMaps", "1")
        
        print(f"Created matplotlib colormap: {name_str} with {num_colors} colors")
        print(f"  ✓ Lookup table validated: {num_colors} entries")
        print(f"  Range: {lookupTable.GetRange()}")
        

        return colorNode

    import numpy as np

    def verify_colormap(self, colorNodeName):
        """
        Verify a colormap has a valid lookup table
        """
        colorNode = slicer.mrmlScene.GetFirstNodeByName(colorNodeName)
        if not colorNode:
            print(f"Color node '{colorNodeName}' not found")
            return False
        
        print(f"\n=== Verifying {colorNodeName} ===")
        print(f"Type: {colorNode.GetClassName()}")
        print(f"Number of colors: {colorNode.GetNumberOfColors()}")
        
        # Check if it has a lookup table
        if hasattr(colorNode, 'GetLookupTable'):
            lut = colorNode.GetLookupTable()
            if lut:
                print(f"Lookup table: {lut.GetNumberOfTableValues()} values")
                print(f"Range: {lut.GetRange()}")
                print("✓ Valid lookup table")
                return True
            else:
                print("✗ No lookup table!")
                return False
        else:
            print("✗ No GetLookupTable method")
            return False

# Test it:

    def create_colour_table_from_matplotlib(self, name_str, cmap_name, num_colors=256):
        """
        Alternative: Create a ColorTableNode (discrete) instead of ProceduralColorNode.
        This can sometimes work better for certain display nodes.
        """
        try:
            import matplotlib
            import matplotlib.pyplot as plt
            import numpy as np

        except ImportError:
            print("Matplotlib not available.")
            return None
        
        # Remove existing node
        node = slicer.mrmlScene.GetFirstNodeByName(f"{name_str}")
        # if node:
        #     slicer.mrmlScene.RemoveNode(node)
        
        # Get matplotlib colormap
        try:
            mpl_cmap = matplotlib.colormaps[cmap_name].resampled(num_colors)
        except:
            mpl_cmap = plt.cm.get_cmap(cmap_name, num_colors)
        
        # Get RGBA values
        colors_rgba = mpl_cmap(np.linspace(0, 1, num_colors))
        
        # Create color table node (discrete)
        colorNode = slicer.vtkMRMLColorTableNode()
        colorNode.SetTypeToUser()  # User-defined color table
        colorNode.SetNumberOfColors(num_colors)
        colorNode.SetName(name_str)
        colorNode.SetAttribute("Category", "Matplotlib")
        
        # Set each color
        for i, (r, g, b, a) in enumerate(colors_rgba):
            colorNode.SetColor(i, f"color_{i}", r, g, b, a)
        
        # Add to scene
        slicer.mrmlScene.AddNode(colorNode)
        colorNode.SetAttribute("MyColourMaps", "1")
        
        return colorNode

   
   
    # def create_colour_node(self, name_str, type_str="ColdToHot", use_table=False):
    #     """
    #     Unified function to create color nodes.
        
    #     Args:
    #         name_str: Name for the color node
    #         type_str: Type of colormap
    #         use_table: If True, creates ColorTableNode instead of ProceduralColorNode
    #     """
    #     # Remove existing node
    #     #node = slicer.mrmlScene.GetFirstNodeByName(name_str)
    #     existing_node = slicer.mrmlScene.GetFirstNodeByName(name_str)
    #     if existing_node:
    #         # CRITICAL FIX: Set the attribute even on existing nodes
    #         existing_node.SetAttribute("MyColourMaps", "1")
    #         print(f"Color node {name_str} already exists, tagged for selector")
    #         return existing_node
    #     # if node:
    #     #     slicer.mrmlScene.RemoveNode(node)
        
    #     # Try built-in vtkMRMLColorTableNode types first
    #     try:
    #         node = slicer.vtkMRMLColorTableNode()
    #         typeFunction = getattr(node, f"SetTypeTo{type_str}")
    #         typeFunction()
    #         node.SetName(name_str)
    #         slicer.mrmlScene.AddNode(node)
    #         node.SetAttribute("MyColourMaps", "1")
    #         print(f"Created built-in color table: {name_str}")
    #         return node
    #     except AttributeError:
    #         pass  # Type doesn't exist, try matplotlib
        
    #     # Matplotlib colormaps
    #     matplotlib_maps = {
    #         'Viridis': 'viridis',
    #         'Plasma': 'plasma', 
    #         'Inferno': 'inferno',
    #         'Magma': 'magma',
    #         'Cividis': 'cividis',
    #         'Turbo': 'turbo',
    #         'RdBu': 'RdBu',
    #         'Spectral': 'Spectral',
    #     }
        
    #     if type_str in matplotlib_maps:
    #         print(f"Creating {type_str} from matplotlib")
    #         if use_table:
    #             return self.create_colour_table_from_matplotlib(name_str, matplotlib_maps[type_str])
    #         else:
    #             return self.create_colour_node_from_matplotlib(name_str, matplotlib_maps[type_str])
        
    #     # Access the ColdToHotRainbow color map
    # #     node = slicer.util.getNode('ColdToHotRainbow')


    #     node = slicer.mrmlScene.GetNodeByID('vtkMRMLColorTableNodeFileHotToColdRainbow.txt')

    # #    #node = slicer.mrmlScene.GetNodeByID('FilePlasma.txt')
    #     node.SetName("HotToColdRainbow")
    #     slicer.mrmlScene.AddNode(node)
    #     node.SetAttribute("MyColourMaps", "1")
    #     #print(f"Created built-in color table: Attmept")


    #     # Or use the display name
    #     #node = slicer.util.getNode('ColdToHotRainbow')
    #     #node = slicer.util.getNode('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
    #     # colorLogic = slicer.modules.colors.logic()
    #     # colorNode = colorLogic.GetColorTableNodeID('ColdToHotRainbow')
    #     # if colorNode:
    #     #     node = slicer.mrmlScene.GetNodeByID(colorNode)
    #     # Fallback: create empty procedural node
    #     #print(f"Creating empty procedural node for {name_str}")
    #     # node = slicer.vtkMRMLProceduralColorNode()
    #     # print(dir(node))
    #     # node.SetNumberOfTableValues(256)
    #     # node.GetColorTransferFunction()
    #     # node.SetName(name_str)
    #     # slicer.mrmlScene.AddNode(node)
    #     # node.SetAttribute("MyColourMaps", "1")
    #     # if node:
    #     #     print(f"Node type: {node.GetClassName()}")
    #     #     print(f"Has GetLookupTable: {hasattr(node, 'GetLookupTable')}")
    #     #     if hasattr(node, 'GetLookupTable'):
    #     #         lut = node.GetLookupTable()
    #     #         if lut:
    #     #             print(f"LUT has {lut.GetNumberOfTableValues()} values")
    #     #             print(f"LUT range: {lut.GetRange()}")
    #     #             # Show first color
    #     #             rgba = lut.GetTableValue(0)
    #     #             print(f"First color: {rgba}")
    #     #         else:
    #     #             print("LUT is None")
    #     #     print(f"Number of colors: {node.GetNumberOfColors()}")
        
    #     return node

    def create_colour_node(self, name_str, node_ID=None, use_table=False):
        """
        Unified function to create color nodes.
        
        Args:
            name_str: Name for the color node
            type_str: Type of colormap
            use_table: If True, creates ColorTableNode instead of ProceduralColorNode
        """
        # Remove existing node
        #node = slicer.mrmlScene.GetFirstNodeByName(name_str)
        #existing_node = slicer.mrmlScene.GetFirstNodeByName(name_str)
        existing_node = slicer.mrmlScene.GetNodeByID(f'{node_ID}')
        if existing_node:
            existing_node.SetName(name_str)
            # CRITICAL FIX: Set the attribute even on existing nodes
            existing_node.SetAttribute("MyColourMaps", "1")
            #existing_node.SetName(f"{name_str}")
            #existing_node.SetName(name_str)
            #existing_node.SetSingletonTag(name_str)  # This prevents duplicates
    
           #print(f"Color node {name_str} already exists")
            return existing_node
        
        # if node:
        #     slicer.mrmlScene.RemoveNode(node)
        
        # Try built-in vtkMRMLColorTableNode types first
        try:
            node = slicer.mrmlScene.GetNodeByID(f'{node_ID}')
            #node = slicer.mrmlScene.GetNodeByID('FilePlasma.txt')
            # if name_str.endswith("_1"):
            #     name_str = name_str.replace("_1", "")
            node.SetName(name_str)
            #node.SetSingletonTag(name_str)
            #node.SetDisplayName(f"{name_str}")

            slicer.mrmlScene.AddNode(node)
            node.SetAttribute("MyColourMaps", "1")
            if node.GetName() != name_str:
                node.SetName(name_str)
            return node
        
        except AttributeError:
            print(f"Failed to make {name_str}!")
            pass  # Type doesn't exist, try matplotlib
        
        # # Matplotlib colormaps
        # matplotlib_maps = {
        #     'Viridis': 'viridis',
        #     'Plasma': 'plasma', 
        #     'Inferno': 'inferno',
        #     'Magma': 'magma',
        #     'Cividis': 'cividis',
        #     'Turbo': 'turbo',
        #     'RdBu': 'RdBu',
        #     'Spectral': 'Spectral',
        # }
        
        # if type_str in matplotlib_maps:
        #     print(f"Creating {type_str} from matplotlib")
        #     if use_table:
        #         return self.create_colour_table_from_matplotlib(name_str, matplotlib_maps[type_str])
        #     else:
        #         return self.create_colour_node_from_matplotlib(name_str, matplotlib_maps[type_str])
        
        # Access the ColdToHotRainbow color map
    #     node = slicer.util.getNode('ColdToHotRainbow')


       
        #print(f"Created built-in color table: Attmept")


     
        return node


    def create_matplotlib_colormaps_only(self):
        """
        Create matplotlib colormaps during setup WITHOUT modifying any volumes.
        Only creates the color nodes if they don't already exist.
        """
        matplotlib_maps = {
            'Viridis': 'viridis',
            'Plasma': 'plasma', 
            'Inferno': 'inferno',
            'Magma': 'magma',
            'Cividis': 'cividis',
        }
        
        for name, mpl_name in matplotlib_maps.items():
            # Check if it already exists
            existing = slicer.mrmlScene.GetFirstNodeByName(name)
            if existing:
                #print(f"Colormap {name} already exists, skipping")
                continue
            
            # Create it
            try:
                node = self.create_colour_node_from_matplotlib(name, mpl_name)
                if node:
                    print(f"Created {name}")
            except Exception as e:
                print(f"Failed to create {name}: {e}")



   

    def onTransformVolumeChanged(self):
        """Called whenever a different volume is selected in loadedTransformVolume"""
        volumeNode = self.ui.loadedTransformVolume.currentNode()
        
        if not volumeNode:
            return
        
        # Get the shared label node
        labelNodeName = "BrainShiftModule_MouseValueLabel"
        labelNode = slicer.mrmlScene.GetFirstNodeByName(labelNodeName)
        
        if not labelNode:
            # Create it if it doesn't exist
            self.labelMarkupNode = self.getOrCreateLabelNodeForCurrentVolume()
            return
        
        # Reset the label node for the new volume
        # Check if this volume already has a stored reference
        labelNodeID = volumeNode.GetAttribute("BrainShiftModule_LabelNodeID")
        
        if not labelNodeID or labelNodeID != labelNode.GetID():
            # Associate the shared label node with this volume
            volumeNode.SetAttribute("BrainShiftModule_LabelNodeID", labelNode.GetID())
        
        # Reset label display
        labelNode.SetNthControlPointLabel(0, "")
        labelNode.SetNthControlPointPosition(0, 0, 0, 0)
        
        # Update the reference
        self.labelMarkupNode = labelNode




    def getOrCreateLabelNodeForCurrentVolume(self):
        """Get or create a label node specific to the currently loaded volume"""
        
        volumeNode = self.ui.loadedTransformVolume.currentNode()
        
        # Get or create the single shared label node
        labelNodeName = "BrainShiftModule_MouseValueLabel"
        node = slicer.mrmlScene.GetFirstNodeByName(labelNodeName)
        # node.GetDisplayNode().SetGlyphScale(8)
        
        if not node:
            node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLMarkupsFiducialNode",
                labelNodeName
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
        
        # Store reference on volume
        # volumeNode.SetAttribute("BrainShiftModule_LabelNodeID", node.GetID())
        
        return node
        



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
        processingLayout.addRow("Colour Map:", self.ui.colorMapSelector)
        

        visualizeVolumeLayout = qt.QHBoxLayout()
        visualizeVolumeLayout.addWidget(self.ui.enableDisplacementVisualizationCheckbox)
        visualizeVolumeLayout.addWidget(self.ui.enableHoverDisplayCheckbox)

        # visualizeVolumeLayout.addSpacing(5)
        visualizeVolumeLayout.addWidget(self.ui.loadDisplacementVolumeButton)  # Stretch factor
        #landmarkLayout.setLabelAlignment(qt.Qt.AlignRight | qt.Qt.AlignVCenter)

        processingLayout.addRow(" ", visualizeVolumeLayout)
        
        

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



        # MARKUP TEXT SIZE
        markupTextSizeLayout = qt.QVBoxLayout()
        markupTextSizeLayout.setSpacing(5)
        #vizLayout.addRow("Colour Window:", self.ui.colourWindowSlider)
        colourmarkupTextSizeSliderLayout = qt.QHBoxLayout()
        colourmarkupTextSizeSliderLayout.addWidget(self.ui.markupTextSizeSlider)
        markupTextSizeLayout.addLayout(colourmarkupTextSizeSliderLayout)
        vizLayout.addRow("Text size :", markupTextSizeLayout)

        # MARKUP SIZE
        # markupSizeSlider
        markupSizeLayout = qt.QVBoxLayout()
        markupSizeLayout.setSpacing(5)
        colourmarkupSizeSliderLayout = qt.QHBoxLayout()
        colourmarkupSizeSliderLayout.addWidget(self.ui.markupSizeSlider)
        markupSizeLayout.addLayout(colourmarkupSizeSliderLayout)
        vizLayout.addRow("Cursor size :", markupSizeLayout)


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
    

    def cleanupDuplicateColorNodes(self, nodeName):
        """
        Remove all but the first instance of a color node
        """
        allNodes = slicer.mrmlScene.GetNodesByName(nodeName)
        allNodes.InitTraversal()
        
        nodes_to_remove = []
        first_node = None
        
        for i in range(allNodes.GetNumberOfItems()):
            node = allNodes.GetNextItemAsObject()
            if i == 0:
                first_node = node
                print(f"Keeping {nodeName} (ID: {node.GetID()})")
            else:
                nodes_to_remove.append(node)
                print(f"Will remove duplicate {nodeName} (ID: {node.GetID()})")
        
        # Remove duplicates
        for node in nodes_to_remove:
            slicer.mrmlScene.RemoveNode(node)
        
        return first_node

    def createJacobianColorNode(self):
        """
        Create Jacobian colormap - only once, reuse if exists
        """
        existingNode = slicer.mrmlScene.GetFirstNodeByName("JacobianMap")
        
        if existingNode:
            # Don't remove it! Just return the existing one
            #print("JacobianMap already exists, reusing")
            existingNode.SetAttribute("MyColourMaps", "1")  # Ensure attribute is set
            return existingNode

        # Only create if it doesn't exist
        print("Creating new JacobianMap")
        
        # Use ColorTableNode
        colorNode = slicer.vtkMRMLColorTableNode()
        colorNode.SetName("JacobianMap")
        colorNode.SetAttribute("DisplayName", "Jacobian (Compression/Expansion)")
        colorNode.SetAttribute("MyColourMaps", "1")
        colorNode.SetTypeToUser()
        colorNode.SetNumberOfColors(256)
        
        # Manually set colors in the table
        for i in range(256):
            val = i / 255.0
            if val < 0.5:  # Below neutral (compression - blue)
                intensity = val * 2.0
                r, g, b = 0.0, 0.0, 0.6 + intensity * 0.4
            elif val > 0.5:  # Above neutral (expansion - red)
                intensity = (val - 0.5) * 2.0
                r, g, b = 0.6 + intensity * 0.4, 0.0, 0.0
            else:  # Neutral (white)
                r, g, b = 1.0, 1.0, 1.0
            
            colorNode.SetColor(i, r, g, b, 1.0)
        
        slicer.mrmlScene.AddNode(colorNode)
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
                    displayNode.SetGlyphTypeFromString("CrossDot2D")
                    displayNode.SetSelected(checked)
                    displayNode.SetHandlesInteractive(False) #??
                    displayNode.SetInteractionHandleScale(0.0)

            else:
                # print("don't show node", node.GetName()) #stores typed in landmark name
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
        self.labelMarkupNode = self.getOrCreateLabelNodeForCurrentVolume()
        # sync checkbox to match visibility
        self.updateHoverCheckboxFromNode()

        # sync checkbox to match visibility 
        self.updateVisualizationCheckboxFromNode()


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
        
      
        # Reset the slice viewers to have no foreground initially on entering and reloading module - much cleaner - NO LONGER DOING THIS
        layoutManager = slicer.app.layoutManager()
        # for sliceViewName in layoutManager.sliceViewNames():
        #     compositeNode = layoutManager.sliceWidget(sliceViewName).mrmlSliceCompositeNode()
        #     compositeNode.SetForegroundVolumeID(None)
    
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
                transformNode=self._parameterNode.transformNode,
                defaultColourMap=self.defaultColorNodeID
            )

            # Create Jacobian  (vector volume)
            jacobianVolume = self.logic.computeJacobianMagnitude(
                referenceVolume=self._parameterNode.referenceVolume,
                transformNode=self._parameterNode.transformNode,
                defaultColourMap=self.defaultColorNodeID
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
            colorNode = None
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
            colorNode = self.ui.colorMapSelector.currentNode()
            if colorNode and self._parameterNode.displacementMagnitudeVolume:
                print("In 490!!!")
                displayNode = self._parameterNode.displacementMagnitudeVolume.GetDisplayNode()
                if displayNode:
                    displayNode.SetAndObserveColorNodeID(colorNode.GetID())







    def onLoadDisplacementVolume(self) -> None:

        '''
        Runs when user selects the Load Volume button
        
        '''

        #selectedVolume = self.ui.existingDisplacementVolumeSelector.currentNode()
        selectedVolume = self.ui.loadedTransformVolume.currentNode()
        flag = self.getBrainShiftFlag(selectedVolume)
        # print("BrainShiftFlag =", flag)

        if not selectedVolume or not selectedVolume.GetDisplayNode():
            slicer.util.errorDisplay("Please select a volume before loading.")
            return

        usVolume = self.ui.referenceVolume.currentNode()
    
        backgroundVolume = self._parameterNode.backgroundVolume
        
        state = self.ui.enableUsBorderDisplay.checkState()


        #DYNAMICLALY SET THE LABEL MARKUP
        self.labelMarkupNode = self.getOrCreateLabelNodeForCurrentVolume()


        
        self.onLoadExpertLabelsClicked()

        #self.onToggleDisplacementVisualizationDisplay(True)
        
        persistentDisplayNode = selectedVolume.GetDisplayNode()

        internalDisplayNode = slicer.mrmlScene.AddNewNodeByClass(persistentDisplayNode.GetClassName())

        #internalDisplayNode.Copy(persistentDisplayNode)
        internalDisplayNode = persistentDisplayNode
        selectedVolume.AddAndObserveDisplayNodeID(internalDisplayNode.GetID())

        numDisplayNodes = selectedVolume.GetNumberOfDisplayNodes()      
        # print(f"Number of display nodes: {numDisplayNodes}")
        # print("Update 1")
        # change to selected color
        
        if not flag: #
            #self.ui.colorMapSelector.setCurrentNode(self.defaultColorNodeID) #cold to hot rainbow
            colorNode = slicer.util.getNode(self.defaultColorNodeID)


        else:
            #colorNode = self.ui.colorMapSelector.currentNode("JacobianMap")
            colorNode = slicer.util.getNode("JacobianMap")
        #if colorNode:
            #displayNode.SetAndObserveColorNodeID(colorNode.GetID())

        if colorNode:
            self.ui.colorMapSelector.setCurrentNode(colorNode)

            internalDisplayNode.SetAndObserveColorNodeID(colorNode.GetID())
            internalDisplayNode.Modified()
          
        normalizedValue = self.ui.opacitySlider.value / 100
        internalDisplayNode.SetOpacity(normalizedValue)
        
        slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(persistentDisplayNode)

        # Do NOT set it as foreground of another volume to avoid cropping
        for sliceName in slicer.app.layoutManager().sliceViewNames():
            sliceComposite = slicer.app.layoutManager().sliceWidget(sliceName).mrmlSliceCompositeNode()
            sliceComposite.SetBackgroundVolumeID(backgroundVolume.GetID())  # your US/reference
            sliceComposite.SetForegroundVolumeID(selectedVolume.GetID())    # displacement field
            sliceComposite.SetForegroundOpacity(normalizedValue)

        self.ui.enableDisplacementVisualizationCheckbox.setChecked(True)
        
        self.ui.enableHoverDisplayCheckbox.setChecked(True)

        # # # remove title of volume node appearing on screen
        # displayNode = selectedVolume.GetDisplayNode()
        # if displayNode:
        #     colorLegendNodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLColorLegendDisplayNode")
        #     for i in range(colorLegendNodes.GetNumberOfItems()):
        #         legendNode = colorLegendNodes.GetItemAsObject(i)
        #         if legendNode.GetNodeReferenceID("primaryDisplay") == displayNode.GetID():
        #             legendNode.SetTitleText(" ")
        #             legendNode.SetVisibility(True)  # ensure the legend is still visible


        # change legend to be color name instead of value if jacobian
        displayNode = selectedVolume.GetDisplayNode()
        if displayNode:
            colorLegendNodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLColorLegendDisplayNode")
            for i in range(colorLegendNodes.GetNumberOfItems()):
                legendNode = colorLegendNodes.GetItemAsObject(i)
                if legendNode.GetNodeReferenceID("primaryDisplay") == displayNode.GetID():
                    legendNode.SetTitleText(" ")  # clear title for both jacobian and displacement

                    if flag == 0:  # displacement
                        legendNode.SetUseColorNamesForLabels(False)  # show numeric values
                        legendNode.SetVisibility(True)
                    elif flag == 1:  # jacobian
                        legendNode.SetUseColorNamesForLabels(True)   # show color names
                        legendNode.SetVisibility(True)  
                    else: # other type of node
                        legendNode.SetUseColorNamesForLabels(False)
                        legendNode.SetVisibility(True)
        


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
            
            # print("Current Window:", window)
            # print("Window Range:", minWindow, "to", maxWindow)
            
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

            # print("Current Level:", level)
            # print("Level Range:", minLevel, "to", maxLevel)

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

    def getBrainShiftFlag(self, volumeNode):
        """
        Returns the BrainShiftFlag value stored in FieldData or PointData.
        FieldData → global flag (1 value)
        PointData → per-voxel array (returns first value)
        """
        if not volumeNode:
            return None

        imageData = volumeNode.GetImageData()
        if not imageData:
            return None

        # --- 1) Try FieldData (global flag) ---
        fd = imageData.GetFieldData()
        if fd:
            arr = fd.GetArray("BrainShiftFlag")
            if arr and arr.GetNumberOfTuples() > 0:
                return int(arr.GetValue(0))

        # --- 2) Try PointData (voxel mask) ---
        pd = imageData.GetPointData()
        if pd:
            arr = pd.GetArray("BrainShiftFlag")
            if arr and arr.GetNumberOfTuples() > 0:
                return int(arr.GetValue(0))

        # --- Not found ---
        return None


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
            # self.labelMarkupNode.SetNthControlPointLabel(0, "Out of bounds")
            self.labelMarkupNode.SetNthControlPointLabel(0, "")
            return

        value = displacementVolume.GetImageData().GetScalarComponentAsDouble(*ijk, 0)

        # get flag
        flag = self.getBrainShiftFlag(displacementVolume)

        # apply flag logic
        if flag == 0:
            # displacement magnitude (mm)
            label = f"{value:.2f} mm"
        elif flag == 1:
            # jacobian -> percent difference from 1
            percent_diff = (value - 1.0) * 100.0
            label = f"{percent_diff:+.1f}%"
        else:
            label = f"{value:.2f}"

        self.labelMarkupNode.SetNthControlPointLabel(0, label)


    def onToggleHoverDisplay(self, enabled: bool) -> None:
        # print("on Toggle Hover Display")
        

        self.labelMarkupNode = self.getOrCreateLabelNodeForCurrentVolume()
        disp = self.labelMarkupNode.GetDisplayNode()

        # set it to be CrossDot2D
        if disp:
            # Set default node type
            disp.SetGlyphType(3)  # if you want to change go look at markups -> display -> advanced -> glyphtype and choose number in list
            disp.SetGlyphScale(8) 

        if enabled:
            # print("enabled")
            
            # make mouse cursor invisible
            for sliceName in slicer.app.layoutManager().sliceViewNames():
                sliceWidget = slicer.app.layoutManager().sliceWidget(sliceName)
                sliceView = sliceWidget.sliceView()
                sliceView.setViewCursor(qt.Qt.BlankCursor)

            # FORCE all relevant visibilities ON
            self.labelMarkupNode.SetDisplayVisibility(True)       # main visibility toggle
            disp.SetVisibility(True)                              # fallback
            disp.SetVisibility2D(True)
            disp.SetVisibility3D(False)                           # i want 2D only
            disp.SetPointLabelsVisibility(True)                   # show text
            disp.SetTextScale(4.5)                                # initial label size

            # connect marksup size toggle
            self.ui.markupSizeSlider.setMinimum(50)     
            self.ui.markupSizeSlider.setMaximum(200)   
            self.ui.markupSizeSlider.setValue(int(disp.GetGlyphScale() * 10))  
            self.ui.markupSizeSlider.setSingleStep(1)
            self.ui.markupSizeSlider.valueChanged.connect(self.onMarkupNodeSizeChanged)

            # setup slider to control text size
            self.ui.markupTextSizeSlider.setMinimum(10)  # corresponds to 1.0
            self.ui.markupTextSizeSlider.setMaximum(100) # corresponds to 10.0
            self.ui.markupTextSizeSlider.setValue(int(disp.GetTextScale() * 10))  # match current label size
            self.ui.markupTextSizeSlider.setSingleStep(1)
            self.ui.markupTextSizeSlider.valueChanged.connect(self.onMarkupTextChanged)

            if self.crosshairObserverTag is None:
                self.crosshairObserverTag = self.crosshairNode.AddObserver(
                    slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent,
                    self.onMouseMoved
        )

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

            # restore cursor to default
            for sliceName in slicer.app.layoutManager().sliceViewNames():
                sliceWidget = slicer.app.layoutManager().sliceWidget(sliceName)
                sliceView = sliceWidget.sliceView()
                sliceView.setViewCursor(qt.Qt.ArrowCursor)
    

    def onMarkupNodeSizeChanged(self, value):
        """Adjust the glyph size of the labelMarkupNode."""
        if hasattr(self, "labelMarkupNode") and self.labelMarkupNode:
            disp = self.labelMarkupNode.GetDisplayNode()
            if disp:
                disp.SetGlyphScale(value / 10.0)


    def onMarkupTextChanged(self, value):
        # Adjust the size of the markup labels based on slider value
        if hasattr(self, "labelMarkupNode") and self.labelMarkupNode:
            disp = self.labelMarkupNode.GetDisplayNode()
            if disp:
                # Scale slider value down by 10 to allow float sizes like 3.5
                disp.SetTextScale(value / 10.0)





    def onToggleDisplacementVisualizationDisplay(self, enabled: bool) -> None:
        # print("on Displacement Visualization Toggle")

        self.volumeNode = self.ui.loadedTransformVolume.currentNode()
        
        if not self.volumeNode:
            return
        
        displayNode = self.volumeNode.GetDisplayNode()

        if enabled:
            # print("enabled")
            
            # Show in slice views by setting foreground opacity
            normalizedValue = self.ui.opacitySlider.value / 100
            
            for sliceName in slicer.app.layoutManager().sliceViewNames():
                sliceComposite = slicer.app.layoutManager().sliceWidget(sliceName).mrmlSliceCompositeNode()
                sliceComposite.SetForegroundVolumeID(self.volumeNode.GetID())
                sliceComposite.SetForegroundOpacity(normalizedValue)
            
            # Optional: also enable 3D visibility if needed
            displayNode.SetVisibility3D(False)  # Keep 3D off if you only want 2D

        else:
            # print("disabled")
            
            # Hide from slice views by setting foreground to None or opacity to 0
            for sliceName in slicer.app.layoutManager().sliceViewNames():
                sliceComposite = slicer.app.layoutManager().sliceWidget(sliceName).mrmlSliceCompositeNode()
                # Option 1: Remove as foreground entirely
                sliceComposite.SetForegroundVolumeID(None)
                # Option 2: Or just set opacity to 0
                # sliceComposite.SetForegroundOpacity(0.0)


    def getCurrentDisplacementVolumeNode(self):
        """Return the displacement volume node, creating it if necessary."""
        volumeNode = self.ui.loadedTransformVolume.currentNode()
        if not volumeNode:
            # Optionally, try to auto-find an existing volume in the scene
            for node in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
                if "Displacement" in node.GetName():
                    return node
            return None
        return volumeNode
    
    def getForegroundVolumeNode(self):
        """Return the volume node currently set as foreground in any slice viewer."""
        layoutManager = slicer.app.layoutManager()
        for sliceName in layoutManager.sliceViewNames():
            sliceComposite = layoutManager.sliceWidget(sliceName).mrmlSliceCompositeNode()
            fgVolumeID = sliceComposite.GetForegroundVolumeID()
            if fgVolumeID:
                node = slicer.mrmlScene.GetNodeByID(fgVolumeID)
                if node:
                    return node
        return None

                
    def updateHoverCheckboxFromNode(self):
        # Syncs the hover display checkbox with the actual visibility of the mouse label node 
        self.labelMarkupNode = self.getOrCreateLabelNodeForCurrentVolume()
        disp = self.labelMarkupNode.GetDisplayNode()
        if disp:
            visible = disp.GetVisibility2D() and self.labelMarkupNode.GetDisplayVisibility()
            self.ui.enableHoverDisplayCheckbox.blockSignals(True)
            self.ui.enableHoverDisplayCheckbox.setChecked(visible)
            self.ui.enableHoverDisplayCheckbox.blockSignals(False)



    def updateVisualizationCheckboxFromNode(self):
        """Syncs the displacement display checkbox with the actual visibility of the volume."""
        volumeNode = self.getCurrentDisplacementVolumeNode()
        if not volumeNode:
            self.ui.enableDisplacementVisualizationCheckbox.blockSignals(True)
            self.ui.enableDisplacementVisualizationCheckbox.setChecked(False)
            self.ui.enableDisplacementVisualizationCheckbox.blockSignals(False)
            return

        displayNode = volumeNode.GetDisplayNode()
        if displayNode:
            visible = displayNode.GetVisibility2D() and volumeNode.GetDisplayVisibility()
            self.ui.enableDisplacementVisualizationCheckbox.blockSignals(True)
            self.ui.enableDisplacementVisualizationCheckbox.setChecked(visible)
            self.ui.enableDisplacementVisualizationCheckbox.blockSignals(False)

        
    
    def getOrCreateMouseLabelNode(self):
        #self.ui.LandmarkSelectorComboBox.addItem(node.GetName()) #stores node name (string)
        #--- We CAN'T hard code the node name because we need two - one for each map - depending on whichever is loaded --- 
        # node = slicer.mrmlScene.GetFirstNodeByName("BrainShiftModule_MouseValueLabel")
        
        # volumeNode = self.ui.loadedTransformVolume.currentNode()

        # if not volumeNode:
        #     return None
        
        # # Create unique name using volume name (sanitize special characters)
        # volumeName = volumeNode.GetName().replace(" ", "_")
        # labelNodeName = f"BrainShiftModule_MouseValueLabel_{volumeName}"

        self.labelMarkupNode = self.getOrCreateLabelNodeForCurrentVolume()

        
        node = slicer.mrmlScene.GetFirstNodeByName(labelNodeName)

        if node is None:
            node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLMarkupsFiducialNode",
               labelNodeName
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

        # print("Renamed to:", text1, text2)
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
                                 defaultColourMap: vtkMRMLColorTableNode
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
        # print("outputVolume image data: ", refImage)
        
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

        # add flag
        img = outputVolume.GetImageData()
        flagArray = vtk.vtkIntArray()
        flagArray.SetName("BrainShiftFlag")
        flagArray.SetNumberOfValues(1)
        flagArray.SetValue(0, 0)  # 0 = displacement
        img.GetFieldData().AddArray(flagArray)
        outputVolume.Modified()


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
        #colorNode = slicer.util.getNode("Viridis")
        if defaultColourMap:
            colorNode = slicer.mrmlScene.GetNodeByID(defaultColourMap)

        if colorNode:
            displayNode.SetAndObserveColorNodeID(colorNode.GetID())
        return outputVolume



    def computeJacobianMagnitude(self,
                                referenceVolume: vtkMRMLScalarVolumeNode,
                                transformNode: vtkMRMLTransformNode,
                                defaultColourMap: vtkMRMLColorTableNode
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

        # add flag
        img = outputVolume.GetImageData()
        flagArray = vtk.vtkIntArray()
        flagArray.SetName("BrainShiftFlag")
        flagArray.SetNumberOfValues(1)
        flagArray.SetValue(0, 1)  # 1 = Jacoban
        img.GetFieldData().AddArray(flagArray)
        outputVolume.Modified()

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
        
        existingNode = slicer.mrmlScene.GetFirstNodeByName("JacobianMap")
        
        if existingNode:
            print("Jacobian exists")
            colorNode = slicer.util.getNode("JacobianMap")
        #if colorNode:
            displayNode.SetAndObserveColorNodeID(colorNode.GetID())
        else:
            colorNode = slicer.mrmlScene.GetNodeByID(defaultColourMap)
            displayNode.SetAndObserveColorNodeID(colorNode.GetID())

            #colorNode = slicer.util.getNode("DefaultColourMap")


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
