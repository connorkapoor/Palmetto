"""
Centralized pythonOCC imports with fallback to mock implementations.
This allows the app to run without pythonOCC installed (with limited functionality).
"""

try:
    # Try importing pythonOCC
    from OCC.Core.TopoDS import (
        TopoDS_Shape, TopoDS_Vertex, TopoDS_Edge, TopoDS_Face,
        TopoDS_Shell, TopoDS_Solid, TopoDS_Compound, topods
    )
    from OCC.Core.TopAbs import (
        TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID,
        TopAbs_FORWARD, TopAbs_REVERSED
    )
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomAbs import (
        GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
        GeomAbs_Sphere, GeomAbs_Torus, GeomAbs_BSplineSurface,
        GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_BSplineCurve
    )
    from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Dir, gp_Ax1
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.TopTools import (
        TopTools_IndexedDataMapOfShapeListOfShape,
        TopTools_ListIteratorOfListOfShape
    )
    from OCC.Core.TopExp import topexp
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.Geom import Geom_Surface, Geom_Plane, Geom_CylindricalSurface
    from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_LinearProperties
    from OCC.Core.GeomLProp import GeomLProp_SLProps
    from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCC.Core.GeomAbs import (
        GeomAbs_BezierSurface, GeomAbs_SurfaceOfRevolution, GeomAbs_SurfaceOfExtrusion,
        GeomAbs_Parabola, GeomAbs_Hyperbola, GeomAbs_BezierCurve
    )
    from OCC.Core.TopLoc import TopLoc_Location

    PYTHONOCC_AVAILABLE = True
    print("✓ pythonOCC loaded successfully")

except ImportError:
    print("⚠️  WARNING: pythonOCC not installed - using mock implementation")
    print("   CAD file loading disabled. To enable: conda install -c conda-forge pythonocc-core")

    # Mock classes
    class TopoDS_Shape:
        def IsNull(self): return True

    class TopoDS_Vertex(TopoDS_Shape):
        pass

    class TopoDS_Edge(TopoDS_Shape):
        pass

    class TopoDS_Face(TopoDS_Shape):
        pass

    class TopoDS_Shell(TopoDS_Shape):
        pass

    class TopoDS_Solid(TopoDS_Shape):
        pass

    class TopoDS_Compound(TopoDS_Shape):
        pass

    class topods:
        @staticmethod
        def Vertex(shape): return TopoDS_Vertex()

        @staticmethod
        def Edge(shape): return TopoDS_Edge()

        @staticmethod
        def Face(shape): return TopoDS_Face()

    class TopAbs_VERTEX: pass
    class TopAbs_EDGE: pass
    class TopAbs_FACE: pass
    class TopAbs_SHELL: pass
    class TopAbs_SOLID: pass

    class TopExp_Explorer:
        def __init__(self, *args): pass
        def More(self): return False
        def Next(self): pass
        def Current(self): return TopoDS_Shape()

    class BRepAdaptor_Surface:
        def __init__(self, *args): pass
        def GetType(self): return 0

    class BRepAdaptor_Curve:
        def __init__(self, *args): pass
        def GetType(self): return 0

    class GeomAbs_Plane: pass
    class GeomAbs_Cylinder: pass
    class GeomAbs_Cone: pass
    class GeomAbs_Sphere: pass
    class GeomAbs_Torus: pass
    class GeomAbs_BSplineSurface: pass
    class GeomAbs_Line: pass
    class GeomAbs_Circle: pass
    class GeomAbs_Ellipse: pass
    class GeomAbs_BSplineCurve: pass

    class gp_Pnt:
        def __init__(self, x=0, y=0, z=0):
            self._x, self._y, self._z = x, y, z
        def X(self): return self._x
        def Y(self): return self._y
        def Z(self): return self._z

    class gp_Vec:
        def __init__(self, x=0, y=0, z=0):
            self._x, self._y, self._z = x, y, z
        def X(self): return self._x
        def Y(self): return self._y
        def Z(self): return self._z
        def Dot(self, other): return 0.0

    class gp_Dir:
        def __init__(self, x=0, y=0, z=1):
            self._x, self._y, self._z = x, y, z
        def X(self): return self._x
        def Y(self): return self._y
        def Z(self): return self._z

    class gp_Ax1:
        def __init__(self, *args): pass
        def Direction(self): return gp_Dir()

    class BRep_Tool:
        @staticmethod
        def Pnt_s(*args): return gp_Pnt()

        @staticmethod
        def Surface_s(*args): return None

    class GProp_GProps:
        def Mass(self): return 0.0
        def CentreOfMass(self): return gp_Pnt()

    class brepgprop:
        @staticmethod
        def SurfaceProperties_s(*args): pass

        @staticmethod
        def LinearProperties_s(*args): pass

    class TopTools_IndexedDataMapOfShapeListOfShape:
        def __init__(self): pass
        def Size(self): return 0

    class TopTools_ListIteratorOfListOfShape:
        def __init__(self, lst): pass
        def More(self): return False
        def Next(self): pass
        def Value(self): return TopoDS_Shape()

    class topexp:
        @staticmethod
        def MapShapesAndAncestors(*args): pass

    class BRepMesh_IncrementalMesh:
        def __init__(self, *args): pass
        def Perform(self): pass

    class Geom_Surface:
        pass

    class Geom_Plane:
        @staticmethod
        def DownCast(surface): return None

    class Geom_CylindricalSurface:
        @staticmethod
        def DownCast(surface): return None

    class geom_Plane:
        @staticmethod
        def DownCast(surface): return None

    # Additional mock functions
    def brepgprop_SurfaceProperties(*args): pass
    def brepgprop_LinearProperties(*args): pass

    class GeomLProp_SLProps:
        def __init__(self, *args): pass

    class GeomAbs_BezierSurface: pass
    class GeomAbs_SurfaceOfRevolution: pass
    class GeomAbs_SurfaceOfExtrusion: pass
    class GeomAbs_Parabola: pass
    class GeomAbs_Hyperbola: pass
    class GeomAbs_BezierCurve: pass

    class TopLoc_Location:
        def __init__(self): pass

    PYTHONOCC_AVAILABLE = False
