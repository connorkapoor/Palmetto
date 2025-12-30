# FindOpenCASCADE.cmake
# Find OpenCASCADE libraries (Ubuntu package compatible)

find_path(OpenCASCADE_INCLUDE_DIR
    NAMES Standard_Version.hxx
    PATHS
        /usr/include/opencascade
        /usr/local/include/opencascade
        ${CMAKE_PREFIX_PATH}/include/opencascade
)

# Find OCCT libraries
set(OCCT_LIBS
    TKernel TKMath TKG2d TKG3d TKGeomBase TKBRep TKGeomAlgo
    TKTopAlgo TKPrim TKBO TKBool TKOffset TKFillet TKMesh
    TKSTEP TKSTEPBase TKSTEPAttr TKSTEP209 TKIGES TKXSBase
    TKXDESTEP TKXDEIGES TKBinL TKXmlL TKPLCAF TKLCAF TKCAF
    TKV3d TKService TKOpenGl
)

set(OpenCASCADE_LIBRARIES "")

foreach(lib ${OCCT_LIBS})
    find_library(${lib}_LIBRARY
        NAMES ${lib}
        PATHS
            /usr/lib/x86_64-linux-gnu
            /usr/lib
            /usr/local/lib
            ${CMAKE_PREFIX_PATH}/lib
    )
    if(${lib}_LIBRARY)
        list(APPEND OpenCASCADE_LIBRARIES ${${lib}_LIBRARY})
    endif()
endforeach()

# Set version (Ubuntu 22.04 has OCCT 7.5)
set(OpenCASCADE_VERSION "7.5.1")

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(OpenCASCADE
    REQUIRED_VARS OpenCASCADE_INCLUDE_DIR OpenCASCADE_LIBRARIES
    VERSION_VAR OpenCASCADE_VERSION
)

mark_as_advanced(OpenCASCADE_INCLUDE_DIR OpenCASCADE_LIBRARIES)
