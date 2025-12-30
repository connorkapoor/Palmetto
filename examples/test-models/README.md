# Test CAD Models

This directory is for storing test STEP/IGES/BREP files for testing the Palmetto feature recognition system.

## Where to Get Test Files

### Free CAD Model Repositories:

1. **GrabCAD** (https://grabcad.com/)
   - Huge library of free CAD models
   - Download as STEP format
   - Search for: "bracket", "housing", "mechanical part"

2. **TraceParts** (https://www.traceparts.com/)
   - Industrial parts library
   - Many available in STEP format

3. **McMaster-Carr** (https://www.mcmaster.com/)
   - Download CAD models of standard parts
   - Available in STEP format

4. **Open CASCADE Test Files**
   - Sample STEP files from OpenCASCADE
   - https://github.com/tpaviot/pythonocc-demos/tree/master/assets/models

### Creating Your Own Test Files:

If you have access to CAD software (FreeCAD, Fusion 360, SolidWorks, etc.):

1. Create a simple part with features like:
   - Drilled holes (countersunk, simple, threaded)
   - Cylindrical bosses/shafts
   - Fillets and chamfers
   - Pockets and cavities

2. Export as STEP (.step or .stp) format

3. Place in this directory

## Recommended Test Cases

For thorough testing of the recognition system, try parts with:

- **Holes**: M6, M8 bolt holes, countersunk screw holes
- **Shafts**: Protruding cylinders, pins
- **Fillets**: R3mm, R5mm edge blends
- **Cavities**: Rectangular pockets, blind holes, slots

## Example File Names

Good file naming helps organize tests:
- `bracket_with_holes.step` - L-bracket with mounting holes
- `shaft_with_keyway.step` - Simple shaft
- `housing_complex.step` - Complex part with multiple features
- `simple_block.step` - Basic test case

## Quick FreeCAD Test Part

If you have FreeCAD installed:

1. Open FreeCAD
2. Create a Part Design workbench
3. Make a simple box (100x100x20mm)
4. Add 4 holes (8mm diameter) at corners
5. Add fillets (3mm) to top edges
6. Export → STEP → `simple_test.step`
7. Upload to Palmetto!

## Current Test Files

Place your test STEP files here. The application will recognize:
- `.step`, `.stp` - STEP files
- `.iges`, `.igs` - IGES files
- `.brep` - BREP files
