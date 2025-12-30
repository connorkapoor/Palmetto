"""
Mock pythonOCC classes for demonstration purposes.
This allows the app to run without requiring full pythonOCC installation.

NOTE: This is a stub implementation. To work with actual CAD files,
install pythonocc-core via: conda install -c conda-forge pythonocc-core
"""


class TopoDS_Shape:
    """Mock TopoDS_Shape class."""
    pass


class TopoDS_Face:
    """Mock TopoDS_Face class."""
    pass


class TopoDS_Edge:
    """Mock TopoDS_Edge class."""
    pass


class TopoDS_Vertex:
    """Mock TopoDS_Vertex class."""
    pass


class gp_Pnt:
    """Mock gp_Pnt class."""
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    def X(self):
        return self.x

    def Y(self):
        return self.y

    def Z(self):
        return self.z


class gp_Vec:
    """Mock gp_Vec class."""
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    def X(self):
        return self.x

    def Y(self):
        return self.y

    def Z(self):
        return self.z


# Note: This is a demonstration stub
# For production use, install: conda install -c conda-forge pythonocc-core
PYTHONOCC_AVAILABLE = False
